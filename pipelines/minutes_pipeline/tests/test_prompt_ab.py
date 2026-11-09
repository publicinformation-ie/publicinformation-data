"""Tests for the prompt A/B probe (prompt_ab.py): durable per-call flush and
resume-by-key. Stubbed backend only — no live calls.

The experiment directory name contains dashes, so prompt_ab.py is loaded via
importlib (same pattern as test_motion_model_sweep_extract.py).
"""
import importlib.util
import json
from pathlib import Path

_AB = (Path(__file__).parent.parent / "experiments"
       / "2026-10-07-motion-model-sweep" / "prompt_ab.py")


def _load():
    spec = importlib.util.spec_from_file_location("prompt_ab", _AB)
    assert spec is not None and spec.loader is not None, f"Cannot load {_AB}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load()

# Priced spec model: cost arithmetic needs a real id (unknown models fail closed).
_MODEL = "opencode-go/deepseek-v4.1-flash"
_PROMPTS = {"p1": "system one"}


def _files(n=2):
    return [{"file_url": f"https://example.ie/f{i}.pdf",
             "text": "That the council approves the works. " * 5,
             "extractor": "pdfplumber", "old_motion_count": 1,
             "old_motions": []} for i in range(n)]


def _ok_backend(calls):
    def backend(system, user, model, effort):
        calls.append((system, model))
        return '{"meeting_date": null, "motions": []}'
    return backend


def test_run_ab_writes_one_jsonl_line_per_call(tmp_path):
    calls = []
    out = tmp_path / "ab.jsonl"
    summary = _mod.run_ab(_files(2), out, workers=2, backend=_ok_backend(calls),
                          prompts=_PROMPTS, models=[_MODEL])
    lines = out.read_text().splitlines()
    assert len(lines) == 2 and len(calls) == 2
    recs = [json.loads(x) for x in lines]
    assert {r["prompt"] for r in recs} == {"p1"}
    assert all(r["model"] == _MODEL and r["motions"] == [] for r in recs)
    assert all(r["tokens"] and r["cost_usd"] is not None for r in recs)
    assert summary["submitted"] == 2


def test_run_ab_resumes_skipping_completed_keys(tmp_path):
    out = tmp_path / "ab.jsonl"
    f = _files(1)[0]
    key = _mod.record_key("p1", _MODEL, f["file_url"])
    out.write_text(json.dumps({"key": key, "prompt": "p1", "model": _MODEL,
                               "file_url": f["file_url"]}) + "\n")
    calls = []
    _mod.run_ab([f], out, workers=1, backend=_ok_backend(calls),
                prompts=_PROMPTS, models=[_MODEL])
    assert calls == []                                      # completed key skipped
    assert len(out.read_text().splitlines()) == 1           # no duplicate


def test_run_ab_records_failclosed_error_still_persisted(tmp_path):
    out = tmp_path / "ab.jsonl"

    def boom(system, user, model, effort):
        raise RuntimeError("gateway down")

    _mod.run_ab(_files(1), out, workers=1, backend=boom,
                prompts=_PROMPTS, models=[_MODEL])
    recs = [json.loads(x) for x in out.read_text().splitlines()]
    assert len(recs) == 1
    assert recs[0]["motions"] is None
    assert "RuntimeError" in recs[0]["error"]


def test_run_ab_unknown_model_fails_closed(tmp_path):
    out = tmp_path / "ab.jsonl"
    _mod.run_ab(_files(1), out, workers=1, backend=_ok_backend([]),
                prompts=_PROMPTS, models=["opencode-go/not-in-price-table"])
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["cost_usd"] is None and rec["error"]


def test_report_scores_each_prompt_against_its_own_gold(tmp_path):
    """The offline report groups by prompt and references gold under the same
    prompt; a modified-vs-production delta column is emitted."""
    report = _load_report()
    out = tmp_path / "ab.jsonl"
    files = _files(1)
    url = files[0]["file_url"]
    gold_text = "That the council approves the works."
    rows = [
        ("production", _mod.GOLD_MODEL, [{"motion_text": gold_text, "proposer": "A",
                                          "seconder": None, "status_label": "carried"}]),
        ("exclude_procedural", _mod.GOLD_MODEL, [{"motion_text": gold_text, "proposer": "A",
                                                  "seconder": None, "status_label": "carried"}]),
        ("production", _MODEL, [{"motion_text": gold_text, "proposer": "A",
                                 "seconder": None, "status_label": "carried"}]),
        ("exclude_procedural", _MODEL, []),
    ]
    with out.open("w") as fh:
        for prompt, model, motions in rows:
            fh.write(json.dumps({
                "key": _mod.record_key(prompt, model, url), "prompt": prompt,
                "model": model, "file_url": url, "motions": motions,
                "stated_date": None,
                "tokens": {"prompt": 10, "completion": 5, "total": 15},
                "cost_usd": 0.0001, "error": None}) + "\n")
    table = report.build_table(json.loads(json.dumps({"files": files})), out)
    prod = table["production"][_MODEL]
    mod = table["exclude_procedural"][_MODEL]
    assert prod["text_f1"] == 1.0
    assert mod["text_f1"] == 0.0
    assert table["delta"][_MODEL]["text_f1"] == -1.0


def _load_report():
    path = _AB.parent / "prompt_ab_report.py"
    spec = importlib.util.spec_from_file_location("prompt_ab_report", path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
