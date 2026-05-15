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
