import importlib.util
import json
from pathlib import Path

from lib.response_cache import ResponseCache
from lib.website_candidates import interpret_haiku

_EXP = Path(__file__).resolve().parents[1] / "experiments" / "2026-09-26-website-resolution"
_spec = importlib.util.spec_from_file_location("wr_haiku_cc_bridge", _EXP / "haiku_cc_bridge.py")
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)

FINAL = ('Found it.\n{"own_site": "https://www.hsa.ie/", "own_site_evidence_url": "https://www.hsa.ie/", '
         '"parent_site": null, "has_own_site": "yes", "defunct": "no", "defunct_source": null, "notes": "HSA site"}')


def _answer(pid=1, results=(("https://www.hsa.ie/eng/", "HSA"),), queries=("hsa ireland", "hsa.ie"), text=FINAL):
    return {"public_body_id": pid, "queries": list(queries),
            "results_seen": [{"url": u, "title": t} for u, t in results], "final_text": text}


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")


def test_answer_to_raw_roundtrips_through_interpret_haiku():
    raw = bridge.answer_to_raw("p", _answer())
    assert raw["source"] == "claude_code_subagent"
    out = interpret_haiku(raw)
    assert [c["url"] for c in out["candidates"]] == ["https://www.hsa.ie/"]
    assert out["candidates"][0]["origin"] == "haiku_search"
    assert out["search_count"] == 2
    assert out["signals"]["has_own_site"] == "yes"


def test_uncited_own_site_is_rejected():
    out = interpret_haiku(bridge.answer_to_raw("p", _answer(results=())))
    assert out["candidates"] == [] and out["rejected_uncited"] == ["https://www.hsa.ie/"]


def test_ingest_search_classifies_answers(tmp_path):
    prompts, answers, cache = tmp_path / "sp", tmp_path / "sa", ResponseCache(tmp_path / "c")
    for pid in (1, 2, 3, 4):
        _write(prompts / f"{pid}.json", {"public_body_id": pid, "name": "x", "key": f"k{pid}", "prompt": f"p{pid}"})
    _write(answers / "1.json", _answer(1))
    _write(answers / "2.json", "{not json")                              # invalid: unparsable
    _write(answers / "3.json", _answer(pid=99))                          # invalid: wrong id
    # 4 has no answer → missing
    got = bridge.ingest_search(prompts, answers, cache)
    assert got["ingested"] == 1 and got["missing"] == [4] and sorted(got["invalid"]) == [2, 3]
    assert cache.get("k1")["prompt"] == "p1"
    assert cache.get("k2") is None and cache.get("k3") is None


def test_ingest_search_flags_over_budget_but_keeps_it(tmp_path):
    prompts, answers, cache = tmp_path / "sp", tmp_path / "sa", ResponseCache(tmp_path / "c")
    _write(prompts / "1.json", {"public_body_id": 1, "name": "x", "key": "k1", "prompt": "p1"})
    _write(answers / "1.json", _answer(queries=("a", "b", "c", "d")))
    got = bridge.ingest_search(prompts, answers, cache)
    assert got["over_budget"] == [1] and got["ingested"] == 1


def test_ingest_judge_caches_parsed_and_skips_unparsable(tmp_path):
    prompts, answers, cache = tmp_path / "jp", tmp_path / "ja", ResponseCache(tmp_path / "c")
    for k in ("ka", "kb", "kc"):
        _write(prompts / f"{k}.json", {"key": k, "backend": "haiku-cc", "prompt": "judge me"})
    _write(answers / "ka.json", {"key": "ka", "text": '{"label": "own_site", "rationale": "logo + name"}'})
    _write(answers / "kb.json", {"key": "kb", "text": "I think it's their site"})   # unparsable → not cached
    got = bridge.ingest_judge(prompts, answers, cache)
    assert got["ingested"] == 1 and got["invalid"] == ["kb"] and got["missing"] == ["kc"]
    assert cache.get("ka")["result"] == {"label": "own_site", "rationale": "logo + name", "judge": "haiku-cc"}
    assert cache.get("kb") is None


def test_pending_lists_prompts_without_answers(tmp_path):
    prompts, answers = tmp_path / "sp", tmp_path / "sa"
    for pid in (1, 2):
        _write(prompts / f"{pid}.json", {"public_body_id": pid})
    _write(answers / "1.json", {})
    assert [p.name for p in bridge.pending(prompts, answers)] == ["2.json"]
