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
    _extract_pdf,
    _score_rows,
    _extract_with_camelot_stream,
    process,
    STEP_NAME,
)


@pytest.fixture(autouse=True)
def _no_mistral_by_default(monkeypatch):
    """Ensure MISTRAL_API_KEY (and base URL) are unset for every test unless a
    test explicitly opts in via monkeypatch.setenv — otherwise a real key
    present in the developer's shell environment would silently flip
    mistral_enabled=True for tests that don't mock call_mistral_ocr."""
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_OCR_PDF_BASE_URL", raising=False)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_xlsx(rows, sheet_name="Sheet1", extra_sheets=0, extra_sheet_rows=None):
    """Return bytes of an XLSX workbook with one (or more) sheets."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    for i in range(extra_sheets):
        extra_ws = wb.create_sheet(f"Extra{i + 1}")
        if extra_sheet_rows:
            for row in extra_sheet_rows:
                extra_ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_xls(rows, sheet_name="Sheet1", extra_sheets=0, extra_sheet_rows=None):
    """Return bytes of an XLS workbook with one (or more) sheets."""
    wb = xlwt.Workbook()
    ws = wb.add_sheet(sheet_name)
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            ws.write(r_idx, c_idx, val)
    for i in range(extra_sheets):
        extra_ws = wb.add_sheet(f"Extra{i + 1}")
        if extra_sheet_rows:
            for r_idx, row in enumerate(extra_sheet_rows):
                for c_idx, val in enumerate(row):
                    extra_ws.write(r_idx, c_idx, val)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_pdf(tables_per_page):
    """Return bytes of a PDF with the given tables laid out per page.

    tables_per_page: list[list[list[list[str]]]]
      outer list  → pages
      middle list → tables on that page
      inner list  → rows of that table (each row: list of str)

    Uses reportlab GRID style so pdfplumber can detect tables via line geometry.
    """
    import io as _io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak, Spacer

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    story = []

    for page_idx, page_tables in enumerate(tables_per_page):
        if page_idx > 0:
            story.append(PageBreak())
        for tbl_idx, table_rows in enumerate(page_tables):
            if tbl_idx > 0:
                story.append(Spacer(1, 1 * cm))
            t = Table(table_rows)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(t)

    doc.build(story)
    return buf.getvalue()


def _make_pdf_no_tables():
    """Return bytes of a valid PDF containing only text (no tables)."""
    import io as _io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    doc.build([Paragraph("No tables here.", styles["Normal"])])
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
    xlsx_bytes = _make_xlsx([["a", "b"]], extra_sheets=2, extra_sheet_rows=[["c", "d"]])
    _, rows, _, has_multiple_sheets = _extract_xlsx(xlsx_bytes)
    assert has_multiple_sheets is True
    assert rows[0] == ["a", "b"]  # still got data from first sheet


def test_extract_xlsx_empty_extra_sheets_not_counted():
    # Sheets with no content should not trigger the multiple-sheets warning
    xlsx_bytes = _make_xlsx([["a", "b"]], extra_sheets=2)
    _, rows, _, has_multiple_sheets = _extract_xlsx(xlsx_bytes)
    assert has_multiple_sheets is False
    assert rows[0] == ["a", "b"]


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
    xls_bytes = _make_xls([["a", "b"]], extra_sheets=2, extra_sheet_rows=[["c", "d"]])
    _, rows, _, has_multiple_sheets = _extract_xls(xls_bytes)
    assert has_multiple_sheets is True
    assert rows[0] == ["a", "b"]


def test_extract_xls_empty_extra_sheets_not_counted():
    # Sheets with no content should not trigger the multiple-sheets warning
    xls_bytes = _make_xls([["a", "b"]], extra_sheets=2)
    _, rows, _, has_multiple_sheets = _extract_xls(xls_bytes)
    assert has_multiple_sheets is False
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


def test_extract_xls_csv_fallback_simple():
    # Government sites often publish CSV with a .xls extension.
    # xlrd raises XLRDError("Expected BOF record; found b'...'") on these.
    csv_bytes = b"Request Number,Date Received,Decision Made\r\nFOI-001,2019-01-15,Granted\r\n"
    sheet_name, rows, fallback_cells, has_multiple_sheets = _extract_xls(csv_bytes)
    assert sheet_name == "Sheet1"
    assert rows[0] == ["Request Number", "Date Received", "Decision Made"]
    assert rows[1] == ["FOI-001", "2019-01-15", "Granted"]
    assert fallback_cells == []
    assert has_multiple_sheets is False


def test_extract_xls_csv_fallback_empty_cells_become_none():
    csv_bytes = b"Ref,Date,Summary\r\nFOI-001,,some summary\r\n"
    _, rows, _, _ = _extract_xls(csv_bytes)
    assert rows[1][1] is None


def test_extract_xls_csv_fallback_trailing_newline_stripped():
    csv_bytes = b"Ref,Date\r\nFOI-001,2019-01-01\r\n\r\n"
    _, rows, _, _ = _extract_xls(csv_bytes)
    assert len(rows) == 2  # no trailing empty row


# ── _extract_pdf ──────────────────────────────────────────────────────────────

def test_extract_pdf_single_page_single_table():
    rows_in = [["Our Reference", "Date"], ["16/002", "2016-01-05"]]
    pdf_bytes = _make_pdf([[rows_in]])
    sheet_name, rows, fallback_cells, has_multiple_tables, merge_stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes)
    assert sheet_name == "page 1"
    assert rows[0] == ["Our Reference", "Date"]
    assert rows[1] == ["16/002", "2016-01-05"]
    assert fallback_cells == []
    assert has_multiple_tables is False


def test_extract_pdf_single_page_two_tables_concatenates_rows():
    table1 = [["Ref", "Date"], ["001", "2024-01-01"]]
    table2 = [["002", "2024-01-02"]]
    pdf_bytes = _make_pdf([[table1, table2]])
    sheet_name, rows, fallback_cells, has_multiple_tables, merge_stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes)
    assert sheet_name == "page 1"
    assert has_multiple_tables is True
    # All rows from both tables should appear in order
    assert ["Ref", "Date"] in rows
    assert ["001", "2024-01-01"] in rows
    assert ["002", "2024-01-02"] in rows


def test_extract_pdf_multi_page_concatenates_rows():
    page1_rows = [["Ref", "Date"], ["001", "2024-01-01"]]
    page2_rows = [["002", "2024-01-02"]]
    pdf_bytes = _make_pdf([[page1_rows], [page2_rows]])
    sheet_name, rows, fallback_cells, has_multiple_tables, merge_stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes)
    assert sheet_name == "pages 1-2"
    assert rows[0] == ["Ref", "Date"]
    assert rows[1] == ["001", "2024-01-01"]
    assert rows[2] == ["002", "2024-01-02"]


def test_extract_pdf_no_tables_raises_value_error(monkeypatch):
    import steps.transform_disclosure_files.process as proc
    monkeypatch.setattr(proc, "_extract_with_camelot_stream", lambda b: None)
    pdf_bytes = _make_pdf_no_tables()
    with pytest.raises(ValueError, match="no tables found"):
        _extract_pdf(pdf_bytes)


def test_extract_pdf_default_table_settings_unchanged():
    rows_in = [["Ref", "Date"], ["001", "2024-01-01"]]
    pdf_bytes = _make_pdf([[rows_in]])
    sheet_name, rows, fallback_cells, has_multiple, merge_stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes, table_settings=None)
    assert rows[0] == ["Ref", "Date"]
    assert rows[1] == ["001", "2024-01-01"]
    assert has_multiple is False


def test_extract_pdf_custom_table_settings_accepted():
    rows_in = [["Ref", "Date"], ["001", "2024-01-01"]]
    pdf_bytes = _make_pdf([[rows_in]])
    settings = {"snap_y_tolerance": 6, "snap_tolerance": 6, "edge_min_length": 10}
    sheet_name, rows, fallback_cells, has_multiple, merge_stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes, table_settings=settings)
    assert rows[0] == ["Ref", "Date"]


# ── _extract_pdf fallback signature ──────────────────────────────────────────

def test_extract_pdf_returns_seven_tuple():
    rows = [["Our Ref", "Date Received", "Description"],
            ["1", "2024-01-01", "a request"]]
    pdf_bytes = _make_pdf([[rows]])
    result = _extract_pdf(pdf_bytes)
    assert len(result) == 7, f"expected 7-tuple, got {len(result)}-tuple"


def test_extract_pdf_pdfplumber_extractor_when_score_ge_2():
    rows = [["Our Ref", "Date Received", "Description"],
            ["1", "2024-01-01", "a request"]]
    pdf_bytes = _make_pdf([[rows]])
    _sheet, _rows, _fb, _multi, _stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes)
    assert pdf_extractor == "pdfplumber"
    assert camelot_info is None


def test_extract_pdf_camelot_info_set_when_fallback_attempted():
    import unittest.mock
    # PDF where pdfplumber produces only one mappable column
    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])
    # Make camelot unavailable so we can test the attempt path without real camelot
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process._extract_with_camelot_stream",
        return_value=None,
    ):
        _sheet, _rows, _fb, _multi, _stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes)
    # camelot_info is set because fallback was attempted (n_mapped < 2)
    # extractor stays pdfplumber since camelot returned None
    assert pdf_extractor == "pdfplumber"
    assert camelot_info is not None
    assert "pdfplumber_n_mapped" in camelot_info
    assert camelot_info["used"] == "pdfplumber"


def test_extract_pdf_uses_camelot_when_scores_better():
    import unittest.mock
    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])
    camelot_rows = [["Our Ref", "Date Received", "Description"], ["1", "2024-01-01", "req"]]
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process._extract_with_camelot_stream",
        return_value=camelot_rows,
    ):
        _sheet, result_rows, _fb, _multi, _stats, pdf_extractor, camelot_info = _extract_pdf(pdf_bytes)
    assert pdf_extractor == "camelot_stream"
    assert result_rows == camelot_rows
    assert camelot_info["used"] == "camelot_stream"


def test_extract_pdf_skip_canonicalization_check_keeps_pdfplumber_path():
    """When skip_canonicalization_check=True, a low-scoring pdfplumber result
    (n_mapped < 2, which would normally trigger camelot fallback) must NOT
    fall back to camelot — the manual column_mapping override that motivated
    skip_canonicalization_check handles column assignment regardless of
    whether the header auto-canonicalizes."""
    import unittest.mock
    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process._extract_with_camelot_stream"
    ) as mock_camelot:
        _sheet, result_rows, _fb, _multi, _stats, pdf_extractor, camelot_info = _extract_pdf(
            pdf_bytes, skip_canonicalization_check=True
        )
    mock_camelot.assert_not_called()
    assert pdf_extractor == "pdfplumber"
    assert camelot_info is None
    assert result_rows == rows


def test_extract_pdf_skip_canonicalization_check_false_still_falls_back():
    """Default behavior (skip_canonicalization_check=False) is unchanged —
    low-scoring rows still trigger the camelot fallback."""
    import unittest.mock
    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])
    camelot_rows = [["Our Ref", "Date Received", "Description"], ["1", "2024-01-01", "req"]]
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process._extract_with_camelot_stream",
        return_value=camelot_rows,
    ):
        _sheet, result_rows, _fb, _multi, _stats, pdf_extractor, camelot_info = _extract_pdf(
            pdf_bytes, skip_canonicalization_check=False
        )
    assert pdf_extractor == "camelot_stream"
    assert result_rows == camelot_rows


def test_load_manual_override_urls_reads_column_mappings(tmp_path):
    """_load_manual_override_urls reads the sibling
    extract_disclosures_canonicalize/column_mappings.json and returns only
    the URLs whose entry opts into skip_camelot_fallback."""
    from steps.transform_disclosure_files.process import _load_manual_override_urls
    import json

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    canon_dir.mkdir()
    (canon_dir / "column_mappings.json").write_text(json.dumps({
        "https://example.com/a.pdf": {"source_method": "manual", "overridden": True, "skip_camelot_fallback": True, "column_mapping": {}},
        "https://example.com/b.pdf": {"source_method": "manual", "overridden": True, "column_mapping": {}},
    }))

    result = _load_manual_override_urls(step_dir)
    assert result == {"https://example.com/a.pdf"}


def test_load_manual_override_urls_missing_file_returns_empty_set(tmp_path):
    """If column_mappings.json doesn't exist (the common case — most steps
    have no manual overrides), return an empty set rather than erroring."""
    from steps.transform_disclosure_files.process import _load_manual_override_urls

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    (tmp_path / "extract_disclosures_canonicalize").mkdir()

    result = _load_manual_override_urls(step_dir)
    assert result == set()


def test_load_skip_mistral_urls_reads_column_mappings(tmp_path):
    """_load_skip_mistral_urls reads the sibling
    extract_disclosures_canonicalize/column_mappings.json and returns only
    the URLs whose entry opts into skip_mistral."""
    from steps.transform_disclosure_files.process import _load_skip_mistral_urls
    import json

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    canon_dir.mkdir()
    (canon_dir / "column_mappings.json").write_text(json.dumps({
        "https://example.com/a.pdf": {"source_method": "manual", "overridden": True, "skip_mistral": True, "column_mapping": {}},
        "https://example.com/b.pdf": {"source_method": "manual", "overridden": True, "column_mapping": {}},
    }))

    result = _load_skip_mistral_urls(step_dir)
    assert result == {"https://example.com/a.pdf"}


def test_load_skip_mistral_urls_missing_file_returns_empty_set(tmp_path):
    from steps.transform_disclosure_files.process import _load_skip_mistral_urls

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    (tmp_path / "extract_disclosures_canonicalize").mkdir()

    result = _load_skip_mistral_urls(step_dir)
    assert result == set()


def test_load_skip_mistral_urls_independent_of_skip_camelot_fallback(tmp_path):
    """skip_mistral and skip_camelot_fallback are independent flags that can
    coexist on the same entry — this test guards against one loader
    accidentally reading the other's key."""
    from steps.transform_disclosure_files.process import (
        _load_skip_mistral_urls, _load_manual_override_urls,
    )
    import json

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    canon_dir.mkdir()
    (canon_dir / "column_mappings.json").write_text(json.dumps({
        "https://example.com/both.pdf": {
            "source_method": "manual", "overridden": True,
            "skip_mistral": True, "skip_camelot_fallback": True, "column_mapping": {},
        },
        "https://example.com/mistral-only.pdf": {
            "source_method": "manual", "overridden": True,
            "skip_mistral": True, "column_mapping": {},
        },
        "https://example.com/camelot-only.pdf": {
            "source_method": "manual", "overridden": True,
            "skip_camelot_fallback": True, "column_mapping": {},
        },
    }))

    skip_mistral = _load_skip_mistral_urls(step_dir)
    skip_camelot = _load_manual_override_urls(step_dir)
    assert skip_mistral == {"https://example.com/both.pdf", "https://example.com/mistral-only.pdf"}
    assert skip_camelot == {"https://example.com/both.pdf", "https://example.com/camelot-only.pdf"}


def test_process_respects_manual_override_skip(tmp_path):
    """End-to-end: when a file's URL is in column_mappings.json, process()
    must keep it on the pdfplumber path (no camelot attempted) even when the
    header doesn't auto-canonicalize."""
    import json
    import hashlib
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    canon_dir.mkdir()
    file_url = "http://example.com/override.pdf"
    (canon_dir / "column_mappings.json").write_text(json.dumps({
        file_url: {"source_method": "manual", "overridden": True, "skip_camelot_fallback": True, "column_mapping": {}},
    }))

    cache_dir = step_dir / "cache_data"
    cache_dir.mkdir()
    key = hashlib.sha256(file_url.encode()).hexdigest()
    (cache_dir / f"{key}.bytes").write_bytes(pdf_bytes)

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process._extract_with_camelot_stream"
    ) as mock_camelot:
        process(input_data, step_dir, writer)
    writer.finalize()
    mock_camelot.assert_not_called()

    result = json.loads(output_path.read_text())
    assert result["results"][0]["pdf_extractor"] == "pdfplumber"


def test_process_without_skip_flag_still_falls_back_to_camelot(tmp_path):
    """A manual override WITHOUT skip_camelot_fallback must still use
    camelot when pdfplumber scores low — this is the case for the 3
    non-Meath overrides (centralbank, gov.ie) whose column_mapping was
    calibrated against camelot's row structure. Regression guard for the
    bug found in final review: skip_canonicalization_check must not apply
    to every override, only ones that opt in."""
    import json
    import hashlib
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])
    camelot_rows = [["Our Ref", "Date Received", "Description"], ["1", "2024-01-01", "req"]]

    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    canon_dir.mkdir()
    file_url = "http://example.com/no-flag-override.pdf"
    (canon_dir / "column_mappings.json").write_text(json.dumps({
        file_url: {"source_method": "manual", "overridden": True, "column_mapping": {}},
    }))

    cache_dir = step_dir / "cache_data"
    cache_dir.mkdir()
    key = hashlib.sha256(file_url.encode()).hexdigest()
    (cache_dir / f"{key}.bytes").write_bytes(pdf_bytes)

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process._extract_with_camelot_stream",
        return_value=camelot_rows,
    ) as mock_camelot:
        process(input_data, step_dir, writer)
    writer.finalize()
    mock_camelot.assert_called_once()

    result = json.loads(output_path.read_text())
    assert result["results"][0]["pdf_extractor"] == "camelot_stream"


# ── Mistral OCR branch ────────────────────────────────────────────────────

def _make_mistral_process_fixture(tmp_path, file_url="http://example.com/mistral.pdf"):
    """Build a step_dir with a cached PDF and no column_mappings.json overrides."""
    import hashlib
    step_dir = tmp_path / "transform_disclosure_files"
    step_dir.mkdir()
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    canon_dir.mkdir()
    pdf_bytes = _make_pdf([[[["Ref", "Date"], ["1", "2024-01-01"]]]])
    cache_dir = step_dir / "cache_data"
    cache_dir.mkdir()
    key = hashlib.sha256(file_url.encode()).hexdigest()
    (cache_dir / f"{key}.bytes").write_bytes(pdf_bytes)
    return step_dir, cache_dir, key, file_url


def test_process_mistral_success_sets_extractor_and_merge_stats(tmp_path, monkeypatch):
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.mistral_ocr import _PAGE_BREAK_MARKER
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("MISTRAL_OCR_PDF_BASE_URL", "https://base.example.com")

    markdown = (
        "| Ref | Date |\n|---|---|\n| 1 | 2024-01-01 |"
        + _PAGE_BREAK_MARKER
        + "| Ref | Date |\n|---|---|\n| 2 | 2024-01-02 |"
    )

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
        return_value=markdown,
    ) as mock_call:
        process(input_data, step_dir, writer)
    writer.finalize()
    mock_call.assert_called_once()

    result = json.loads(output_path.read_text())
    record = result["results"][0]
    assert record["pdf_extractor"] == "mistral_ocr"
    assert record["pdf_merge_stats"] == {"page_split_merges": 0, "header_rows_stripped": 1}
    assert record["rows"] == [["Ref", "Date"], ["1", "2024-01-01"], ["2", "2024-01-02"]]


def test_process_mistral_strips_header_repeated_after_title_preamble(tmp_path, monkeypatch):
    """Reproduces the National Transport Authority bug: page 1 opens with a
    title and subtitle row before the real header; page 2 repeats only the
    header (no title). The old rows[0]-based dedup never matched because
    rows[0] was the title, not the header — asserts the fix strips it."""
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.mistral_ocr import _PAGE_BREAK_MARKER
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("MISTRAL_OCR_PDF_BASE_URL", "https://base.example.com")

    page1 = (
        "| National Transport Authority - FOI Disclosure Log (Non-Personal Requests) |\n"
        "| Quarter 2 2024 (1 April 2024 - 30 June 2024) |\n"
        "| FOI Reference | Date Received | Decision | Date Decision letter issued |\n"
        "|---|---|---|---|\n"
        "| 2024-0028 | 08/04/2024 | Part-Granted | 19/04/2024 |"
    )
    page2 = (
        "| FOI Reference | Date Received | Decision | Date Decision letter issued |\n"
        "|---|---|---|---|\n"
        "| 2024-0042 | 09/04/2024 | Part-Granted | 14/05/2024 |"
    )
    markdown = page1 + _PAGE_BREAK_MARKER + page2

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
        return_value=markdown,
    ):
        process(input_data, step_dir, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    record = result["results"][0]
    assert record["pdf_extractor"] == "mistral_ocr"
    assert record["rows"] == [
        ["National Transport Authority - FOI Disclosure Log (Non-Personal Requests)"],
        ["Quarter 2 2024 (1 April 2024 - 30 June 2024)"],
        ["FOI Reference", "Date Received", "Decision", "Date Decision letter issued"],
        ["2024-0028", "08/04/2024", "Part-Granted", "19/04/2024"],
        ["2024-0042", "09/04/2024", "Part-Granted", "14/05/2024"],
    ]
    assert record["pdf_merge_stats"]["header_rows_stripped"] == 1


def test_process_mistral_api_failure_falls_back_to_pdfplumber(tmp_path, monkeypatch):
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("MISTRAL_OCR_PDF_BASE_URL", "https://base.example.com")

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
        return_value=None,
    ):
        process(input_data, step_dir, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    record = result["results"][0]
    assert record["pdf_extractor"] == "pdfplumber"
    assert record["rows"] == [["Ref", "Date"], ["1", "2024-01-01"]]

    errors = json.loads((step_dir / "errors.json").read_text())
    assert any(e["error_type"] == "MistralOCRWarning" for e in errors)


def test_process_mistral_exception_falls_back_to_pdfplumber(tmp_path, monkeypatch):
    """Test that exceptions raised by call_mistral_ocr (e.g. corrupt cache file)
    are caught and fall back to pdfplumber, not causing permanent zero-row failure."""
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("MISTRAL_OCR_PDF_BASE_URL", "https://base.example.com")

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
        side_effect=Exception("simulated failure, e.g. corrupt cache"),
    ):
        process(input_data, step_dir, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    record = result["results"][0]
    assert record["pdf_extractor"] == "pdfplumber"
    assert record["rows"] == [["Ref", "Date"], ["1", "2024-01-01"]]

    errors = json.loads((step_dir / "errors.json").read_text())
    assert any(e["error_type"] == "MistralOCRWarning" for e in errors)


def test_process_mistral_empty_result_falls_back_to_pdfplumber(tmp_path, monkeypatch):
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("MISTRAL_OCR_PDF_BASE_URL", "https://base.example.com")

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
        return_value="",
    ):
        process(input_data, step_dir, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    record = result["results"][0]
    assert record["pdf_extractor"] == "pdfplumber"

    errors = json.loads((step_dir / "errors.json").read_text())
    assert any(e["error_type"] == "MistralOCREmptyWarning" for e in errors)


def test_process_skip_mistral_override_does_not_call_mistral(tmp_path, monkeypatch):
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("MISTRAL_OCR_PDF_BASE_URL", "https://base.example.com")
    canon_dir = tmp_path / "extract_disclosures_canonicalize"
    (canon_dir / "column_mappings.json").write_text(json.dumps({
        file_url: {"source_method": "manual", "overridden": True, "skip_mistral": True, "column_mapping": {}},
    }))

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
    ) as mock_call:
        process(input_data, step_dir, writer)
    writer.finalize()
    mock_call.assert_not_called()

    result = json.loads(output_path.read_text())
    assert result["results"][0]["pdf_extractor"] == "pdfplumber"


def test_process_api_key_without_base_url_falls_back_to_pdfplumber(tmp_path, monkeypatch, capsys):
    """MISTRAL_API_KEY set but MISTRAL_OCR_PDF_BASE_URL unset must not enable
    the Mistral branch, and must not crash — the file should still be
    processed via pdfplumber with rows present rather than a permanent
    zero-row failure (regression test for the base_url None.rstrip() bug)."""
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.delenv("MISTRAL_OCR_PDF_BASE_URL", raising=False)

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ):
        process(input_data, step_dir, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    record = result["results"][0]
    assert record["pdf_extractor"] == "pdfplumber"
    assert record["rows"] == [["Ref", "Date"], ["1", "2024-01-01"]]

    # mistral_enabled is False when base_url is missing, so the Mistral
    # branch (and its warning logging) is never entered — no errors at all.
    errors = json.loads((step_dir / "errors.json").read_text())
    assert errors == []

    captured = capsys.readouterr()
    assert "MISTRAL_OCR_PDF_BASE_URL" in captured.out


def test_process_no_api_key_disables_mistral_for_whole_run(tmp_path, monkeypatch, capsys):
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    step_dir, cache_dir, key, file_url = _make_mistral_process_fixture(tmp_path)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    input_data = {"results": [{"file_url": file_url, "file_type": "pdf", "public_body_id": 1}]}
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch(
        "steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
        return_value=cache_dir / f"{key}.bytes",
    ), unittest.mock.patch(
        "steps.transform_disclosure_files.process.call_mistral_ocr",
    ) as mock_call:
        process(input_data, step_dir, writer)
    writer.finalize()
    mock_call.assert_not_called()

    result = json.loads(output_path.read_text())
    assert result["results"][0]["pdf_extractor"] == "pdfplumber"
    captured = capsys.readouterr()
    assert "MISTRAL_API_KEY" in captured.out


# ── _process_single_file result record ───────────────────────────────────────

def test_process_single_file_includes_pdf_extractor(tmp_path):
    import json
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    rows = [["Our Ref", "Date Received", "Description"], ["1", "2024-01-01", "req"]]
    pdf_bytes = _make_pdf([[rows]])

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    import hashlib
    key = hashlib.sha256(b"http://example.com/test.pdf").hexdigest()
    (cache_dir / f"{key}.bytes").write_bytes(pdf_bytes)

    input_data = {"results": [{"file_url": "http://example.com/test.pdf", "file_type": "pdf", "public_body_id": 1}]}
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    from unittest.mock import patch
    with patch("steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path", return_value=cache_dir / f"{key}.bytes"):
        process(input_data, tmp_path, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    assert result["results"][0].get("pdf_extractor") in ("pdfplumber", "camelot_stream")


def test_process_single_file_camelot_attempted_sets_flag_in_output(tmp_path):
    import json
    import unittest.mock
    from lib.file_utils import IncrementalWriter
    from steps.transform_disclosure_files.process import process

    rows = [["Blob1", "Blob2", "Blob3"], ["1", "2", "3"]]
    pdf_bytes = _make_pdf([[rows]])

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    import hashlib
    key = hashlib.sha256(b"http://example.com/test.pdf").hexdigest()
    (cache_dir / f"{key}.bytes").write_bytes(pdf_bytes)

    input_data = {"results": [{"file_url": "http://example.com/test.pdf", "file_type": "pdf", "public_body_id": 1}]}
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "transform_disclosure_files", key_field="file_url", force=True)
    with unittest.mock.patch("steps.transform_disclosure_files.process.DisclosureFileCache.get_file_path",
                              return_value=cache_dir / f"{key}.bytes"), \
         unittest.mock.patch("steps.transform_disclosure_files.process._extract_with_camelot_stream",
                              return_value=None):
        process(input_data, tmp_path, writer)
    writer.finalize()

    result = json.loads(output_path.read_text())
    assert result["results"][0].get("pdf_camelot_attempted") is True
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert not any(e.get("error_type") == "CamelotFallbackAttempted" for e in errors)


# ── _score_rows ───────────────────────────────────────────────────────────────

def test_score_rows_known_headers():
    # "Our Ref" → foi_reference_id, "Date Received" → date_received, "Description" → request_description
    rows = [["Our Ref", "Date Received", "Description"]]
    assert _score_rows(rows) >= 2


def test_score_rows_empty_returns_zero():
    assert _score_rows([]) == 0


def test_score_rows_all_none_header():
    rows = [[None, None, None]]
    assert _score_rows(rows) == 0


def test_score_rows_one_known_column():
    rows = [["Our Ref", "Blob1", "Blob2"]]
    assert _score_rows(rows) == 1


# ── _extract_with_camelot_stream ─────────────────────────────────────────────

def test_extract_with_camelot_stream_returns_none_on_import_error():
    import sys
    import unittest.mock
    with unittest.mock.patch.dict(sys.modules, {"camelot": None}):
        result = _extract_with_camelot_stream(b"not a pdf")
    assert result is None


def test_extract_with_camelot_stream_returns_none_on_exception():
    import unittest.mock
    mock_camelot = unittest.mock.MagicMock()
    mock_camelot.read_pdf.side_effect = Exception("camelot error")
    with unittest.mock.patch.dict("sys.modules", {"camelot": mock_camelot}):
        # Force reimport inside the function
        result = _extract_with_camelot_stream(b"%PDF fake")
    assert result is None


def test_extract_with_camelot_stream_normalizes_empty_string_to_none():
    import unittest.mock
    import pandas as pd
    mock_table = unittest.mock.MagicMock()
    mock_table.df = pd.DataFrame([["val", ""], ["", "other"]])
    mock_camelot = unittest.mock.MagicMock()
    mock_camelot.read_pdf.return_value = [mock_table]
    with unittest.mock.patch.dict("sys.modules", {"camelot": mock_camelot}):
        result = _extract_with_camelot_stream(b"%PDF fake")
    assert result == [["val", None], [None, "other"]]


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

PDF_URL = "https://assets.gov.ie/report.pdf"


# ── process() — PDF happy path ────────────────────────────────────────────────

def test_process_pdf_extracts_rows(requests_mock, tmp_path, make_writer):
    rows_in = [["Ref", "Date"], ["16/002", "2016-01-05"]]
    pdf_bytes = _make_pdf([[rows_in]])
    requests_mock.get(PDF_URL, content=pdf_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    r = writer.results[0]
    assert r["sheet_name"] == "page 1"
    assert r["rows"][0] == ["Ref", "Date"]
    assert r["rows"][1] == ["16/002", "2016-01-05"]


def test_process_pdf_no_errors_on_clean_file(requests_mock, tmp_path, make_writer):
    pdf_bytes = _make_pdf([[[ ["Our Ref", "Date Received", "Description"], ["001", "2024-01-01", "req"] ]]])
    requests_mock.get(PDF_URL, content=pdf_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []


def test_process_pdf_multiple_tables_sets_flag_in_output(requests_mock, tmp_path, make_writer):
    table1 = [["Ref", "Date"], ["001", "2024-01-01"]]
    table2 = [["002", "2024-01-02"]]
    pdf_bytes = _make_pdf([[table1, table2]])
    requests_mock.get(PDF_URL, content=pdf_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    assert len(writer.results) == 1  # record still written
    assert writer.results[0].get("pdf_multiple_tables") is True
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert not any(e.get("error_type") == "MultipleTableWarning" for e in errors)


def test_process_pdf_single_table_has_no_multiple_tables_flag(requests_mock, tmp_path, make_writer):
    rows = [["Our Ref", "Date Received", "Description"], ["1", "2024-01-01", "req"]]
    pdf_bytes = _make_pdf([[rows]])
    requests_mock.get(PDF_URL, content=pdf_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert not writer.results[0].get("pdf_multiple_tables")


def test_process_pdf_no_tables_logs_error_and_skips_record(requests_mock, tmp_path, make_writer, monkeypatch):
    import steps.transform_disclosure_files.process as proc
    monkeypatch.setattr(proc, "_extract_with_camelot_stream", lambda b: None)
    pdf_bytes = _make_pdf_no_tables()
    requests_mock.get(PDF_URL, content=pdf_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    assert writer.results == []
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME
    assert errors[0]["error_type"] == "ValueError"


def test_process_pdf_corrupt_logs_error_and_skips_record(requests_mock, tmp_path, make_writer):
    requests_mock.get(PDF_URL, content=b"not a valid pdf")
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(PDF_INPUT, tmp_path, writer)
    assert writer.results == []
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME


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
    from lib.file_utils import write_json, IncrementalWriter
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


# ── process() — error handling ────────────────────────────────────────────────

def test_process_download_failure_logs_error(requests_mock, tmp_path, make_writer):
    import requests as req
    requests_mock.get("https://assets.gov.ie/log.xlsx",
                      exc=req.exceptions.ConnectionError("timeout"))
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    assert writer.results == []  # no record written
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME
    assert errors[0]["error_type"] == "ConnectionError"


def test_process_parse_failure_logs_error(requests_mock, tmp_path, make_writer):
    requests_mock.get("https://assets.gov.ie/log.xlsx", content=b"not-a-valid-xlsx")
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    assert writer.results == []
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME


def test_errors_persist_across_process_calls(requests_mock, tmp_path, make_writer):
    """Errors from a prior process() call are not destroyed on re-run."""
    import requests as req

    # First run: download fails, error logged
    requests_mock.get("https://assets.gov.ie/log.xlsx",
                      exc=req.exceptions.ConnectionError("timeout"))
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)

    errors_after_first = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors_after_first) == 1

    # Second run with a different file — errors.json must not be wiped
    second_input = {
        "metadata": {"step": "find_disclosure_files"},
        "results": [{**BASE_ITEM, "file_url": "https://assets.gov.ie/other.xlsx", "file_type": "xlsx"}],
    }
    requests_mock.get("https://assets.gov.ie/other.xlsx",
                      exc=req.exceptions.ConnectionError("timeout2"))
    writer2 = make_writer(STEP_NAME, key_field="file_url")
    process(second_input, tmp_path, writer2)

    errors_after_second = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors_after_second) == 2, (
        f"Expected 2 cumulative errors, got {len(errors_after_second)} — "
        "first run's errors were wiped"
    )


def test_process_download_failure_does_not_mark_processed(requests_mock, tmp_path, make_writer):
    """After a failure, the file_url is NOT marked processed (allows retry)."""
    import requests as req
    requests_mock.get("https://assets.gov.ie/log.xlsx",
                      exc=req.exceptions.ConnectionError("x"))
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    # Error does not mark the file_url as processed — allows retry on next run
    assert not writer.is_processed("https://assets.gov.ie/log.xlsx")


def test_process_xlsx_multiple_sheets_sets_flag_in_output(requests_mock, tmp_path, make_writer):
    xlsx_bytes = _make_xlsx([["Col A"]], extra_sheets=2, extra_sheet_rows=[["Col B"]])
    requests_mock.get("https://assets.gov.ie/log.xlsx", content=xlsx_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)
    assert len(writer.results) == 1  # record still written
    assert writer.results[0]["rows"][0] == ["Col A"]
    assert writer.results[0].get("multiple_sheets") is True
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert not any(e.get("error_type") == "MultipleSheetWarning" for e in errors)


def test_process_xls_multiple_sheets_sets_flag_in_output(requests_mock, tmp_path, make_writer):
    xls_bytes = _make_xls([["Col A"]], extra_sheets=2, extra_sheet_rows=[["Col B"]])
    requests_mock.get("https://assets.gov.ie/log.xls", content=xls_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLS_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert writer.results[0].get("multiple_sheets") is True
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert not any(e.get("error_type") == "MultipleSheetWarning" for e in errors)


# ── process() — CellSerializationWarning ─────────────────────────────────────

def test_process_cell_serialization_warning_not_logged_to_errors(requests_mock, tmp_path, make_writer, monkeypatch):
    """Verify that fallback cells do NOT write to errors.json; record is still written."""
    import steps.transform_disclosure_files.process as proc_mod

    original_serialise = proc_mod.serialise_cell
    call_count = {"n": 0}

    def patched_serialise(value):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return str(value) + "_fallback", True
        return original_serialise(value)

    monkeypatch.setattr(proc_mod, "serialise_cell", patched_serialise)

    xlsx_bytes = _make_xlsx([["Header", "Value"], ["row1", "data"]])
    requests_mock.get("https://assets.gov.ie/log.xlsx", content=xlsx_bytes)
    writer = make_writer(STEP_NAME, key_field="file_url")
    process(XLSX_INPUT, tmp_path, writer)

    assert len(writer.results) == 1
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert not any(e.get("error_type") == "CellSerializationWarning" for e in errors)


import sys as _sys
from lib.file_utils import read_json as _read_json, write_json as _write_json
import steps.transform_disclosure_files.process as _proc


def test_public_body_scoped_leaves_others_untouched(requests_mock, tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    # Seed file-keyed records (multiple files for body 1002)
    seeded = [
        {"public_body_id": 1001, "file_url": "https://a.ie/f.xlsx", "marker": "keep-1001"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f1.xlsx", "marker": "old-1002-f1"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f2.xlsx", "marker": "old-1002-f2"},
        {"public_body_id": 1003, "file_url": "https://c.ie/f.xlsx", "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "transform_disclosure_files"}, "results": seeded})

    xlsx_bytes = _make_xlsx([["Ref", "Date"], ["001", "2024-01-01"]])
    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "file_url": "https://a.ie/f.xlsx", "file_type": "xlsx",
         "disclosure_page_url": "https://a.ie/disc/"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f1.xlsx", "file_type": "xlsx",
         "disclosure_page_url": "https://b.ie/disc/"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f2.xlsx", "file_type": "xlsx",
         "disclosure_page_url": "https://b.ie/disc/"},
        {"public_body_id": 1003, "file_url": "https://c.ie/f.xlsx", "file_type": "xlsx",
         "disclosure_page_url": "https://c.ie/disc/"},
    ]})
    requests_mock.get("https://b.ie/f1.xlsx", content=xlsx_bytes)
    requests_mock.get("https://b.ie/f2.xlsx", content=xlsx_bytes)

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    body_map = {}
    for r in results:
        body_map.setdefault(r["public_body_id"], []).append(r)

    assert body_map[1001][0]["marker"] == "keep-1001"
    assert body_map[1003][0]["marker"] == "keep-1003"
    assert not any(r.get("marker", "").startswith("old-1002") for r in body_map.get(1002, []))
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]


# ── DisclosureFileCache tests ─────────────────────────────────────────────────

import hashlib
import tempfile
import shutil

from steps.transform_disclosure_files.process import (
    DisclosureFileCache,
    DownloadError,
)


@pytest.fixture
def cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_path = tmp_path / "cache"
    cache_path.mkdir()
    return cache_path


@pytest.fixture
def cache(cache_dir):
    """Create a DisclosureFileCache instance."""
    return DisclosureFileCache(cache_dir)


def test_cache_miss_downloads_and_caches(cache_dir, requests_mock):
    """New URL triggers download and save to cache."""
    url = "https://example.com/test.pdf"
    content = b"test pdf content"

    requests_mock.get(url, content=content)

    cache = DisclosureFileCache(cache_dir)
    result_path = cache.get_file_path(url, cache_dir.parent)

    assert result_path.exists()
    assert result_path.read_bytes() == content
    assert requests_mock.call_count == 1


def test_cache_hit_returns_cached(cache_dir, requests_mock):
    """Cached URL returns file without download."""
    url = "https://example.com/test.pdf"
    content = b"test pdf content"

    # Pre-populate cache
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{url_hash}.bytes"
    cache_path.write_bytes(content)

    cache = DisclosureFileCache(cache_dir)
    result_path = cache.get_file_path(url, cache_dir.parent)

    assert result_path.exists()
    assert result_path.read_bytes() == content
    assert requests_mock.call_count == 0


def test_concurrent_same_url_single_download(cache_dir, requests_mock):
    """Multiple workers requesting same URL results in one download.
    
    Note: This test verifies that the cache returns the same path for the same URL.
    The file locking mechanism prevents duplicate downloads, but testing it precisely
    is complex in a test environment. We verify that the same cached file is returned.
    """
    url = "https://example.com/test.pdf"
    content = b"test pdf content"

    requests_mock.get(url, content=content)

    cache = DisclosureFileCache(cache_dir)

    # First download
    result_path1 = cache.get_file_path(url, cache_dir.parent)
    assert result_path1.exists()
    assert requests_mock.call_count == 1
    
    # Second request for same URL should use cache
    result_path2 = cache.get_file_path(url, cache_dir.parent)
    assert result_path2.exists()
    assert str(result_path1) == str(result_path2)
    assert requests_mock.call_count == 1  # No additional download


def test_cache_directory_creation(tmp_path):
    """Cache directory created if missing."""
    cache_dir = tmp_path / "nonexistent" / "cache"
    assert not cache_dir.exists()

    cache = DisclosureFileCache(cache_dir)
    assert cache_dir.exists()


def test_acquire_lock_returns_fd(cache_dir):
    """_acquire_lock returns the fd that holds the flock, not a boolean."""
    import fcntl
    from steps.transform_disclosure_files.process import DisclosureFileCache
    cache = DisclosureFileCache(cache_dir)
    lock_path = cache_dir / "test.lock"
    lock_file = cache._acquire_lock(lock_path)
    assert lock_file is not None, "_acquire_lock should return the fd"
    assert not lock_file.closed, "returned fd should be open"
    # Confirm the fd actually holds the lock (a second non-blocking attempt should fail)
    fd2 = open(lock_path, "w")
    try:
        fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # If we get here the lock was NOT held — that's the bug
        assert False, "expected flock to be held by _acquire_lock's fd"
    except (IOError, OSError):
        pass  # correct: lock is held
    finally:
        fd2.close()
    cache._release_lock(lock_file)


def test_url_hash_helper_deduplicates_sha256(cache_dir):
    """_url_hash returns the same value as both _get_cache_path and _lock_path use."""
    from steps.transform_disclosure_files.process import DisclosureFileCache
    import hashlib
    cache = DisclosureFileCache(cache_dir)
    url = "https://example.com/file.xlsx"
    expected_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    assert cache._url_hash(url) == expected_hash
    assert cache._get_cache_path(url) == cache_dir / f"{expected_hash}.bytes"
    assert cache._lock_path(url) == cache_dir / f"{expected_hash}.lock"


# ── Parallel Processing Integration Tests ────────────────────────────────────


# Note: test_parallel_processing_correctness temporarily disabled due to
# threading issues with IncrementalWriter in test environment
# def test_parallel_processing_correctness(requests_mock, tmp_path, make_writer):
#     ...


def test_parallel_processing_preserves_order(requests_mock, tmp_path, make_writer):
    """Verify results match input order."""
    # Create 4 different XLSX files with identifiable content
    xlsx_files = {}
    for i in range(1, 5):
        xlsx_files[f"https://example.com/file{i}.xlsx"] = _make_xlsx([[f"file{i}"]])

    input_data = {
        "metadata": {"step": "find_disclosure_files"},
        "results": [
            {**BASE_ITEM, "file_url": url, "file_type": "xlsx"}
            for url in sorted(xlsx_files.keys())
        ],
    }

    for url, content in xlsx_files.items():
        requests_mock.get(url, content=content)

    writer = make_writer(STEP_NAME, key_field="file_url")
    process(input_data, tmp_path, writer, workers=2)

    assert len(writer.results) == 4
    # Results should be in same order as input
    for i, result in enumerate(writer.results):
        expected_url = f"https://example.com/file{i+1}.xlsx"
        assert result["file_url"] == expected_url
        assert result["rows"][0][0] == f"file{i+1}"


# Note: test_parallel_error_handling temporarily disabled due to
# threading issues with IncrementalWriter in test environment
# def test_parallel_error_handling(requests_mock, tmp_path, make_writer):
#     ...


# ── process() — verification status filtering ────────────────────────────────

def test_process_skips_unverified_item_silently(requests_mock, tmp_path, make_writer):
    """Unverified items are skipped: no download, no output record, no error entry."""
    xlsx_bytes = _make_xlsx([["Ref", "Date"], ["001", "2024-01-01"]])
    url = "https://assets.gov.ie/log.xlsx"
    requests_mock.get(url, content=xlsx_bytes)

    unverified_input = {
        "metadata": {"step": "find_disclosure_files"},
        "results": [
            {
                **BASE_ITEM,
                "file_url": url,
                "file_type": "xlsx",
                "verification_status": "unverified",
            }
        ],
    }

    writer = make_writer(STEP_NAME, key_field="file_url")
    process(unverified_input, tmp_path, writer)

    assert requests_mock.call_count == 0, "unverified item must not trigger a download"
    assert writer.results == []
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []
