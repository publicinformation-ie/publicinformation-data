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
