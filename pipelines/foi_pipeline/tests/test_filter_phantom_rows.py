from steps.filter_phantom_rows.process import (
    _drop_blank_rows,
    _merge_continuation_rows,
    _prune_null_columns,
    process,
)


def test_drop_blank_rows_removes_all_none_rows():
    rows = [["a", "b"], [None, None], ["c", "d"]]
    kept, dropped = _drop_blank_rows(rows)
    assert kept == [["a", "b"], ["c", "d"]]
    assert dropped == [1]


def test_drop_blank_rows_removes_empty_and_whitespace_rows():
    rows = [["a", "b"], ["", "  "], [None, ""], []]
    kept, dropped = _drop_blank_rows(rows)
    assert kept == [["a", "b"]]
    assert dropped == [1, 2, 3]


def test_drop_blank_rows_keeps_sparse_rows():
    # A row with ANY real value is kept — sparsity alone is never grounds to drop
    rows = [["a", "b"], [None, "only one value"]]
    kept, dropped = _drop_blank_rows(rows)
    assert kept == rows
    assert dropped == []


def test_process_drops_blanks_for_all_file_types(make_writer):
    # xlsx blank rows are the second-largest phantom source; must not be PDF-gated
    writer = make_writer("filter_phantom_rows", key_field="file_url")
    input_data = {"results": [
        {"file_url": "u1", "file_type": "xlsx", "public_body_id": 1, "name": "B",
         "rows": [["h1", "h2"], ["v1", "v2"], [None, None]]},
    ]}
    process(input_data, writer)
    writer.finalize()
    import json
    out = json.loads(writer.output_path.read_text())["results"]
    assert out[0]["rows"] == [["h1", "h2"], ["v1", "v2"]]
    assert out[0]["filter_stats"] == {"blank_rows_dropped": 1}


def test_process_passes_through_rowless_items(make_writer):
    writer = make_writer("filter_phantom_rows", key_field="file_url")
    input_data = {"results": [
        {"file_url": "u2", "file_type": "pdf", "public_body_id": 1, "name": "B",
         "rows": None},
    ]}
    process(input_data, writer)
    writer.finalize()
    import json
    out = json.loads(writer.output_path.read_text())["results"]
    assert out[0]["rows"] is None
    assert "filter_stats" not in out[0]


# ── _merge_continuation_rows ──────────────────────────────────────────────────

def test_merge_continuation_rows_basic():
    rows = [
        ["Ref", "Subject", "Decision"],
        ["FOI-001", "Long subject text that wraps", "Granted"],
        [None, "continuation of subject", None],
        ["FOI-002", "Another request", "Refused"],
    ]
    result, _ = _merge_continuation_rows(rows)
    assert len(result) == 3
    assert result[1] == ["FOI-001", "Long subject text that wraps continuation of subject", "Granted"]
    assert result[2] == ["FOI-002", "Another request", "Refused"]


def test_merge_continuation_rows_consecutive():
    rows = [
        ["Ref", "Subject", "Decision"],
        ["FOI-001", "First part", "Granted"],
        [None, "second part", None],
        [None, "third part", None],
    ]
    result, _ = _merge_continuation_rows(rows)
    assert len(result) == 2
    assert result[1][1] == "First part second part third part"


def test_merge_continuation_rows_no_op_narrow_table():
    # Tables with < 3 columns are not touched (ambiguous whether row is continuation)
    rows = [
        ["Ref", "Decision"],
        ["FOI-001", None],
    ]
    result, _ = _merge_continuation_rows(rows)
    assert result == rows


def test_merge_continuation_rows_non_string_not_merged():
    # Non-string value in continuation position — row is kept as-is
    rows = [
        ["Ref", "Count", "Decision"],
        ["FOI-001", 5, "Granted"],
        [None, 3, None],  # non-string in col 1 — not mergeable
    ]
    result, _ = _merge_continuation_rows(rows)
    assert len(result) == 3


def test_merge_continuation_rows_empty():
    result, _ = _merge_continuation_rows([])
    assert result == []


def test_merge_continuation_rows_single_row():
    rows = [["Ref", "Subject", "Decision"]]
    result, _ = _merge_continuation_rows(rows)
    assert result == rows


def test_merge_continuation_rows_does_not_corrupt_header():
    """Preamble phantom rows immediately after the header must never be merged into it.

    DOT pattern: pdfplumber extracts a boilerplate sentence as a single-cell row
    aligned with the 'Description' column, between the header and the first data row.
    The fix: only merge when out already contains more than the header alone (len(out) > 1).
    """
    rows = [
        ['FOI Reference', 'Category', 'Description', 'Decision', 'Decision Date'],
        # preamble rows — long prose, appear before first real data row
        [None, None, 'Under the FOI Act the Department is obliged to publish this log.', None, None],
        [None, None, 'A disclosure log must be published within 10 working days.', None, None],
        # first real data row
        ['TRA-FOI-2020-0001', 'Business', 'report as delivered by consultants', 'Refused', '17/01/2020'],
        # legitimate continuation of the data row's Description cell
        [None, None, 'additional detail about the report', None, None],
    ]
    result, _ = _merge_continuation_rows(rows)

    # Header must be completely unchanged
    assert result[0] == ['FOI Reference', 'Category', 'Description', 'Decision', 'Decision Date']

    # Preamble row 1 is appended (len(out)==1 prevents it from merging into header).
    # Preamble row 2 then merges into preamble row 1 (len(out)==2 at that point),
    # forming a single orphaned chimera row. The data row's continuation still merges correctly.
    data_row = next(r for r in result if r[0] == 'TRA-FOI-2020-0001')
    assert 'additional detail about the report' in data_row[2]


def test_merge_returns_merge_count():
    rows = [["h1", "h2", "h3"],
            ["a", "long text", "c"],
            [None, "continued", None]]
    out, merged = _merge_continuation_rows(rows)
    assert merged == 1
    assert out == [["h1", "h2", "h3"], ["a", "long text continued", "c"]]


# ── _prune_null_columns ───────────────────────────────────────────────────────

def test_prune_null_columns_basic():
    rows = [
        ["Ref", None, "Decision"],
        ["FOI-001", None, "Granted"],
        ["FOI-002", None, "Refused"],
    ]
    result, _ = _prune_null_columns(rows)
    assert result == [["Ref", "Decision"], ["FOI-001", "Granted"], ["FOI-002", "Refused"]]


def test_prune_null_columns_multiple():
    rows = [
        [None, "Ref", None, "Decision"],
        [None, "FOI-001", None, "Granted"],
    ]
    result, _ = _prune_null_columns(rows)
    assert result == [["Ref", "Decision"], ["FOI-001", "Granted"]]


def test_prune_null_columns_no_op():
    rows = [
        ["Ref", "Subject", "Decision"],
        ["FOI-001", "Request A", "Granted"],
    ]
    result, _ = _prune_null_columns(rows)
    assert result == rows


def test_prune_null_columns_partial_none_kept():
    # Column has None in only some rows — must NOT be dropped
    rows = [
        ["Ref", "Subject", "Decision"],
        ["FOI-001", None, "Granted"],
    ]
    result, _ = _prune_null_columns(rows)
    assert result == rows


def test_prune_null_columns_empty():
    result, _ = _prune_null_columns([])
    assert result == []


def test_prune_returns_pruned_count():
    rows = [["h1", None, "h3"], ["a", None, "c"]]
    out, pruned = _prune_null_columns(rows)
    assert pruned == 1
    assert out == [["h1", "h3"], ["a", "c"]]


# ── structural fixes via process() ───────────────────────────────────────────

def test_process_pdf_merges_continuation_rows(make_writer):
    writer = make_writer("filter_phantom_rows", key_field="file_url")
    input_data = {"results": [
        {"file_url": "u3", "file_type": "pdf", "public_body_id": 1, "name": "B",
         "rows": [
            ["Ref", "Subject", "Decision"],
            ["FOI-001", "Long text", "Granted"],
            [None, "wrapped continuation", None],
            ["FOI-002", "Other", "Refused"],
        ]},
    ]}
    process(input_data, writer)
    writer.finalize()
    import json
    out = json.loads(writer.output_path.read_text())["results"]
    result_rows = out[0]["rows"]
    assert len(result_rows) == 3
    assert result_rows[1][1] == "Long text wrapped continuation"
    assert out[0]["filter_stats"]["fragments_merged"] == 1


def test_process_pdf_prunes_null_columns(make_writer):
    writer = make_writer("filter_phantom_rows", key_field="file_url")
    input_data = {"results": [
        {"file_url": "u4", "file_type": "pdf", "public_body_id": 1, "name": "B",
         "rows": [
            ["Ref", None, "Decision"],
            ["FOI-001", None, "Granted"],
        ]},
    ]}
    process(input_data, writer)
    writer.finalize()
    import json
    out = json.loads(writer.output_path.read_text())["results"]
    result_rows = out[0]["rows"]
    assert all(len(r) == 2 for r in result_rows)
    assert result_rows[0] == ["Ref", "Decision"]
    assert out[0]["filter_stats"]["null_columns_pruned"] == 1


def test_process_xlsx_structural_fixes_not_applied(make_writer):
    # xlsx rows that look like continuations must NOT be merged, and null
    # columns must NOT be pruned — those repairs are PDF-only.
    writer = make_writer("filter_phantom_rows", key_field="file_url")
    input_data = {"results": [
        {"file_url": "https://assets.gov.ie/log.xlsx", "file_type": "xlsx",
         "public_body_id": 1, "name": "B", "sheet_name": "Sheet1",
         "rows": [
            ["Ref", "Subject", "Decision"],
            ["FOI-001", "Request", "Granted"],
            [None, "should stay", None],
        ]},
    ]}
    process(input_data, writer)
    writer.finalize()
    import json
    out = json.loads(writer.output_path.read_text())["results"]
    assert len(out[0]["rows"]) == 3
