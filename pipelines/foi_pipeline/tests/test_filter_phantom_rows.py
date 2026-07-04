from steps.filter_phantom_rows.process import _drop_blank_rows, process


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
