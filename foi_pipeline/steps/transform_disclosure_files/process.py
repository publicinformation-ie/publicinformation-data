#!/usr/bin/env python3
import argparse
import datetime
import decimal
import io
import sys
from pathlib import Path

from scripts.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from scripts.http_utils import fetch

STEP_NAME = "transform_disclosure_files"


def serialise_cell(value):
    """Convert a cell value to a JSON-safe type. Returns (value, used_fallback)."""
    if value is None:
        return None, False
    if isinstance(value, bool):
        return value, False
    if isinstance(value, (str, int, float)):
        return value, False
    if isinstance(value, datetime.datetime):
        return value.isoformat(), False
    if isinstance(value, datetime.date):
        return value.isoformat(), False
    if isinstance(value, decimal.Decimal):
        return float(value), False
    return str(value), True


def _extract_xlsx(file_bytes):
    """Parse XLSX bytes. Returns (sheet_name, rows, fallback_cells, has_multiple_sheets)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    has_multiple_sheets = len(wb.sheetnames) > 1
    ws = wb.worksheets[0]
    sheet_name = ws.title
    rows = []
    fallback_cells = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
        serialised_row = []
        for col_idx, cell_val in enumerate(row):
            val, used_fallback = serialise_cell(cell_val)
            if used_fallback:
                fallback_cells.append(
                    (row_idx, col_idx, type(cell_val).__name__, repr(cell_val)[:50])
                )
            serialised_row.append(val)
        rows.append(serialised_row)
    wb.close()
    return sheet_name, rows, fallback_cells, has_multiple_sheets


def _extract_xls(file_bytes):
    """Parse XLS bytes. Placeholder for future implementation."""
    pass


def process(input_path, output_path):
    """Placeholder for main process function."""
    pass
