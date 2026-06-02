import json
import pytest
from pathlib import Path

import jsonschema

EVAL_DIR = Path(__file__).parent.parent
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
