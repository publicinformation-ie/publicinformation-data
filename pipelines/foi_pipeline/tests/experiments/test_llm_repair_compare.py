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


match_rows = _compare.match_rows
fidelity_scores = _compare.fidelity_scores


def _entry(**kw):
    base = {f: None for f in _compare.CANONICAL_FIELDS}
    base.update(kw)
    return base


def test_match_by_reference_then_fallback():
    gt = [_entry(foi_reference_id="FOI-1"), _entry(date_received="2024-03-03",
                                                   request_description="roads")]
    arm_b = [_entry(date_received="2024-03-03", request_description="roads"),
             _entry(foi_reference_id="FOI-1")]
    pairs = match_rows(arm_b, gt)
    # GT row 0 (ref FOI-1) matches arm_b idx 1; GT row 1 matches arm_b idx 0.
    assert (1, 0) in pairs
    assert (0, 1) in pairs


def test_perfect_fidelity():
    row = _entry(foi_reference_id="FOI-1", date_received="2024-01-02",
                 request_description="docs")
    scores = fidelity_scores([dict(row)], [dict(row)])
    assert scores["value_fidelity_violations"] == 0
    assert scores["invented_rows"] == 0
    assert scores["dropped_rows"] == 0
    assert scores["per_field"]["foi_reference_id"]["precision"] == 1.0
    assert scores["per_field"]["foi_reference_id"]["recall"] == 1.0


def test_altered_value_is_violation_and_hurts_precision_recall():
    gt = [_entry(foi_reference_id="FOI-1", request_description="roads budget")]
    arm_b = [_entry(foi_reference_id="FOI-1", request_description="ROADS money")]
    scores = fidelity_scores(arm_b, gt)
    assert scores["value_fidelity_violations"] == 1
    fld = scores["per_field"]["request_description"]
    assert fld["fn"] == 1 and fld["fp"] == 1
    assert fld["precision"] == 0.0 and fld["recall"] == 0.0


def test_invented_and_dropped_rows_counted():
    gt = [_entry(foi_reference_id="FOI-1"), _entry(foi_reference_id="FOI-2")]
    arm_b = [_entry(foi_reference_id="FOI-1"), _entry(foi_reference_id="FOI-9")]
    scores = fidelity_scores(arm_b, gt)
    assert scores["invented_rows"] == 1   # FOI-9 unmatched
    assert scores["dropped_rows"] == 1    # FOI-2 unmatched


def test_whitespace_collapsed_equality():
    gt = [_entry(request_description="a  b\tc")]
    arm_b = [_entry(request_description="a b c")]
    scores = fidelity_scores(arm_b, gt)
    assert scores["value_fidelity_violations"] == 0


cost_aggregate = _compare.cost_aggregate


def test_cost_aggregate_and_extrapolation():
    records = [
        {"file_url": "u1", "tokens": {"prompt": 1000, "completion": 500, "total": 1500},
         "cost_usd": 0.005, "ocr_made": True},
        {"file_url": "u2", "tokens": {"prompt": 3000, "completion": 500, "total": 3500},
         "cost_usd": 0.009, "ocr_made": True},
        {"file_url": "u3", "tokens": None, "cost_usd": None, "ocr_made": False,
         "error": "boom"},  # failure -> excluded from cost
    ]
    agg = cost_aggregate(records)
    assert agg["files_costed"] == 2
    assert agg["total_tokens"]["total"] == 5000
    assert agg["total_cost_usd"] == 0.014
    assert agg["mean_cost_per_file_usd"] == 0.007
    assert agg["full_tail_files"] == _compare.FULL_TAIL_FILES
    assert agg["extrapolated_full_tail_usd"] == round(0.007 * _compare.FULL_TAIL_FILES, 2)


def test_cost_aggregate_empty():
    agg = cost_aggregate([{"file_url": "u", "tokens": None, "cost_usd": None}])
    assert agg["files_costed"] == 0
    assert agg["total_cost_usd"] == 0.0
    assert agg["extrapolated_full_tail_usd"] == 0.0
