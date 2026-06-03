from steps.extract_disclosures_normalize_header.eval import evaluate as nhe


def test_run_eval_null_header_column_rate_after_normalization():
    """After normalization, previously-null header cells should be filled."""
    items = [
        # forward-fill fixes this: header had None at col 1
        {
            "file_url": "a",
            "file_type": "pdf",
            "rows": [["Serial", "Serial", "Date", "Decision"], ["1", "x", "2020", "Granted"]],
            "header_row_idx": 0,
        },
        # still has None (leading None, no prior value to fill from)
        {
            "file_url": "b",
            "file_type": "pdf",
            "rows": [[None, "Date", "Decision"], ["1", "2020", "Granted"]],
            "header_row_idx": 0,
        },
    ]
    results, issues = nhe.run_eval(items, input_hash="a" * 64)
    metric = next(m for m in results.metrics if m.name == "null_header_column_rate")
    assert metric.counts["flagged"] == 1
    assert metric.counts["total"] == 2
    assert metric.value == 0.5


def test_run_eval_empty_items():
    results, issues = nhe.run_eval([], input_hash="a" * 64)
    metric = next(m for m in results.metrics if m.name == "null_header_column_rate")
    assert metric.value == 0.0
    assert issues == []
