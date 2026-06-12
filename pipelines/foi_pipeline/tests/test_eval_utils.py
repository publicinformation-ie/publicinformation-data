import json
import pytest
from pathlib import Path

import jsonschema

EVAL_DIR = Path(__file__).parent.parent / "eval"
SCHEMA = json.loads((EVAL_DIR / "eval_schema.json").read_text())


def _validate(instance, defn):
    schema = {**SCHEMA, "$ref": f"#/$defs/{defn}"}
    jsonschema.validate(instance, schema)


def test_schema_accepts_minimal_eval_results():
    _validate(
        {
            "step": "find_disclosure_pages",
            "metrics": [
                {"name": "f1", "value": 0.574,
                 "counts": {"TP": 31, "FP": 31}, "is_primary": True}
            ],
            "input_hash": "a" * 64,
            "judge_model": None,
        },
        "eval_results",
    )


def test_schema_rejects_eval_results_missing_metrics():
    with pytest.raises(jsonschema.ValidationError):
        _validate(
            {"step": "x", "input_hash": "a" * 64, "judge_model": None},
            "eval_results",
        )


def test_schema_accepts_issue():
    _validate(
        {
            "severity": "warning",
            "description": "12 files appear non-FOI",
            "affected_count": 12,
            "affected_ids": ["https://x/a.pdf"],
            "suggested_upstream_step": "find_disclosure_files",
            "suggestion_detail": "add a content-type filter",
            "confidence": 0.8,
        },
        "issue",
    )


from eval import utils as eval_utils


def test_input_hash_is_stable_and_content_addressed(tmp_path):
    f = tmp_path / "input.json"
    f.write_text('{"b": 2, "a": 1}')
    h1 = eval_utils.input_hash(f)
    f.write_text('{"b": 2, "a": 1}')  # same bytes, new mtime
    assert eval_utils.input_hash(f) == h1
    assert len(h1) == 64
    f.write_text('{"a": 1}')
    assert eval_utils.input_hash(f) != h1


def test_is_eval_stale_when_results_missing(tmp_path):
    results = tmp_path / "eval_results.json"
    fixture = tmp_path / "input.json"
    fixture.write_text("{}")
    assert eval_utils.is_eval_stale(results, [fixture]) is True


def test_is_eval_stale_when_dependency_newer(tmp_path):
    import os, time
    results = tmp_path / "eval_results.json"
    fixture = tmp_path / "input.json"
    results.write_text("{}")
    fixture.write_text("{}")
    future = time.time() + 100
    os.utime(fixture, (future, future))
    assert eval_utils.is_eval_stale(results, [fixture]) is True


def test_is_eval_stale_false_when_up_to_date(tmp_path):
    import os, time
    results = tmp_path / "eval_results.json"
    fixture = tmp_path / "input.json"
    fixture.write_text("{}")
    results.write_text("{}")
    future = time.time() + 100
    os.utime(results, (future, future))
    assert eval_utils.is_eval_stale(results, [fixture]) is False


def test_write_eval_outputs_writes_validated_files(tmp_path):
    results = eval_utils.EvalResults(
        step="demo",
        metrics=[eval_utils.Metric("f1", 0.5, {"TP": 1, "FP": 1}, is_primary=True)],
        input_hash="a" * 64,
        judge_model=None,
    )
    issues = [eval_utils.Issue("warning", "d", 1, ["x"], None, None, 0.5)]
    eval_utils.write_eval_outputs(tmp_path, results, issues)

    written = json.loads((tmp_path / "eval_results.json").read_text())
    assert written["metrics"][0]["name"] == "f1"
    assert json.loads((tmp_path / "issues.json").read_text())[0]["severity"] == "warning"


def test_write_eval_outputs_rejects_invalid_results(tmp_path):
    bad = eval_utils.EvalResults(step="demo", metrics=[], input_hash="bad", judge_model=None)
    with pytest.raises(jsonschema.ValidationError):
        eval_utils.write_eval_outputs(tmp_path, bad, [])
