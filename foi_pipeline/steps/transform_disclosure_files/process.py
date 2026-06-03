#!/usr/bin/env python3
import argparse
import datetime
import decimal
import io
import sys
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

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
    has_multiple_sheets = any(
        any(v is not None for row in ws.iter_rows(values_only=True) for v in row)
        for ws in wb.worksheets[1:]
    )
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


def _xlrd_cell_to_python(cell, datemode):
    """Convert an xlrd Cell to a Python value suitable for serialise_cell."""
    import xlrd
    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return cell.value
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        return cell.value  # always float from xlrd
    if cell.ctype == xlrd.XL_CELL_DATE:
        return datetime.datetime(*xlrd.xldate_as_tuple(cell.value, datemode))
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    return cell.value  # XL_CELL_ERROR — hits str() fallback in serialise_cell


def _extract_xls(file_bytes):
    """Parse XLS bytes. Returns (sheet_name, rows, fallback_cells, has_multiple_sheets)."""
    import xlrd
    wb = xlrd.open_workbook(file_contents=file_bytes)
    has_multiple_sheets = any(ws.nrows > 0 for ws in wb.sheets()[1:])
    ws = wb.sheets()[0]
    sheet_name = ws.name
    rows = []
    fallback_cells = []
    for row_idx in range(ws.nrows):
        serialised_row = []
        for col_idx in range(ws.ncols):
            raw = _xlrd_cell_to_python(ws.cell(row_idx, col_idx), wb.datemode)
            val, used_fallback = serialise_cell(raw)
            if used_fallback:
                fallback_cells.append(
                    (row_idx, col_idx, type(raw).__name__, repr(raw)[:50])
                )
            serialised_row.append(val)
        rows.append(serialised_row)
    return sheet_name, rows, fallback_cells, has_multiple_sheets


def _extract_pdf(file_bytes):
    """Parse PDF bytes. Returns (sheet_name, rows, fallback_cells, has_multiple_tables)."""
    import pdfplumber
    rows = []
    total_tables = 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        n_pages = len(pdf.pages)
        for page in pdf.pages:
            tables = page.extract_tables()
            total_tables += len(tables)
            for table in tables:
                for row in table:
                    serialised_row = [serialise_cell(cell)[0] for cell in row]
                    rows.append(serialised_row)
    if total_tables == 0:
        raise ValueError("no tables found")
    sheet_name = "page 1" if n_pages == 1 else f"pages 1-{n_pages}"
    return sheet_name, rows, [], total_tables > 1


def process(input_data, step_dir, writer, verbose=False):
    from datetime import datetime, timezone
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for item in input_data["results"]:
        file_url = item["file_url"]
        if writer.is_processed(file_url):
            continue

        file_type = item["file_type"]

        try:
            response = fetch("GET", file_url, allow_redirects=True)
            file_bytes = response.content

            if file_type == "xlsx":
                sheet_name, rows, fallback_cells, has_multiple = _extract_xlsx(file_bytes)
                if has_multiple:
                    append_error(step_dir, {
                        "step": STEP_NAME,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error_type": "MultipleSheetWarning",
                        "error_message": "File has multiple sheets; only the first sheet was extracted.",
                        "context": {"file_url": file_url},
                    })
            elif file_type == "xls":
                sheet_name, rows, fallback_cells, has_multiple = _extract_xls(file_bytes)
                if has_multiple:
                    append_error(step_dir, {
                        "step": STEP_NAME,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error_type": "MultipleSheetWarning",
                        "error_message": "File has multiple sheets; only the first sheet was extracted.",
                        "context": {"file_url": file_url},
                    })
            else:  # pdf
                sheet_name, rows, fallback_cells, has_multiple = _extract_pdf(file_bytes)
                if has_multiple:
                    append_error(step_dir, {
                        "step": STEP_NAME,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error_type": "MultipleTableWarning",
                        "error_message": "File has multiple tables; all table rows were concatenated.",
                        "context": {"file_url": file_url},
                    })

            if fallback_cells:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "CellSerializationWarning",
                    "error_message": f"{len(fallback_cells)} cell(s) used str() fallback.",
                    "context": {"file_url": file_url, "cells": fallback_cells},
                })

            writer.append([{**item, "sheet_name": sheet_name, "rows": rows}])

        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"file_url": file_url},
            })
            writer.processed_keys.add(file_url)
            writer.append([])

        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download and convert disclosure log files (XLSX/XLS/PDF) to JSON arrays"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (
        input_data.get("results") or input_data.get("public_bodies")
    ):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(
        output_path, STEP_NAME, key_field="file_url", force=args.force,
        override_path=override_path,
        upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
        target_public_body=args.public_body,
    )

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
