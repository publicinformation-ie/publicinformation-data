#!/usr/bin/env python3
"""Split combined date+description columns into two separate columns.

Some disclosure logs use a single "Date and Details of Request Received" column
that contains both the date and the request description in a single cell, separated
by a space (after normalize_disclosure_cells converts PDF newlines to spaces).
This step splits such columns before extract_disclosures_normalize_rows runs, so
the description is not destroyed by date normalisation.
"""
import argparse
import re
import sys
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_status, IncrementalWriter
from lib.column_map import COMBINED_DATE_HEADERS
from lib.text_utils import normalize_header
from steps.extract_disclosures_canonicalize.column_map import canonicalize_header

STEP_NAME = "extract_disclosures_split_combined_columns"

# Replacement headers used when splitting. Both are already recognised synonyms
# in column_map.py: "Date Received" → date_received, "Request Details" → request_description.
_DATE_HEADER = "Date Received"
_DESC_HEADER = "Request Details"

# Matches a date prefix at the start of the string followed by a space and description text.
# Group 1: the date portion. Group 2: the description portion.
_SPLIT_RE = re.compile(
    r'^('
    r'\d{4}-\d{1,2}-\d{1,2}'                                                         # ISO YYYY-MM-DD
    r'|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}'  # DD[ord] Month YYYY
    r'|\d{1,2}/\d{1,2}/\d{2,4}'                                                       # DD/MM/YYYY
    r'|\d{1,2}-\d{1,2}-\d{2,4}'                                                       # DD-MM-YYYY
    r'|\d{1,2}\.\d{1,2}\.\d{2,4}'                                                     # DD.MM.YYYY
    r')\s+(\S.*)',
    re.IGNORECASE | re.DOTALL,
)

# Matches: <asterisk?><date> <refID>   e.g. "06/07/2022 19447" or "*02/01/2018 9559"
_DATE_REFID_RE = re.compile(
    r'^\*?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s+(\d{4,6})$'
)

# Matches: <refID> <date>   e.g. "7190 19/01/2017"
_REFID_DATE_RE = re.compile(
    r'^(\d{4,6})\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})$'
)

# Matches a pure FOI reference ID (4–6 digits, optional leading asterisk)
_PURE_REFID_RE = re.compile(r'^\*?(\d{4,6})$')

# Replacement header used when inserting the extracted reference ID column.
# "FOI Reference Number" is already a synonym for foi_reference_id in column_map.py.
_REFID_HEADER = "FOI Reference Number"

# Canonical names for date columns — split detection applies only to these.
_DATE_CANONICALS = frozenset({"date_received", "decision_date"})


def _column_has_embedded_refids(rows: list, col_idx: int, header_row_idx: int) -> bool:
    """Return True if any data-row cell in this column is a pure FOI reference ID."""
    for row in rows[header_row_idx + 1:]:
        if not row or col_idx >= len(row):
            continue
        cell = row[col_idx]
        if cell and isinstance(cell, str) and _PURE_REFID_RE.match(cell.strip()):
            return True
    return False


def split_cell(cell) -> tuple:
    """Split a combined date+description cell into (date_text, description_text).

    Returns (cell, None) when no description prefix is found (pure date or non-string).
    """
    if not isinstance(cell, str):
        return (cell, None)
    if not cell:
        return (cell, None)
    m = _SPLIT_RE.match(cell.strip())
    if m:
        return (m.group(1).strip(), m.group(2).strip() or None)
    return (cell, None)


def split_refid_date_cell(cell) -> tuple:
    """Split a cell that mixes a FOI reference ID with a date.

    Returns (refid, date_str). Either element may be None.

    Handles the patterns found in DSP multi-sub-column date headers:
      - pure date:         "18/01/2017"         → (None,    "18/01/2017")
      - pure refID:        "7191"                → ("7191",  None)
      - refID then date:   "7190 19/01/2017"     → ("7190",  "19/01/2017")
      - date then refID:   "06/07/2022 19447"    → ("19447", "06/07/2022")
      - asterisk-prefixed: "*02/01/2018 9559"    → ("9559",  "02/01/2018")
      - asterisk+refID:    "*9557"               → ("9557",  None)
    """
    if not isinstance(cell, str) or not cell.strip():
        return (None, None)
    value = cell.strip()

    m = _DATE_REFID_RE.match(value)
    if m:
        return (m.group(2), m.group(1))

    m = _REFID_DATE_RE.match(value)
    if m:
        return (m.group(1), m.group(2))

    m = _PURE_REFID_RE.match(value)
    if m:
        return (m.group(1), None)

    # Pure date or unrecognised — leave unchanged
    return (None, value)


def split_file(item: dict) -> tuple:
    """Split combined date+description columns in one file record.

    Returns (updated_item, errors). Returns (item, []) unchanged if no combined
    column is found or if the item has no rows/header.
    """
    rows = item.get("rows")
    header_row_idx = item.get("header_row_idx")
    if rows is None or header_row_idx is None or header_row_idx >= len(rows):
        return item, []

    headers = rows[header_row_idx]

    # Find indices of combined columns. Process right-to-left so inserting a new
    # column at index N doesn't shift the position of columns at index < N.
    combined_indices = [
        i for i, h in enumerate(headers)
        if h and normalize_header(str(h)) in COMBINED_DATE_HEADERS
    ]

    new_rows = [list(r) if r is not None else r for r in rows]
    header_row = new_rows[header_row_idx]
    if header_row is None:
        return item, []

    for col_idx in reversed(combined_indices):
        # Replace combined header with two separate headers
        header_row[col_idx] = _DATE_HEADER
        header_row.insert(col_idx + 1, _DESC_HEADER)

        # Split each data row
        for row_idx in range(header_row_idx + 1, len(new_rows)):
            row = new_rows[row_idx]
            if not row:
                continue
            cell = row[col_idx] if col_idx < len(row) else None
            date_text, desc_text = split_cell(cell)
            if col_idx < len(row):
                row[col_idx] = date_text
                row.insert(col_idx + 1, desc_text)

    # --- Detect and split date columns that contain embedded FOI reference IDs ---
    # Some PDFs use a two-sub-column layout (RefID | Date) under a single "Date of Request"
    # header. The PDF extractor collapses these into one column, producing cells like
    # "7190 19/01/2017", "7191" (pure refID), "19447" (pure refID), or "06/07/2022 19447".
    refid_indices = [
        i for i, h in enumerate(header_row)
        if h and canonicalize_header(str(h)) in _DATE_CANONICALS
        and _column_has_embedded_refids(new_rows, i, header_row_idx)
    ]

    if not combined_indices and not refid_indices:
        return item, []

    for col_idx in reversed(refid_indices):
        # Insert new FOI Reference Number header after the date column
        header_row.insert(col_idx + 1, _REFID_HEADER)

        for row_idx in range(header_row_idx + 1, len(new_rows)):
            row = new_rows[row_idx]
            if not row:
                continue
            cell = row[col_idx] if col_idx < len(row) else None
            refid, date_str = split_refid_date_cell(cell)
            if col_idx < len(row):
                row[col_idx] = date_str
                row.insert(col_idx + 1, refid)
            else:
                row.insert(col_idx + 1, None)

    return {**item, "rows": new_rows}, []


def main():
    parser = argparse.ArgumentParser(
        description="Split combined date+description columns into two separate columns"
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

    writer = IncrementalWriter(
        output_path, STEP_NAME, key_field="file_url", force=args.force,
        override_path=override_path,
        upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
        target_public_body=args.public_body,
    )

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    splits_count = 0
    for item in input_data.get("results", []):
        file_url = item.get("file_url")
        if writer.is_processed(file_url):
            continue
        updated_item, _ = split_file(item)
        if updated_item is not item:
            splits_count += 1
        writer.append([updated_item])

    count = writer.finalize()
    write_status(step_dir, count)

    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path} ({splits_count} file(s) had columns split)")


if __name__ == "__main__":
    main()
