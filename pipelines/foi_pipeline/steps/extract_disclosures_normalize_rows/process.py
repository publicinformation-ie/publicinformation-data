#!/usr/bin/env python3
"""Normalize date values in disclosure rows to ISO 8601 format."""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dateutil.parser import parse as dateutil_parse

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status, IncrementalWriter, append_errors
from steps.extract_disclosures_canonicalize.column_map import canonicalize_header

STEP_NAME = "extract_disclosures_normalize_rows"

# Date column canonical names
DATE_COLUMNS = frozenset({"date_received", "decision_date"})

# Regex patterns for known date formats (ordered by specificity)
# Each pattern returns (year, month, day) groups
_DATE_PATTERNS = [
    # ISO 8601: YYYY-MM-DD
    (re.compile(r'^(\d{4})-(\d{1,2})-(\d{1,2})$'), True),
    
    # Short year formats: DD-Mon-YY or DD-Mon-YYYY
    (re.compile(r'^(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{2,4})$', re.IGNORECASE), True),
    
    # DD.MM.YYYY or D.M.YYYY
    (re.compile(r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$'), False),
    
    # DD-MM-YYYY or D-M-YYYY
    (re.compile(r'^(\d{1,2})-(\d{1,2})-(\d{2,4})$'), False),
    
    # DD/MM/YYYY or D/M/YYYY
    (re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$'), False),
    
    # Month DD, YYYY (e.g., "February 01, 2023")
    (re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),\s*(\d{4})$', re.IGNORECASE), True),
    
    # DD Month YYYY (e.g., "01 February 2023" or "1 Feb 2023")
    (re.compile(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})$', re.IGNORECASE), True),
    
    # Ordinal formats: "14th July 2016", "1st January 2020"
    (re.compile(r'^(\d{1,2})(st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})$', re.IGNORECASE), True),
]

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

# Values in date columns that are intentionally non-dates (headers, status words, etc.)
_SKIP_VALUES = frozenset({
    'n/a', 'na', 'null', 'none', '', '-', '---',
    'date received', 'date', 'received', 'decision date',
    'decision', 'date issued', 'date of request',
    'part granted', 'granted', 'refused', 'full granted',
    'pending', 'withdrawn', 'transferred',
})


def _parse_month(month_str: str) -> int:
    """Convert month string to integer (1-12)."""
    return _MONTH_MAP[month_str[:3].lower()]


def normalize_date_value(raw_value: Optional[str]) -> Optional[str]:
    """Normalize a single date string to ISO 8601 format (YYYY-MM-DD).
    
    Args:
        raw_value: The raw date value to normalize. Can be None or empty string.
        
    Returns:
        ISO 8601 formatted date string (YYYY-MM-DD), or None if unparseable.
        
    Algorithm:
        1. Return None for None, empty string, or whitespace-only values
        2. Try regex patterns for known formats
        3. Fall back to dateutil.parser with dayfirst=True (Irish convention)
        4. Validate parsed date: year between 1900 and 2100
        5. Return ISO 8601 string
    """
    if raw_value is None:
        return None
    
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)
    
    # Strip whitespace
    value = raw_value.strip()
    
    # Return None for empty strings
    if not value:
        return None
    
    if value.lower() in _SKIP_VALUES:
        return None
    
    # Try regex patterns first
    for pattern, is_iso_order in _DATE_PATTERNS:
        match = pattern.match(value)
        if match:
            try:
                groups = match.groups()
                if is_iso_order:
                    if pattern == _DATE_PATTERNS[0][0]:
                        # ISO format: YYYY-MM-DD
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    elif pattern == _DATE_PATTERNS[1][0]:
                        # DD-Mon-YY or DD-Mon-YYYY
                        day = int(groups[0])
                        month = _parse_month(groups[1])
                        year_str = groups[2]
                        year = int(year_str) if len(year_str) == 4 else _two_digit_year(year_str)
                    elif pattern == _DATE_PATTERNS[5][0]:
                        # Month DD, YYYY: groups = (month_name, day, year)
                        month = _parse_month(groups[0])
                        day = int(groups[1])
                        year = int(groups[2])
                    elif pattern == _DATE_PATTERNS[6][0]:
                        # DD Month YYYY: groups = (day, month_name, year)
                        day = int(groups[0])
                        month = _parse_month(groups[1])
                        year = int(groups[2])
                    elif pattern == _DATE_PATTERNS[7][0]:
                        # Ordinal DDth Month YYYY: groups = (day, suffix, month_name, year)
                        day = int(groups[0])
                        month = _parse_month(groups[2])
                        year = int(groups[3])
                    else:
                        continue
                else:
                    # DD/MM/YYYY order (Irish standard)
                    if len(groups) == 3:
                        if pattern == _DATE_PATTERNS[2][0]:
                            # DD.MM.YYYY
                            day, month, year_str = int(groups[0]), int(groups[1]), groups[2]
                        elif pattern == _DATE_PATTERNS[3][0]:
                            # DD-MM-YYYY
                            day, month, year_str = int(groups[0]), int(groups[1]), groups[2]
                        elif pattern == _DATE_PATTERNS[4][0]:
                            # DD/MM/YYYY
                            day, month, year_str = int(groups[0]), int(groups[1]), groups[2]
                        else:
                            continue
                        year = int(year_str) if len(year_str) == 4 else _two_digit_year(year_str)
                    else:
                        continue
                
                # Validate date components
                if not _is_valid_date(year, month, day):
                    return None
                
                return f"{year:04d}-{month:02d}-{day:02d}"
            except (ValueError, KeyError, IndexError):
                continue
    
    # Fall back to dateutil.parser with Irish date convention (DD/MM/YYYY)
    try:
        parsed = dateutil_parse(value, dayfirst=True)
        year = parsed.year
        month = parsed.month
        day = parsed.day
        
        # Validate year range
        if year < 1900 or year > 2100:
            return None
        
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, OverflowError, TypeError):
        return None


def _two_digit_year(year_str: str) -> int:
    """Convert 2-digit year to 4-digit year using Irish convention.
    
    00-29 -> 2000-2029
    30-99 -> 1930-1999
    """
    year = int(year_str)
    if year >= 0 and year <= 29:
        return 2000 + year
    elif year >= 30 and year <= 99:
        return 1900 + year
    return year


def _is_valid_date(year: int, month: int, day: int) -> bool:
    if year < 1900 or year > 2100:
        return False
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def is_date_column(header: Optional[str]) -> bool:
    """Determine if a column header represents a date field.
    
    Args:
        header: The column header string to check.
        
    Returns:
        True if the header maps to a canonical date column, False otherwise.
    """
    if header is None:
        return False
    canonical = canonicalize_header(header)
    return canonical in DATE_COLUMNS


def process_file(item: dict, step_dir: Path, verbose: bool = False) -> tuple[dict, list[dict]]:
    """Process a single file record, normalizing date values in date columns.
    
    Args:
        item: A file record from the previous step output.
        step_dir: Path to the step directory.
        verbose: If True, print progress dots.
        
    Returns:
        A tuple of (updated_item, errors) where:
        - updated_item: The item with date values normalized in its rows
        - errors: List of error dicts for unparseable date values
    """
    rows = item.get("rows")
    header_row_idx = item.get("header_row_idx")
    file_url = item.get("file_url")
    public_body_id = item.get("public_body_id")
    public_body_name = item.get("name")
    
    # If no rows or no header row, return unchanged
    if rows is None or header_row_idx is None or header_row_idx >= len(rows):
        return item, []
    
    errors = []
    
    # Get headers from the header row
    headers = rows[header_row_idx]
    
    # Identify date column indices
    date_col_indices = []
    for col_idx, header in enumerate(headers):
        if is_date_column(header):
            date_col_indices.append(col_idx)
    
    if not date_col_indices:
        # No date columns found, return unchanged
        return item, []
    
    if verbose:
        print(f"  Found {len(date_col_indices)} date column(s) in {file_url}")
    
    # Process each data row (rows after header_row_idx)
    new_rows = list(rows)
    for row_idx in range(header_row_idx + 1, len(rows)):
        row = list(rows[row_idx])
        for col_idx in date_col_indices:
            if col_idx < len(row):
                cell_value = row[col_idx]
                # Get the canonical header name for error context
                header_name = headers[col_idx] if col_idx < len(headers) else str(col_idx)
                canonical_col = canonicalize_header(header_name)
                
                normalized = normalize_date_value(cell_value)
                
                cell_str = str(cell_value).strip() if cell_value is not None else ""
                if normalized is None and cell_str and cell_str.lower() not in _SKIP_VALUES:
                    # Log error for unparseable date
                    error_context = {
                        "file_url": file_url,
                        "public_body_id": public_body_id,
                        "public_body_name": public_body_name,
                        "column_header": header_name,
                        "canonical_column": canonical_col,
                        "original_value": str(cell_value),
                        "row_index": row_idx,
                        "column_index": col_idx,
                    }
                    error = {
                        "error_type": "UnparseableDate",
                        "error_message": f"Could not parse date value: {cell_value}",
                        "context": error_context,
                        "step": STEP_NAME,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    errors.append(error)
                    if verbose:
                        print(f"  WARNING: Unparseable date at row {row_idx}, col {col_idx}: {cell_value}")
                
                # Replace cell value with normalized date (or None)
                row[col_idx] = normalized
        new_rows[row_idx] = row
    
    updated_item = {**item, "rows": new_rows}
    return updated_item, errors


def process(input_data: dict, step_dir: Path, writer: IncrementalWriter, verbose: bool = False):
    """Process all items in the input data.
    
    Args:
        input_data: The input data dict with 'results' key containing file records.
        step_dir: Path to the step directory.
        writer: IncrementalWriter instance for output.
        verbose: If True, print progress information.
    """
    errors_path = step_dir / "errors.json"
    if not errors_path.exists():
        write_json(errors_path, [])
    
    for item in input_data.get("results", []):
        file_url = item.get("file_url")
        
        # Skip if already processed (handled by IncrementalWriter)
        if writer.is_processed(file_url):
            if verbose:
                print(f"  Skipping already processed: {file_url}")
            continue
        
        updated_item, file_errors = process_file(item, step_dir, verbose)
        
        # Append to writer
        writer.append([updated_item])
        
        # Append errors to errors.json (one read/write per file)
        append_errors(step_dir, file_errors)
        
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize date values in disclosure rows to ISO 8601 format"
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
