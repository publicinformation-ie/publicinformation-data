import importlib.util
from pathlib import Path

_EXP = Path(__file__).resolve().parents[1] / "experiments" / "2026-09-26-website-resolution"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


runner = _load("wr_run_experiment", _EXP / "run_experiment.py")


def test_seed_only_end_to_end_with_fakes(tmp_path):
    bodies = [
        {"public_body_id": 1, "name": "Health and Safety Authority", "parent_id": None,
         "parent_name": None, "gold_status": "own_site", "gold_url": "https://www.hsa.ie/"},
        {"public_body_id": 2, "name": "Orliven Ltd", "parent_id": 5, "parent_name": "ESB",
         "gold_status": "no_own_site", "gold_url": ""},
    ]
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={1: "www.hsa.ie"}, prior={}, refresh=False)

    def probe(url):
        ok = "hsa.ie" in url
        return {"url": url, "final_url": url, "outcome": "ok" if ok else "nxdomain",
                "evidence": {"title": "HSA"} if ok else None}

    def judge(body, url, evidence):
        return {"label": "own_site", "rationale": "", "judge": "fake"}

    out = runner.evaluate(bodies, ["seed_only"], ctx, probe, judge, parent_lookup={5: "https://esb.ie/"})
    rows = {r["public_body_id"]: r for r in out["seed_only"]}
    assert rows[1]["website_status"] == "own_site"
    assert rows[1]["official_website_url"] == "https://www.hsa.ie/"
    # seed_only exhausts only the seed tier; the child has no parent evidence from seed alone
    assert rows[2]["website_status"] == "not_found"
    assert ctx["spend"]["apify_paid_queries"] == 0 and ctx["spend"]["haiku_paid_calls"] == 0


def test_foigovie_bare_host_is_normalised(tmp_path):
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={1: "www.hsa.ie"}, prior={}, refresh=False)
    seed = runner.load_approach("seed_only")
    got = seed.gather({"public_body_id": 1, "name": "HSA Test"}, ctx)
    assert got["candidates"][0] == {"url": "https://www.hsa.ie/", "origin": "foigovie"}


import json as _json

from lib.response_cache import ResponseCache
from lib.website_judge import judge_cascade

import lib.haiku_cc_exchange as bridge

_HSA = {"public_body_id": 1, "name": "Health and Safety Authority", "parent_id": None,
        "parent_name": None, "gold_status": "own_site", "gold_url": "https://www.hsa.ie/"}
_FINAL = ('{"own_site": "https://www.hsa.ie/", "own_site_evidence_url": null, "parent_site": null, '
          '"has_own_site": "yes", "defunct": "no", "defunct_source": null, "notes": "n"}')


def _probe(url):
    ok = "hsa.ie" in url
    return {"url": url, "final_url": url, "outcome": "ok" if ok else "nxdomain",
            "evidence": {"title": "HSA"} if ok else None}


def _judge(body, url, evidence):
    return {"label": "own_site", "rationale": "", "judge": "fake"}


def _seed_cc_cache(tmp_path, body, queries=("hsa ireland",)):
    cc = runner.load_approach("haiku_cc")
    answer = {"public_body_id": body["public_body_id"], "queries": list(queries),
              "results_seen": [{"url": "https://www.hsa.ie/eng/", "title": "HSA"}], "final_text": _FINAL}
    ResponseCache(tmp_path / "haiku_cc").put(cc.search_key(body), bridge.answer_to_raw("p", answer))


def test_haiku_cc_source_uses_ingested_answer(tmp_path):
    _seed_cc_cache(tmp_path, _HSA)
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={}, prior={}, refresh=False)
    out = runner.evaluate([_HSA], ["haiku"], ctx, _probe, _judge, parent_lookup={})
    row = out["haiku"][0]
    assert row["website_status"] == "own_site"
    assert "hsa.ie" in row["official_website_url"]


def test_haiku_cc_missing_answer_is_pending_not_not_found(tmp_path):
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={}, prior={}, refresh=False)
    def dead(url):  # seed domain guesses must not resolve, or the body settles without Haiku
        return {"url": url, "final_url": url, "outcome": "nxdomain", "evidence": None}

    out = runner.evaluate([_HSA], ["haiku"], ctx, dead, _judge, parent_lookup={})
    assert out["haiku"][0]["website_status"] == "pending"


def test_haiku_cc_searches_counted_once_across_approaches(tmp_path):
    _seed_cc_cache(tmp_path, _HSA, queries=("a", "b"))
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={}, prior={}, refresh=False)
    runner.evaluate([_HSA], ["haiku", "haiku_then_apify"], ctx, _probe, _judge, parent_lookup={})
    assert ctx["spend"]["haiku_searches"] == 2 and ctx["spend"]["haiku_paid_calls"] == 0


def test_export_search_prompts_keys_match_approach(tmp_path):
    assert runner.export_search_prompts([_HSA], tmp_path) == 1
    spec = _json.loads((tmp_path / "1.json").read_text(encoding="utf-8"))
    assert spec["key"] == runner.load_approach("haiku_cc").search_key(_HSA)
    assert "Health and Safety Authority" in spec["prompt"]


def test_judge_recorder_writes_prompt_and_does_not_poison_cache(tmp_path):
    rec = runner.JudgePromptRecorder(tmp_path / "jp", runner.CC_JUDGE)
    cache = ResponseCache(tmp_path / "judge")
    r = judge_cascade({"name": "HSA"}, "https://www.hsa.ie/", {"title": "HSA"},
                      primary=runner.CC_JUDGE, fallback=None, primary_fn=rec, cache=cache)
    assert r["label"] == "unsure"
    assert len(rec.recorded) == 1
    spec = _json.loads((tmp_path / "jp" / f"{rec.recorded[0]}.json").read_text(encoding="utf-8"))
    assert spec["backend"] == "haiku-cc"
    assert spec["key"] == ResponseCache.key("judge", "haiku-cc", spec["prompt"])
    assert cache.get(spec["key"]) is None
