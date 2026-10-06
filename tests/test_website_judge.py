from lib.response_cache import ResponseCache
from lib.website_judge import judge, judge_cascade, parse_judge_response, build_prompt

BODY = {"name": "Orliven Ltd", "legal_status": "Commercial Non-Financial Corporation",
        "parent_name": "Electricity Supply Board", "government_department": None, "cro": "654321"}
EV = {"title": "Orliven", "meta_description": "", "site_name": "", "h1": "Orliven",
      "text_head": "Orliven wind farm project", "footer_text": ""}


def fn_returning(text, calls=None):
    def _fn(prompt):
        if calls is not None:
            calls.append(prompt)
        return text
    return _fn


def test_prompt_contains_body_facts_and_evidence():
    p = build_prompt(BODY, "https://orliven.ie/", EV)
    assert "Orliven Ltd" in p and "Electricity Supply Board" in p and "wind farm" in p


def test_parse_valid_and_fenced_json():
    assert parse_judge_response('{"label": "own_site", "rationale": "match"}') == ("own_site", "match")
    assert parse_judge_response('```json\n{"label":"parent_site","rationale":"r"}\n```')[0] == "parent_site"


def test_parse_garbage_is_unsure():
    assert parse_judge_response("I think yes")[0] == "unsure"
    assert parse_judge_response('{"label": "definitely"}')[0] == "unsure"


def test_directory_short_circuits_without_llm():
    calls = []
    r = judge(BODY, "https://www.solocheck.ie/Irish-Company/Orliven", EV,
              api_fn=fn_returning('{"label":"own_site"}', calls))
    assert r["label"] == "directory" and r["judge"] == "rule" and calls == []


def test_cro_in_footer_is_own_site_without_llm():
    calls = []
    ev = {**EV, "footer_text": "Registered in Ireland No. 654321"}
    r = judge(BODY, "https://orliven.ie/", ev, api_fn=fn_returning("{}", calls))
    assert r["label"] == "own_site" and r["judge"] == "cro_match" and calls == []


def test_no_evidence_is_unsure():
    assert judge(BODY, "https://orliven.ie/", None, api_fn=fn_returning("{}"))["label"] == "unsure"


def test_backend_error_fails_closed():
    def boom(prompt):
        raise ConnectionError("ollama not running")
    r = judge(BODY, "https://orliven.ie/", EV, api_fn=boom)
    assert r["label"] == "unsure" and "ConnectionError" in r["rationale"]


def test_cascade_escalates_unsure_to_fallback():
    r = judge_cascade(BODY, "https://orliven.ie/", EV, fallback="haiku",
                      primary_fn=fn_returning('{"label":"unsure","rationale":"?"}'),
                      fallback_fn=fn_returning('{"label":"own_site","rationale":"ok"}'))
    assert r["label"] == "own_site" and r["judge"] == "haiku"


def test_cascade_keeps_confident_primary():
    fallback_calls = []
    r = judge_cascade(BODY, "https://orliven.ie/", EV,
                      primary_fn=fn_returning('{"label":"other_entity","rationale":"namesake"}'),
                      fallback_fn=fn_returning("{}", fallback_calls))
    assert r["label"] == "other_entity" and fallback_calls == []


def test_cache_prevents_second_call(tmp_path):
    calls = []
    cache = ResponseCache(tmp_path)
    fn = fn_returning('{"label":"own_site","rationale":"x"}', calls)
    judge(BODY, "https://orliven.ie/", EV, api_fn=fn, cache=cache)
    judge(BODY, "https://orliven.ie/", EV, api_fn=fn, cache=cache)
    assert len(calls) == 1


import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_no_anthropic_api_in_website_resolution_code():
    paths = [*(_REPO / "src" / "lib").glob("website_*.py"), *(_REPO / "src" / "lib").glob("haiku_*.py"),
             *(_REPO / "pipelines" / "cso_pipeline").rglob("*.py")]
    offenders = [str(p.relative_to(_REPO)) for p in paths
                 if re.search(r"import anthropic|ANTHROPIC_API_KEY|anthropic\.Anthropic",
                              p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_cascade_has_no_default_fallback():
    import inspect
    from lib.website_judge import judge_cascade
    assert inspect.signature(judge_cascade).parameters["fallback"].default is None
