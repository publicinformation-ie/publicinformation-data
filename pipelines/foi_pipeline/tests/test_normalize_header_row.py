import pytest
from steps.extract_disclosures_normalize_header.process import normalize_header_row


# ── forward-fill ──────────────────────────────────────────────────────────────

def test_forward_fill_none_in_header():
    """None cells in the header are filled from the left non-None value."""
    rows = [
        ["Serial", None, "Date", None, "Decision"],
        ["1", "x", "2020-01-01", "y", "Granted"],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert result_rows[0] == ["Serial", "Serial", "Date", "Date", "Decision"]
    assert idx == 0


def test_forward_fill_leaves_leading_none_unfilled():
    """None at the start of the header (no prior value) remains None."""
    rows = [
        [None, "Date", None, "Decision"],
        ["1", "2020-01-01", "y", "Granted"],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert result_rows[0] == [None, "Date", "Date", "Decision"]
    assert idx == 0


def test_forward_fill_skips_non_pdf_style_clean_header():
    """Header with no None cells is returned unchanged."""
    rows = [
        ["Ref", "Date", "Decision"],
        ["1", "2020-01-01", "Granted"],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert result_rows[0] == ["Ref", "Date", "Decision"]
    assert result_rows == rows


# ── continuation-row merge ────────────────────────────────────────────────────

def test_merges_single_continuation_row():
    """A high-null row immediately after the header is merged into it."""
    # Mayo County Council pattern: header split across two rows
    rows = [
        ["Ref. No", None, "Date", None, "Category", "Description"],  # row 0: header
        [None, None, "Received", None, None, None],                   # row 1: continuation (4/6 null)
        ["FOI-001", "02-Apr-25", None, None, "Other", "Some request"],# row 2: data starts
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    # "Date" + " " + "Received" merged into col 2
    assert result_rows[0][2] == "Date Received"
    # Continuation row removed
    assert len(result_rows) == 2
    assert result_rows[1][0] == "FOI-001"
    assert idx == 0


def test_merges_two_continuation_rows():
    """Up to max_continuation_rows rows are merged."""
    rows = [
        ["Ref", None, "Date"],
        [None, None, "of"],
        [None, None, "Request"],
        ["1", "x", "2020"],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert result_rows[0][2] == "Date of Request"
    assert len(result_rows) == 2
    assert result_rows[1][0] == "1"


def test_does_not_merge_data_row_with_mostly_populated_cells():
    """A row with many non-None cells is NOT treated as a continuation."""
    rows = [
        ["Ref", "Date", "Decision"],
        ["FOI-001", "2020-01-01", "Granted"],  # 3/3 non-null — not continuation
        ["FOI-002", "2020-02-01", "Refused"],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert len(result_rows) == 3  # nothing removed
    assert result_rows[0] == ["Ref", "Date", "Decision"]


# ── header_row_idx != 0 ───────────────────────────────────────────────────────

def test_handles_header_not_on_row_zero():
    """Works correctly when header is on row 1 (preamble row above it)."""
    rows = [
        ["FOI Disclosure Log 2024", None, None],  # row 0: preamble
        ["Ref", None, "Decision"],                # row 1: header
        [None, None, "Received"],                 # row 2: continuation
        ["1", "x", "Granted"],                    # row 3: data
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=1)
    assert idx == 1
    assert result_rows[1][1] == "Ref"   # forward-filled
    assert result_rows[1][2] == "Decision Received"  # merged continuation
    assert len(result_rows) == 3   # preamble + header + data


# ── edge cases ────────────────────────────────────────────────────────────────

def test_empty_rows_returns_unchanged():
    result_rows, idx = normalize_header_row([], header_row_idx=0)
    assert result_rows == []
    assert idx == 0


def test_header_idx_out_of_range_returns_unchanged():
    rows = [["Ref", "Date"]]
    result_rows, idx = normalize_header_row(rows, header_row_idx=5)
    assert result_rows == rows
    assert idx == 5


# ── scan-ahead rescue for sparse multi-row PDF headers ────────────────────────

def test_forward_fill_sparse_header_with_good_next_row():
    """When forward-fill produces a header with < 2 canonical columns, the next row should be promoted if it has >= 3."""
    rows = [
        ['Unnamed', None, None, None, None, None],  # idx 0: forward-fill yields only 1 canonical (< 2), should rescue
        ['Number', 'Date Received', 'Description', 'Category', 'Received', 'Decision'],  # idx 1: good (5+ canonical)
        ['001', '01/01/2018', 'Some request', 'Journalist', '05/01/2018', 'Granted'],
    ]
    new_rows, new_idx = normalize_header_row(rows, header_row_idx=0)
    # Should use row 1 (the good row) as the header
    assert new_idx == 1
    assert new_rows[1] == ['Number', 'Date Received', 'Description', 'Category', 'Received', 'Decision']


def test_forward_fill_sparse_header_no_rescue_needed():
    """When forward-fill produces a good header (>= 2 canonical matches), no scan-ahead occurs."""
    rows = [
        ['Request', None, 'Decision', None],  # 'Request' ~ request_description, 'Decision' ~ decision_status
        ['details', 'category', 'made', 'date'],
    ]
    new_rows, new_idx = normalize_header_row(rows, header_row_idx=0)
    # header_row_idx unchanged — original result was fine
    assert new_idx == 0


def test_forward_fill_does_not_rescue_when_next_row_is_data():
    """Scan-ahead should not promote a row where the cells look like data, not headers."""
    rows = [
        ['Our Ref', None, 'Status', None],  # maps 2 columns — no rescue needed
        ['FOI-001', '01/01/2018', 'Granted', 'Journalist'],
    ]
    new_rows, new_idx = normalize_header_row(rows, header_row_idx=0)
    assert new_idx == 0
