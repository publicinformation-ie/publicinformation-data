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

    if not combined_indices:
        return item, []

    new_rows = [list(r) if r is not None else r for r in rows]

    for col_idx in reversed(combined_indices):
        # Replace combined header with two separate headers
        new_rows[header_row_idx][col_idx] = _DATE_HEADER
        new_rows[header_row_idx].insert(col_idx + 1, _DESC_HEADER)

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
