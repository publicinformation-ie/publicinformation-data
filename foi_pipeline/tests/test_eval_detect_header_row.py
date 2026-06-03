from pathlib import Path

from eval import utils as eval_utils
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


def test_run_eval_reports_null_header_column_rate():
    """null_header_column_rate counts PDFs where detected header has a None cell."""
    items = [
        # clean header - detected at row 0
        {"file_url": "a", "file_type": "pdf", "rows": [["Ref", "Date", "Decision"], ["1", "2", "3"]]},
        # null in detected header (row 1, skipping title row)
        {"file_url": "b", "file_type": "pdf", "rows": [["title", None, None], ["Ref", None, "Decision"], ["1", "2", "3"]]},
    ]
    labels = []
    results, issues = dhr.run_eval(items, labels, input_hash="a" * 64)
    metric = next(m for m in results.metrics if m.name == "null_header_column_rate")
    assert metric.value == 0.5
    assert metric.counts == {"flagged": 1, "total": 2}
