import json
import pytest
from steps.extract_disclosures_detect_header_row.process import (
    detect_header_row,
    process,
    STEP_NAME,
)


# ── detect_header_row unit tests ──────────────────────────────────────────────

def test_first_row_is_header_when_two_non_null_cells():
    rows = [["Our Reference", "Date Rec'd", "Request Details"], ["16/002", "2016-01-05", "desc"]]
    assert detect_header_row(rows) == 0


def test_skips_all_none_row():
    rows = [
        [None, None, None, None, None],
        ["FOI Reference Number", "Date Received", "Status", "Description", "Decision"],
        ["16/001", "2016-01-01", "Open", "some request", "Granted"],
    ]
    assert detect_header_row(rows) == 1


def test_skips_single_cell_title_row():
    # "January - September 2011" in col 0, rest None — only 1 non-null cell
    rows = [
        ["January - September 2011", None, None, None, None],
        ["FOI Reference", "Date", "Description", "Status", "Decision"],
        ["11/001", "2011-01-15", "some request", "Granted", ""],
    ]
    assert detect_header_row(rows) == 1


def test_skips_multiple_leading_title_rows():
    rows = [
        [None, None, None, None],
        ["Annual Disclosure Log 2013", None, None, None],
        ["Reference No", "Date", "Description", "Decision"],
        ["13/001", "2013-03-01", "request", "Grant"],
    ]
    assert detect_header_row(rows) == 2


def test_falls_back_to_zero_when_no_qualifying_row_found():
    # Pathological file: all rows within look-ahead are sparse
    rows = [
        [None],
        [None, None],
        [None, None, None],
    ]
    assert detect_header_row(rows) == 0


def test_empty_string_cells_not_counted():
    rows = [
        ["", "", "", ""],
        ["FOI Ref", "Date", "Summary", "Decision"],
    ]
    assert detect_header_row(rows) == 1


def test_two_non_null_is_enough():
    # Exactly 2 non-null cells — meets the threshold
    rows = [["Ref", "Description", None, None]]
    assert detect_header_row(rows) == 0


def test_max_look_ahead_respected():
    # Row 0 is sparse, row 6 is good — but max_look_ahead=5 means row 6 never checked
    rows = [[None]] + [[None]] * 5 + [["Ref", "Date", "Description"]]
    assert detect_header_row(rows, max_look_ahead=5) == 0  # fallback


# ── process() integration tests ───────────────────────────────────────────────

def _make_input(results):
    return {"metadata": {"step": "transform_disclosure_files"}, "results": results}


BASE_FILE = {
    "public_body_id": 1001,
    "name": "Dept A",
    "disclosure_page_url": "https://dept-a.ie/disclosures/",
    "file_url": "https://assets.gov.ie/log.xlsx",
    "file_type": "xlsx",
    "sheet_name": "Sheet1",
}


def test_process_pdf_passthrough(tmp_path, make_writer):
    item = {**BASE_FILE, "file_url": "https://assets.gov.ie/log.pdf",
            "file_type": "pdf", "sheet_name": None, "rows": None}
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(_make_input([item]), tmp_path, writer)
    assert len(writer.results) == 1
    r = writer.results[0]
    assert r["rows"] is None
    assert r["header_row_idx"] is None


def test_process_clean_header_row(tmp_path, make_writer):
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002", "2016-01-05", "some request"],
    ]
    item = {**BASE_FILE, "rows": rows}
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(_make_input([item]), tmp_path, writer)
    assert writer.results[0]["header_row_idx"] == 0


def test_process_title_row_skipped(tmp_path, make_writer):
    rows = [
        ["January - September 2011", None, None, None, None],
        ["FOI Reference", "Date", "Description", "Status", "Decision"],
        ["11/001", "2011-01-15", "some request", "Granted", ""],
    ]
    item = {**BASE_FILE, "rows": rows}
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(_make_input([item]), tmp_path, writer)
    assert writer.results[0]["header_row_idx"] == 1


def test_process_all_none_first_row(tmp_path, make_writer):
    rows = [
        [None, None, None, None, None],
        ["FOI Reference Number", "Date Received", "Status", "Description", "Decision"],
        ["16/001", "2016-01-01", "Open", "some request", "Granted"],
    ]
    item = {**BASE_FILE, "rows": rows}
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(_make_input([item]), tmp_path, writer)
    assert writer.results[0]["header_row_idx"] == 1


def test_process_preserves_all_source_fields(tmp_path, make_writer):
    rows = [["Ref", "Description"], ["16/001", "some request"]]
    item = {**BASE_FILE, "rows": rows}
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(_make_input([item]), tmp_path, writer)
    r = writer.results[0]
    assert r["public_body_id"] == 1001
    assert r["name"] == "Dept A"
    assert r["file_url"] == BASE_FILE["file_url"]
    assert r["rows"] == rows


def test_process_no_errors_written_for_clean_input(tmp_path, make_writer):
    rows = [["Ref", "Description"], ["16/001", "request"]]
    item = {**BASE_FILE, "rows": rows}
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(_make_input([item]), tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []


def test_process_skips_already_processed(tmp_path, make_writer):
    from scripts.file_utils import write_json, IncrementalWriter
    existing_result = {
        **BASE_FILE,
        "rows": [["Ref", "Desc"], ["16/001", "request"]],
        "header_row_idx": 0,
    }
    write_json(tmp_path / "output.json", {"metadata": {"step": STEP_NAME}, "results": [existing_result]})
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="file_url", force=False)
    rows_new = [["Ref", "Desc"], ["16/002", "other request"]]
    item = {**BASE_FILE, "rows": rows_new}
    process(_make_input([item]), tmp_path, writer)
    # No new processing — already done
    assert len(writer.results) == 1
    assert writer.results[0]["header_row_idx"] == 0
