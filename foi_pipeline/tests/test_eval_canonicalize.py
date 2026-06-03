from eval import utils as eval_utils
from steps.extract_disclosures_canonicalize.eval import evaluate as canon


def test_header_mapping_accuracy_over_verified_labels():
    # 'Decision' maps to decision_status via column_map synonyms; 'Foobar' maps to None.
    labels = [
        {"raw_header": "Decision", "expected_canonical_field": "decision_status", "verified": "yes"},
        {"raw_header": "Foobar", "expected_canonical_field": "__none__", "verified": "yes"},
        {"raw_header": "Decision", "expected_canonical_field": "decision_status", "verified": "auto"},
    ]
    acc, counts, mism = canon.score_header_mapping(labels)
    assert counts == {"correct": 2, "total": 2}
    assert acc == 1.0
    assert mism == []


def test_field_coverage_population_rates():
    records = [
        {"decision_date": "2019-01-01T00:00:00", "request_description": "x",
         "decision_status": "Granted", "foi_reference_id": "R1"},
        {"decision_date": None, "request_description": "", "decision_status": None,
         "foi_reference_id": "R2"},
    ]
    cov = canon.score_field_coverage(records)
    assert cov["decision_date"] == 0.5
    assert cov["request_description"] == 0.5
    assert cov["foi_reference_id"] == 1.0


def test_run_eval_marks_header_mapping_primary():
    labels = [{"raw_header": "Decision", "expected_canonical_field": "decision_status",
               "verified": "yes"}]
    records = [{"decision_date": "2019-01-01T00:00:00", "request_description": "x",
                "decision_status": "g", "foi_reference_id": "R1", "file_url": "test.pdf"}]
    results, issues = canon.run_eval(labels, records, [], input_hash="a" * 64)
    primary = [m for m in results.metrics if m.is_primary][0]
    assert primary.name == "header_mapping_accuracy"
    assert {m.name for m in results.metrics} >= {"header_mapping_accuracy", "field_coverage"}


def test_run_eval_reports_file_success_rate():
    """file_success_rate = files with ≥1 record / total files."""
    labels = [{"raw_header": "Decision", "expected_canonical_field": "decision_status",
               "verified": "yes"}]
    records = [
        {"file_url": "a.pdf", "foi_reference_id": "1"},
        {"file_url": "a.pdf", "foi_reference_id": "2"},
        {"file_url": "b.pdf", "foi_reference_id": "3"},
    ]
    errors = [
        {"error_type": "InsufficientColumns", "context": {"file_url": "c.pdf"}},
    ]
    results, issues = canon.run_eval(labels, records, errors, input_hash="a" * 64)
    success_m = next(m for m in results.metrics if m.name == "file_success_rate")
    insuff_m = next(m for m in results.metrics if m.name == "insufficient_columns_rate")
    # 2 successful files (a, b), 1 error (c), total = 3
    assert success_m.value == round(2 / 3, 3)
    assert success_m.counts == {"successful": 2, "total": 3}
    assert insuff_m.value == round(1 / 3, 3)
    assert insuff_m.counts == {"failed": 1, "total": 3}


def test_run_eval_file_success_rate_all_succeed():
    labels = [{"raw_header": "Decision", "expected_canonical_field": "decision_status",
               "verified": "yes"}]
    records = [{"file_url": "a.pdf", "foi_reference_id": "1"}]
    errors = []
    results, issues = canon.run_eval(labels, records, errors, input_hash="a" * 64)
    success_m = next(m for m in results.metrics if m.name == "file_success_rate")
    assert success_m.value == 1.0
    assert success_m.counts == {"successful": 1, "total": 1}
