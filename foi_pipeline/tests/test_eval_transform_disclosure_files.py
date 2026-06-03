from steps.transform_disclosure_files.eval.evaluate import (
    has_null_first_row,
    has_null_column,
    has_newline_split_row,
)


# ── has_null_first_row ──────────────────────────────────────────────────────

def test_null_first_row_empty_rows():
    assert has_null_first_row([]) is False

def test_null_first_row_all_values():
    assert has_null_first_row([["a", "b", "c"], ["x", "y", "z"]]) is False

def test_null_first_row_null_in_first():
    assert has_null_first_row([["a", None, "c"]]) is True

def test_null_first_row_null_only_in_later_row():
    assert has_null_first_row([["a", "b", "c"], ["x", None, "z"]]) is False

def test_null_first_row_all_null():
    assert has_null_first_row([[None, None, None]]) is True


# ── has_null_column ─────────────────────────────────────────────────────────

def test_null_column_empty_rows():
    assert has_null_column([]) is False

def test_null_column_no_nulls():
    assert has_null_column([["a", "b"], ["c", "d"]]) is False

def test_null_column_one_col_always_null():
    assert has_null_column([["a", None], ["b", None]]) is True

def test_null_column_short_row_counts_as_null():
    # Row 1 has no col index 1 — treated as None
    assert has_null_column([["a", "b"], ["c"]]) is True

def test_null_column_mixed_null_not_triggered():
    # col 1 is None in row 0 but not row 1 — no always-null column
    assert has_null_column([["a", None], ["b", "c"]]) is False


# ── has_newline_split_row ───────────────────────────────────────────────────

def test_newline_split_empty_rows():
    assert has_newline_split_row([]) is False

def test_newline_split_no_issue():
    assert has_newline_split_row([["h1", "h2", "h3"], ["a", "b", "c"]]) is False

def test_newline_split_triggers():
    # Row 1 has 1 non-null in a 3-col row
    assert has_newline_split_row([["h1", "h2", "h3"], ["desc", None, None]]) is True

def test_newline_split_only_two_cols_no_trigger():
    # Only 2 columns — minimum is 3
    assert has_newline_split_row([["h1", "h2"], ["desc", None]]) is False

def test_newline_split_header_row_excluded():
    # The single-col row IS the header (index 0) — should not fire
    assert has_newline_split_row([["desc", None, None]]) is False

def test_newline_split_all_null_no_trigger():
    # 0 non-null cells — doesn't match "exactly 1"
    assert has_newline_split_row([["h1", "h2", "h3"], [None, None, None]]) is False

def test_newline_split_in_later_row():
    rows = [["h1", "h2", "h3"], ["a", "b", "c"], ["desc", None, None]]
    assert has_newline_split_row(rows) is True


from steps.transform_disclosure_files.eval.evaluate import (
    run_eval,
    build_quality_by_body,
)


def _item(file_url, public_body_id, name, rows, file_type="pdf"):
    return {
        "file_url": file_url,
        "public_body_id": public_body_id,
        "name": name,
        "file_type": file_type,
        "rows": rows,
    }


CLEAN_ROWS = [["h1", "h2", "h3"], ["a", "b", "c"], ["d", "e", "f"]]
NULL_FIRST_ROWS = [[None, "h2", "h3"], ["a", "b", "c"]]
NULL_COL_ROWS = [["h1", None], ["a", None], ["b", None]]
SPLIT_ROWS = [["h1", "h2", "h3"], ["desc", None, None]]


# ── run_eval ────────────────────────────────────────────────────────────────

def test_run_eval_empty():
    results, issues, qbb = run_eval([], set(), input_hash="a" * 64)
    names = {m.name: m.value for m in results.metrics}
    assert names["clean_extraction_rate"] == 0.0
    assert issues == []
    assert qbb == {}


def test_run_eval_all_clean():
    items = [_item("u1", 1, "Body A", CLEAN_ROWS), _item("u2", 1, "Body A", CLEAN_ROWS)]
    results, issues, _ = run_eval(items, set(), input_hash="a" * 64)
    primary = next(m for m in results.metrics if m.is_primary)
    assert primary.value == 1.0
    assert primary.counts == {"clean": 2, "total": 2}
    assert issues == []


def test_run_eval_mixed():
    items = [
        _item("u1", 1, "Body A", CLEAN_ROWS),
        _item("u2", 1, "Body A", NULL_FIRST_ROWS),
        _item("u3", 2, "Body B", SPLIT_ROWS),
    ]
    results, issues, _ = run_eval(items, set(), input_hash="a" * 64)
    names = {m.name: m.value for m in results.metrics}
    assert names["clean_extraction_rate"] == round(1 / 3, 3)
    assert names["null_first_row_rate"] == round(1 / 3, 3)
    assert names["newline_split_row_rate"] == round(1 / 3, 3)
    assert len(issues) == 2  # null_first_row and newline_split_row each produce one issue


def test_run_eval_null_column():
    items = [_item("u1", 1, "Body A", NULL_COL_ROWS)]
    results, issues, _ = run_eval(items, set(), input_hash="a" * 64)
    names = {m.name: m.value for m in results.metrics}
    assert names["null_column_rate"] == 1.0
    assert any("null_column" in i.description for i in issues)


def test_run_eval_issue_contains_affected_ids():
    items = [_item("http://example.com/file.pdf", 1, "Body A", NULL_FIRST_ROWS)]
    _, issues, _ = run_eval(items, set(), input_hash="a" * 64)
    nfr_issue = next(i for i in issues if "null_first_row" in i.description)
    assert "http://example.com/file.pdf" in nfr_issue.affected_ids


def test_run_eval_process_warning_flagged():
    items = [_item("u1", 1, "Body A", SPLIT_ROWS)]
    _, _, qbb = run_eval(items, {"u1"}, input_hash="a" * 64)
    sample = qbb[1]["flagged_samples"][0]
    assert sample["has_process_warning"] is True


def test_run_eval_process_warning_not_flagged():
    items = [_item("u1", 1, "Body A", SPLIT_ROWS)]
    _, _, qbb = run_eval(items, set(), input_hash="a" * 64)
    sample = qbb[1]["flagged_samples"][0]
    assert sample["has_process_warning"] is False


# ── build_quality_by_body ───────────────────────────────────────────────────

def test_quality_by_body_clean_file():
    items = [_item("u1", 42, "Body X", CLEAN_ROWS)]
    qbb = build_quality_by_body(items, set())
    assert qbb[42]["name"] == "Body X"
    assert qbb[42]["total_pdfs"] == 1
    assert qbb[42]["clean"] == 1
    assert qbb[42]["flagged_samples"] == []


def test_quality_by_body_flagged_file():
    items = [_item("u1", 42, "Body X", SPLIT_ROWS)]
    qbb = build_quality_by_body(items, set())
    entry = qbb[42]
    assert entry["clean"] == 0
    assert entry["newline_split_row"] == 1
    assert len(entry["flagged_samples"]) == 1
    sample = entry["flagged_samples"][0]
    assert sample["file_url"] == "u1"
    assert "newline_split_row" in sample["flags"]
    assert sample["total_rows"] == len(SPLIT_ROWS)
    assert sample["first_rows"] == SPLIT_ROWS[:3]


def test_quality_by_body_flagged_rows_count():
    rows = [["h1", "h2", "h3"], ["desc1", None, None], ["a", "b", "c"], ["desc2", None, None]]
    items = [_item("u1", 1, "Body A", rows)]
    qbb = build_quality_by_body(items, set())
    assert qbb[1]["flagged_samples"][0]["flagged_rows"] == 2


def test_quality_by_body_multiple_bodies():
    items = [
        _item("u1", 1, "Body A", CLEAN_ROWS),
        _item("u2", 2, "Body B", NULL_FIRST_ROWS),
    ]
    qbb = build_quality_by_body(items, set())
    assert 1 in qbb and 2 in qbb
    assert qbb[1]["clean"] == 1
    assert qbb[2]["null_first_row"] == 1
