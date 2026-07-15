"""Tests for the llm-repair compare/scoring functions."""
import importlib.util
from pathlib import Path

_COMPARE_PATH = (
    Path(__file__).parents[2]
    / "experiments/2026-07-15-llm-structuring-repair/compare.py"
)
_spec = importlib.util.spec_from_file_location("llm_repair_compare", _COMPARE_PATH)
assert _spec is not None and _spec.loader is not None
_compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_compare)

repair_stats = _compare.repair_stats

# A clean 6-col entry (all fields present -> trips no predicate).
_CLEAN_ENTRY = {
    "foi_reference_id": "FOI-1", "date_received": "2024-01-02",
    "request_description": "docs", "requester_type": "Journalist",
    "decision_status": "Granted", "decision_date": "2024-02-01",
}
# Arm A rows with a newline_split_row: a 6-col table whose 2nd data row has
# exactly one non-null cell.
_SPLIT_ARM_A = [
    ["ref", "date", "desc", "type", "status", "ddate"],
    ["FOI-1", "2024-01-02", "docs", "Journalist", "Granted", "2024-02-01"],
    ["continued text", None, None, None, None, None],
]


def test_repair_flips_split_to_clean():
    records = [{
        "file_url": "u1", "stratum": "newline_split_row",
        "arm_a_rows": _SPLIT_ARM_A,
        "arm_b_entries": [_CLEAN_ENTRY, dict(_CLEAN_ENTRY, foi_reference_id="FOI-2")],
        "error": None,
    }]
    stats = repair_stats(records)
    assert stats["broken"] == 1
    assert stats["repaired"] == 1
    assert stats["repair_rate"] == 1.0
    assert stats["regressions"] == []


def test_failure_record_counts_broken_not_repaired():
    records = [{
        "file_url": "u2", "stratum": "newline_split_row",
        "arm_a_rows": _SPLIT_ARM_A,
        "arm_b_entries": None, "error": "empty_structured_output",
    }]
    stats = repair_stats(records)
    assert stats["broken"] == 1
    assert stats["repaired"] == 0
    assert stats["repair_rate"] == 0.0


def test_regression_detected():
    # Arm A clean (no split); arm B introduces a split row -> regression.
    clean_arm_a = [
        ["ref", "date", "desc", "type", "status", "ddate"],
        ["FOI-1", "2024-01-02", "docs", "J", "Granted", "2024-02-01"],
    ]
    split_entry = {"foi_reference_id": "only-this"}  # one non-null of six
    records = [{
        "file_url": "u3", "stratum": "null_column",
        "arm_a_rows": clean_arm_a,
        "arm_b_entries": [_CLEAN_ENTRY, split_entry],
        "error": None,
    }]
    stats = repair_stats(records)
    assert "u3" in stats["regressions"]
