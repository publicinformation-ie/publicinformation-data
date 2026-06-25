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


def test_merges_continuation_row_at_exact_50_percent_null_boundary():
    """A row with exactly 50% null cells IS treated as a continuation (Meath 2016 pattern).

    Old threshold was null_fraction <= 0.5 which broke here; new threshold is < 0.5.
    """
    # Exact 50% null (2 null out of 4): should merge under the new < threshold
    rows = [
        ["Ref", None, "Date", None],               # header row
        [None, "Received", None, "Decision"],       # continuation: 2/4 null = 50% — boundary case
        ["1", "2020-01-01", "x", "Granted"],        # data
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert result_rows[0][1] == "Received"          # merged from continuation
    assert result_rows[0][3] == "Decision"          # merged from continuation
    assert len(result_rows) == 2


def test_does_not_merge_row_with_majority_populated_cells():
    """A row with more than 50% populated cells (< 50% null) is NOT a continuation."""
    rows = [
        ["Ref", "Date", "Decision", None],
        ["FOI-001", "2020-01-01", "Granted", None],  # 3/4 non-null = 75% populated → real data
        ["FOI-002", "2020-02-01", "Refused", None],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert len(result_rows) == 3  # nothing removed


# ── header_row_idx != 0 ───────────────────────────────────────────────────────

def test_handles_header_not_on_row_zero():
    """Preamble rows before the header are stripped; header lands at idx 0."""
    rows = [
        ["FOI Disclosure Log 2024", None, None],  # row 0: preamble
        ["Ref", None, "Decision"],                # row 1: header
        [None, None, "Received"],                 # row 2: continuation
        ["1", "x", "Granted"],                    # row 3: data
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=1)
    assert idx == 0
    assert result_rows[0][1] == "Ref"             # forward-filled
    assert result_rows[0][2] == "Decision Received"  # merged continuation
    assert len(result_rows) == 2                  # preamble stripped; header + data


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


# ── targeted fill (Fix 2): fully-populated second header row ──────────────────

def test_targeted_fill_fully_populated_continuation_row():
    """Tipperary July 2021 pattern: a fully-populated row with ≥2 canonical matches is
    detected as a missed continuation row and its value is used to fill None at position 0."""
    rows = [
        [None, 'Date', 'Requester', 'Requester', 'Date decision', 'Date decision'],
        ['FOI File No', 'Received', 'Category', 'Brief Description of Request', 'issued', 'Decision'],
        ['TCC/37/20', None, 'Member of public', 'Some accommodation request', None, '02/07/2021 Refused'],
    ]
    result, idx = normalize_header_row(rows, header_row_idx=0)
    assert result[0][0] == 'FOI File No'       # None at position 0 was filled
    assert idx == 0
    assert len(result) == 2                     # continuation row removed from data
    assert result[1][0] == 'TCC/37/20'         # first actual data row


def test_targeted_fill_does_not_merge_data_row_without_canonical_matches():
    """BIM pattern: a data row with 0 canonical matches is NOT treated as a continuation,
    so the structural None at position 0 is left in place."""
    rows = [
        [None, 'Date of Request', 'Request Type', 'Description', 'Decision', 'Date of Response'],
        [None, '11 January 2017', 'Business/Interest Groups', 'Some request text', 'Granted', '01 March 2017'],
    ]
    result, idx = normalize_header_row(rows, header_row_idx=0)
    assert result[0][0] is None    # structural blank at position 0 — not filled
    assert len(result) == 2        # data row NOT removed


def test_targeted_fill_does_not_touch_non_none_header_positions():
    """Targeted fill only writes to positions that are currently None after forward-fill;
    non-None header cells are never overwritten with values from the candidate row.
    Note: forward-fill already handles trailing/mid Nones; targeted fill only reaches
    leading Nones (before any non-None value) that forward-fill cannot propagate into."""
    rows = [
        [None, 'Date Received', 'Decision', 'Description'],
        ['Ref No', 'Date', 'Outcome', 'Summary'],   # candidate: ≥2 canonical matches
        ['001', '2020-01-01', 'Granted', 'Some request'],
    ]
    result, idx = normalize_header_row(rows, header_row_idx=0)
    # Position 0 (leading None) is filled from the candidate row
    assert result[0][0] == 'Ref No'
    # Non-None positions are NOT overwritten by the candidate row's values
    assert result[0][1] == 'Date Received'
    assert result[0][2] == 'Decision'
    assert result[0][3] == 'Description'
    assert len(result) == 2   # candidate row consumed



# ── Meath 2018/2019: 6-row continuation depth ─────────────────────────────────

def test_merges_up_to_six_continuation_rows():
    """Meath 2018/2019 pattern: 6 sparse continuation rows must all be merged.

    The old limit of 3 left rows 4-6 (here indices 4-6) in the data as phantom
    header fragments.  After raising _MAX_CONTINUATION_ROWS to 6, all 6 are
    consumed and the assembled header matches the Meath column names that Fix 3
    will add to column_map.py.
    """
    rows = [
        ['Number', 'Date of Receipt', None, None, None, None],                      # header
        [None, None, 'Category of', None, 'the Decision', 'Summary of'],             # cont 1
        ['Assigned by', 'of Request in', None, 'Summary of the Info', None, None],   # cont 2
        [None, None, 'Applicant', None, 'Issued to the', 'Decision'],                # cont 3
        ['the', 'Department', None, None, None, None],                               # cont 4
        [None, None, None, None, 'Applicant', None],                                 # cont 5
        ['Department', None, None, None, None, None],                                # cont 6
        ['FOI 77/18', '10/07/2018', 'Individual', 'sign erected', '07/08/2018', 'Section'],  # data
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    assert result_rows[0][0] == 'Number Assigned by the Department'
    assert result_rows[0][1] == 'Date of Receipt of Request in Department'
    assert result_rows[0][2] == 'Category of Applicant'
    assert result_rows[0][4] == 'the Decision Issued to the Applicant'
    assert len(result_rows) == 2   # all 6 continuation rows consumed
    assert result_rows[1][0] == 'FOI 77/18'
    assert idx == 0


# ── Meath 2016/2017: dense continuation rows with canonical hits ─────────────────

def test_merges_dense_continuation_rows_with_canonical_column_hits():
    """Meath 2016/2017 pattern: dense rows (>50% non-null) that contain ≥2 canonical
    column labels are still consumed as continuations, not treated as data.

    Without the fix the loop breaks at cont row 2 ('Assigned by', 'Receipt of',
    'Category of', None, 'Decision', 'Summary of') — 5/6 non-null = 17% null,
    which is below _CONTINUATION_NULL_THRESHOLD=0.5.  With the fix, that row's
    _count_canonical_columns == 2 ('Category of'→requester_type, 'Decision'→
    decision_status) so merging continues.
    """
    rows = [
        ['Reference', None, None, None, 'Date When', None],              # header
        ['Number', 'Date of', None, None, 'the', None],                  # cont 1 sparse
        ['Assigned by', 'Receipt of', 'Category of', None, 'Decision', 'Summary of'],  # cont 2 DENSE but canonical
        [None, None, None, 'Summary of the Info/Records', None, None],   # cont 3 sparse
        ['the', 'Request in', 'Applicant', None, 'Issued to', 'Decision'],  # cont 4 DENSE but canonical
        ['Department', 'Department', None, None, 'the Applicant', None], # cont 5 sparse
        ['FOI 01/16', '09/01/2016', 'Individual', 'some request', '12/01/2016', 'Part Granted'],  # data
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0, max_continuation_rows=6)
    # All 5 continuation rows consumed — first non-header row is real data
    assert result_rows[1][0] == 'FOI 01/16'
    assert len(result_rows) == 2
    assert idx == 0
    # Spot-check merged header cells
    assert result_rows[0][0] == 'Reference Number Assigned by the Department'
    assert result_rows[0][1] == 'Date of Receipt of Request in Department'


def test_dense_row_without_canonical_hits_still_breaks_loop():
    """A dense row with 0 canonical column hits is real data and MUST break the loop.

    This verifies Fix 2 does not over-merge: a normal data row (FOI ref, date,
    category value) has no canonical label hits, so the null-fraction check alone
    breaks the loop correctly.
    """
    rows = [
        ['Ref', None, 'Date', None, 'Decision', None],        # header (2 canonical)
        [None, None, 'Received', None, None, None],            # cont 1 sparse — merged
        ['FOI-001', '2020-01-01', 'Individual', 'request text', 'Granted', None],  # dense data
        ['FOI-002', '2020-01-02', 'Business', 'another request', 'Refused', None],
    ]
    result_rows, idx = normalize_header_row(rows, header_row_idx=0)
    # Data row not consumed — 3 rows remain after stripping 1 continuation
    assert len(result_rows) == 3
    assert result_rows[1][0] == 'FOI-001'
