import json

from lib.file_utils import IncrementalWriter
from lib.website_resolve import (empty_gathered, evict_pending, make_judge, merge_gathered,
                                 resolve_body)

BODY = {"public_body_id": 5, "name": "Oweninny Power DAC", "parent_name": "ESB"}


def _ok_probe(url):
    return {"url": url, "final_url": url, "outcome": "ok", "status_code": 200, "error": None,
            "evidence": {"title": "Oweninny Wind Farm", "meta_description": "", "site_name": "",
                         "h1": "", "text_head": "wind", "footer_text": ""}}


def _unsure(*a, **k):
    raise RuntimeError("ollama down")


def _gathered(*urls, **extra):
    g = empty_gathered()
    g["candidates"] = [{"url": u, "origin": "haiku_search"} for u in urls]
    g["tiers"] = ["seed", "haiku_search"]
    g.update(extra)
    return g


def test_unanswered_judge_holds_body_pending(tmp_path):
    judge_fn, rec = make_judge(tmp_path)
    judge_fn = _patch_primary(judge_fn, _unsure)
    g = _gathered("https://oweninny.ie/", signals={"has_own_site": "no"})
    d = resolve_body(BODY, g, probe_fn=_ok_probe, judge_fn=judge_fn, recorder=rec,
                     required_tiers=("seed", "haiku_search"))
    assert d["website_status"] == "pending"
    assert d["website_resolution"]["pending_reason"] == "judge_pending"
    assert rec.misses == 1 and len(list((tmp_path / "haiku_cc_exchange" / "judge_prompts").glob("*.json"))) == 1


def test_own_site_wins_over_pending_judge(tmp_path):
    judge_fn, rec = make_judge(tmp_path)
    calls = iter(["own", "unsure"])

    def primary(prompt):
        if next(calls) == "own":
            return json.dumps({"label": "own_site", "rationale": "name in title"})
        raise RuntimeError("ollama down")

    judge_fn = _patch_primary(judge_fn, primary)
    g = _gathered("https://oweninny.ie/", "https://esb.ie/")
    d = resolve_body(BODY, g, probe_fn=_ok_probe, judge_fn=judge_fn, recorder=rec,
                     required_tiers=("seed", "haiku_search"))
    assert d["website_status"] == "own_site"
    assert d["official_website_url"].startswith("https://oweninny.ie")


def test_hold_reason_passes_through(tmp_path):
    judge_fn, rec = make_judge(tmp_path)
    d = resolve_body(BODY, _gathered(), probe_fn=_ok_probe, judge_fn=judge_fn, recorder=rec,
                     hold_reason="haiku_pending")
    assert d["website_status"] == "pending"
    assert d["website_resolution"]["pending_reason"] == "haiku_pending"


def test_merge_gathered_concatenates_and_keeps_first_pending_reason():
    a = {**empty_gathered(), "candidates": [{"url": "a", "origin": "x"}], "tiers": ["seed"]}
    b = {**empty_gathered(), "candidates": [{"url": "b", "origin": "y"}], "tiers": ["haiku_search"],
         "signals": {"has_own_site": "no", "defunct": None}, "pending_reason": "p"}
    m = merge_gathered([a, b])
    assert [c["url"] for c in m["candidates"]] == ["a", "b"]
    assert m["tiers"] == ["seed", "haiku_search"]
    assert m["signals"] == {"has_own_site": "no"}
    assert m["pending_reason"] == "p"


def test_evict_pending_only_drops_pending_records(tmp_path):
    out = tmp_path / "output.json"
    w = IncrementalWriter(out, "s", force=True)
    w.append([{"public_body_id": 1, "website_status": "pending"},
              {"public_body_id": 2, "website_status": "own_site"}])
    w.finalize()
    w2 = IncrementalWriter(out, "s")
    assert evict_pending(w2) == 1
    assert w2.is_processed(2) and not w2.is_processed(1)


def _patch_primary(judge_fn, fn):
    """Return judge_fn with its primary backend replaced by fn (api_fn)."""
    from functools import partial
    return partial(judge_fn.func, **{**judge_fn.keywords, "primary_fn": fn})
