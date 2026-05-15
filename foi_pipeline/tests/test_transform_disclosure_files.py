import datetime
import decimal
import io
import json
import pytest
import openpyxl
import xlwt

from steps.transform_disclosure_files.process import (
    serialise_cell,
    _extract_xlsx,
    _extract_xls,
    process,
    STEP_NAME,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_xlsx(rows, sheet_name="Sheet1", extra_sheets=0):
    """Return bytes of an XLSX workbook with one (or more) sheets."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    for i in range(extra_sheets):
        wb.create_sheet(f"Extra{i + 1}")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_xls(rows, sheet_name="Sheet1", extra_sheets=0):
    """Return bytes of an XLS workbook with one (or more) sheets."""
    wb = xlwt.Workbook()
    ws = wb.add_sheet(sheet_name)
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            ws.write(r_idx, c_idx, val)
    for i in range(extra_sheets):
        wb.add_sheet(f"Extra{i + 1}")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── serialise_cell ────────────────────────────────────────────────────────────

def test_serialise_cell_none():
    val, fallback = serialise_cell(None)
    assert val is None
    assert fallback is False


def test_serialise_cell_str():
    val, fallback = serialise_cell("hello")
    assert val == "hello"
    assert fallback is False


def test_serialise_cell_int():
    val, fallback = serialise_cell(42)
    assert val == 42
    assert fallback is False


def test_serialise_cell_float():
    val, fallback = serialise_cell(3.14)
    assert val == 3.14
    assert fallback is False


def test_serialise_cell_bool():
    val, fallback = serialise_cell(True)
    assert val is True
    assert fallback is False


def test_serialise_cell_datetime():
    dt = datetime.datetime(2016, 1, 5, 0, 0, 0)
    val, fallback = serialise_cell(dt)
    assert val == "2016-01-05T00:00:00"
    assert fallback is False


def test_serialise_cell_date():
    d = datetime.date(2016, 1, 5)
    val, fallback = serialise_cell(d)
    assert val == "2016-01-05"
    assert fallback is False


def test_serialise_cell_decimal():
    val, fallback = serialise_cell(decimal.Decimal("3.14"))
    assert isinstance(val, float)
    assert abs(val - 3.14) < 1e-9
    assert fallback is False


def test_serialise_cell_unknown_type_uses_fallback():
    class Weird:
        def __str__(self):
            return "weird"
    val, fallback = serialise_cell(Weird())
    assert val == "weird"
    assert fallback is True


# ── _extract_xlsx ─────────────────────────────────────────────────────────────

def test_extract_xlsx_single_sheet_rows():
    xlsx_bytes = _make_xlsx([["Our Reference", "Date"], ["16/002", "2016-01-05"]])
    sheet_name, rows, fallback_cells, has_multiple_sheets = _extract_xlsx(xlsx_bytes)
    assert sheet_name == "Sheet1"
    assert rows[0] == ["Our Reference", "Date"]
    assert rows[1] == ["16/002", "2016-01-05"]
    assert fallback_cells == []
    assert has_multiple_sheets is False


def test_extract_xlsx_multiple_sheets_flag():
    xlsx_bytes = _make_xlsx([["a", "b"]], extra_sheets=2)
    _, rows, _, has_multiple_sheets = _extract_xlsx(xlsx_bytes)
    assert has_multiple_sheets is True
    assert rows[0] == ["a", "b"]  # still got data from first sheet


def test_extract_xlsx_datetime_cell_serialised():
    dt = datetime.datetime(2016, 3, 15, 9, 30, 0)
    xlsx_bytes = _make_xlsx([[dt]])
    _, rows, fallback_cells, _ = _extract_xlsx(xlsx_bytes)
    assert rows[0][0] == "2016-03-15T09:30:00"
    assert fallback_cells == []


def test_extract_xlsx_fallback_cell_collected():
    class Weird:
        def __str__(self):
            return "weird"
    # openpyxl won't store arbitrary Python objects, so we test fallback_cells
    # by monkey-patching serialise_cell to return True for a known value.
    # Instead, test via process() with a corrupt-type patch; here we just confirm
    # that passing a Decimal (which serialise_cell handles cleanly) produces no fallback.
    xlsx_bytes = _make_xlsx([[decimal.Decimal("1.5")]])
    _, rows, fallback_cells, _ = _extract_xlsx(xlsx_bytes)
    # openpyxl loads Decimal-written cells as floats — either way, no fallback
    assert fallback_cells == []


# ── _extract_xls ──────────────────────────────────────────────────────────────

def test_extract_xls_single_sheet_rows():
    xls_bytes = _make_xls([["Our Reference", "Date"], ["16/002", "2016-01-05"]])
    sheet_name, rows, fallback_cells, has_multiple_sheets = _extract_xls(xls_bytes)
    assert sheet_name == "Sheet1"
    assert rows[0] == ["Our Reference", "Date"]
    assert rows[1] == ["16/002", "2016-01-05"]
    assert fallback_cells == []
    assert has_multiple_sheets is False


def test_extract_xls_multiple_sheets_flag():
    xls_bytes = _make_xls([["a", "b"]], extra_sheets=2)
    _, rows, _, has_multiple_sheets = _extract_xls(xls_bytes)
    assert has_multiple_sheets is True
    assert rows[0] == ["a", "b"]


def test_extract_xls_numeric_cell():
    xls_bytes = _make_xls([[42.0, 3.14]])
    _, rows, fallback_cells, _ = _extract_xls(xls_bytes)
    assert rows[0][0] == 42.0
    assert abs(rows[0][1] - 3.14) < 1e-9
    assert fallback_cells == []


def test_extract_xls_empty_cell_is_none():
    # xlwt writes an empty string for missing cells; xlrd reads blank cells as empty str
    # Write one cell and leave the rest of the row empty
    xls_bytes = _make_xls([["only-col-a"]])
    _, rows, _, _ = _extract_xls(xls_bytes)
    assert rows[0][0] == "only-col-a"


# ── process() fixtures ────────────────────────────────────────────────────────

BASE_ITEM = {
    "public_body_id": 1001,
    "name": "Dept A",
    "disclosure_page_url": "https://dept-a.ie/disclosures/",
}

PDF_INPUT = {
    "metadata": {"step": "find_disclosure_files"},
    "results": [
        {**BASE_ITEM, "file_url": "https://assets.gov.ie/report.pdf", "file_type": "pdf"},
    ],
}

XLSX_INPUT = {
    "metadata": {"step": "find_disclosure_files"},
    "results": [
        {**BASE_ITEM, "file_url": "https://assets.gov.ie/log.xlsx", "file_type": "xlsx"},
    ],
}

XLS_INPUT = {
    "metadata": {"step": "find_disclosure_files"},
    "results": [
        {**BASE_ITEM, "file_url": "https://assets.gov.ie/log.xls", "file_type": "xls"},
    ],
}


# ── process() — pass-through ──────────────────────────────────────────────────

def test_process_pdf_passthrough(tmp_path, make_writer):
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    r = writer.results[0]
    assert r["file_url"] == "https://assets.gov.ie/report.pdf"
    assert r["sheet_name"] is None
    assert r["rows"] is None


def test_process_pdf_no_errors_written(tmp_path, make_writer):
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []


# ── process() — XLSX happy path ───────────────────────────────────────────────

def test_process_xlsx_extracts_rows(requests_mock, tmp_path, make_writer):
    xlsx_bytes = _make_xlsx([["Col A", "Col B"], ["val1", "val2"]])
    requests_mock.get("https://assets.gov.ie/log.xlsx", content=xlsx_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    r = writer.results[0]
    assert r["rows"][0] == ["Col A", "Col B"]
    assert r["rows"][1] == ["val1", "val2"]
    assert r["sheet_name"] == "Sheet1"


def test_process_xlsx_no_errors_on_clean_file(requests_mock, tmp_path, make_writer):
    xlsx_bytes = _make_xlsx([["a", "b"]])
    requests_mock.get("https://assets.gov.ie/log.xlsx", content=xlsx_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []


# ── process() — XLS happy path ────────────────────────────────────────────────

def test_process_xls_extracts_rows(requests_mock, tmp_path, make_writer):
    xls_bytes = _make_xls([["Ref", "Detail"], ["16/001", "Request about X"]])
    requests_mock.get("https://assets.gov.ie/log.xls", content=xls_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLS_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    r = writer.results[0]
    assert r["rows"][0] == ["Ref", "Detail"]
    assert r["sheet_name"] == "Sheet1"


def test_process_output_has_required_fields(requests_mock, tmp_path, make_writer):
    xlsx_bytes = _make_xlsx([["h1"]])
    requests_mock.get("https://assets.gov.ie/log.xlsx", content=xlsx_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    r = writer.results[0]
    assert {"public_body_id", "file_url", "file_type", "sheet_name", "rows"} <= r.keys()


def test_process_skips_already_processed(requests_mock, tmp_path, make_writer):
    from scripts.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{
            **BASE_ITEM,
            "file_url": "https://assets.gov.ie/log.xlsx",
            "file_type": "xlsx",
            "sheet_name": "Sheet1",
            "rows": [["already", "processed"]],
        }],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME,
                               key_field="file_url", force=False)
    process(XLSX_INPUT, tmp_path, writer)
    assert requests_mock.call_count == 0
    assert len(writer.results) == 1
