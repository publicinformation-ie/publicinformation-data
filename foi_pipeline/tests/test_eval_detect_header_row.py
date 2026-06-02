from pathlib import Path

import eval_utils
from steps.extract_disclosures_detect_header_row.eval import evaluate as dhr


def test_run_eval_scores_exact_match_accuracy():
    items = [
        {"file_url": "a", "rows": [["x"], ["h1", "h2"], ["1", "2"]]},  # detect idx 1
        {"file_url": "b", "rows": [["h1", "h2"], ["1", "2"]]},          # detect idx 0
    ]
    labels = [
        {"file_url": "a", "expected_header_row_index": "1", "verified": "yes"},
        {"file_url": "b", "expected_header_row_index": "0", "verified": "yes"},
    ]
    results, issues = dhr.run_eval(items, labels, input_hash="a" * 64)
    primary = [m for m in results.metrics if m.is_primary][0]
    assert primary.name == "accuracy"
    assert primary.value == 1.0
    assert primary.counts == {"correct": 2, "total": 2}
    assert issues == []


def test_run_eval_emits_issue_on_mismatch():
    items = [{"file_url": "a", "rows": [["h1", "h2"], ["1", "2"]]}]  # detects 0
    labels = [{"file_url": "a", "expected_header_row_index": "1", "verified": "yes"}]
    results, issues = dhr.run_eval(items, labels, input_hash="a" * 64)
    assert results.metrics[0].value == 0.0
    assert len(issues) == 1
    assert issues[0].affected_ids == ["a"]


def test_only_verified_labels_count():
    items = [{"file_url": "a", "rows": [["h1", "h2"]]}]
    labels = [{"file_url": "a", "expected_header_row_index": "0", "verified": "auto"}]
    results, issues = dhr.run_eval(items, labels, input_hash="a" * 64)
    assert results.metrics[0].counts["total"] == 0
