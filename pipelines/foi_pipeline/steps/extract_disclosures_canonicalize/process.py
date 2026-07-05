#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body, merge_replacing_body
from lib.file_utils import read_json, write_json, write_status
from lib.column_map import (
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
    canonicalize_header,
    canonicalize_headers,
    compute_row_id,
)

STEP_NAME = "extract_disclosures_canonicalize"


def load_column_swaps(step_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """Load column swap overrides from column_swaps.json."""
    swaps_path = step_dir / "column_swaps.json"
    if not swaps_path.exists():
        return {}
    raw = read_json(swaps_path)
    return {url: [tuple(pair) for pair in pairs] for url, pairs in raw.items()}


def _load_column_mappings(step_dir: Path) -> dict:
    """Load column_mappings.json if it exists."""
    mappings_path = step_dir / "column_mappings.json"
    if not mappings_path.exists():
        return {}
    return read_json(mappings_path)


def _apply_manual_mapping(item: dict, mapping: dict) -> tuple[list, list, int]:
    """Apply manual column mapping to a file's rows.

    Returns (results, errors, header_rows_dropped) matching canonicalize_file signature.
    """
    rows = item.get("rows", [])
    header_row_idx = item.get("header_row_idx", 0)

    if not rows or header_row_idx is None or header_row_idx >= len(rows):
        return [], [], 0

    column_mapping = mapping.get("column_mapping", {})
    meta = {
        "public_body_id": item["public_body_id"],
        "name": item["name"],
        "file_url": item["file_url"],
        "file_type": item["file_type"],
        "source_method": mapping.get("source_method", "manual"),
        "overridden": mapping.get("overridden", True),
    }

    # Validate mapping covers required columns
    mapped_canonical: set[str] = set()
    for target in column_mapping.values():
        if isinstance(target, str):
            mapped_canonical.add(target)
        elif isinstance(target, list):
            mapped_canonical.update(t for t in target if t is not None)

    missing_required = REQUIRED_COLUMNS - mapped_canonical
    if missing_required:
        return [], [{
            "error_type": "MissingRequiredColumns",
            "error_message": f"Manual mapping missing required columns: {sorted(missing_required)}",
            "context": {"file_url": item["file_url"]},
        }], 0

    results = []
    errors = []
    header_rows_dropped = 0
    date_known_issues = item.get("date_known_issues") or {}
    # Process data rows (skip header)
    for original_row_index, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 1):
        if not row:
            continue
        record = {**meta}
        # Initialize all canonical columns to None
        for key in CANONICAL_COLUMNS:
            record[key] = None
        for col_str, target in column_mapping.items():
            try:
                col_idx = int(col_str)
            except ValueError:
                return [], [{
                    "error_type": "InvalidColumnMapping",
                    "error_message": f"column_mapping key {col_str!r} is not a valid integer column index",
                    "context": {"file_url": item["file_url"]},
                }], 0
            if col_idx >= len(row):
                continue
            cell_value = row[col_idx]
            if target is None:
                continue
            elif isinstance(target, str):
                record[target] = cell_value
            elif isinstance(target, list):
                # Split combined column (e.g. '05/01/2016 FOI/2016/0001')
                parts = str(cell_value or "").split() if cell_value else []
                for i, field in enumerate(target):
                    if field is None:
                        continue
                    record[field] = parts[i] if i < len(parts) else None
        if is_header_row(record):
            header_rows_dropped += 1
            continue
        if all(record.get(k) in (None, "") for k in CANONICAL_COLUMNS):
            errors.append({
                "error_type": "PhantomRecord",
                "error_message": "Record has no populated canonical fields; skipped",
                "context": {
                    "file_url": meta["file_url"],
                    "public_body_id": meta["public_body_id"],
                    "original_row_index": original_row_index,
                    "row_preview": list(row[:8]),
                },
            })
            continue
        record["row_id"] = compute_row_id(item["file_url"], original_row_index)
        record["known_issues"] = list(date_known_issues.get(str(original_row_index), []))
        results.append(record)

    return results, errors, header_rows_dropped


def is_header_row(row: dict, threshold: int = 2) -> bool:
    """Return True if 2+ field values in the row match known column header synonyms."""
    matches = sum(
        1 for key in CANONICAL_COLUMNS
        if canonicalize_header(str(row.get(key) or "")) is not None
    )
    return matches >= threshold


def _is_repeated_header_row(row: list, threshold: int = 2) -> bool:
    """Return True if 2+ raw cells in an extracted row match known column header
    synonyms.

    Mirrors is_header_row(), but operates on the raw row list before any
    canonical-field mapping or length-based realignment runs. Repeated header
    rows from page breaks in multi-page PDF tables can be hit by the same
    multi-line text-wrap artifact that produces RowLengthMismatch overflow —
    that can also land a repeated header at exactly len(headers)-1 or
    len(headers)+1, where Root Cause A/B would otherwise silently "correct" it
    into a fabricated data record instead of dropping it. Must run before any
    length-based branch in canonicalize_file()'s row loop.
    """
    matches = sum(
        1 for cell in row
        if cell and canonicalize_header(str(cell)) is not None
    )
    return matches >= threshold


def _is_column_letter_row(row: list) -> bool:
    non_none = [cell for cell in row if cell is not None]
    return bool(non_none) and all(
        isinstance(cell, str) and len(cell.strip()) == 1
        and cell.strip().isupper() and cell.strip().isalpha()
        for cell in non_none
    )


def _column_cardinality(rows: list, header_row_idx: int, col_idx: int) -> int:
    """Count distinct non-blank values in one column across the data rows.

    Used to break header→canonical collisions (analysis §4 M1a): a constant
    generic column (e.g. "General" in every row) has cardinality 1 and loses
    to the real column that holds varied requester/decision values.
    """
    seen: set[str] = set()
    for row in rows[header_row_idx + 1:]:
        if col_idx < len(row):
            value = row[col_idx]
            if value is not None and str(value).strip():
                seen.add(str(value).strip().lower())
    return len(seen)


def canonicalize_file(item, column_swaps=None, column_mappings=None):
    """Convert one file record into a list of canonical FOI row dicts.

    Returns (results, errors, header_rows_dropped).
    """
    # Check for manual column mapping override
    file_url = item.get("file_url")
    if column_mappings and file_url in column_mappings:
        return _apply_manual_mapping(item, column_mappings[file_url])

    rows = item.get("rows")
    header_row_idx = item.get("header_row_idx")
    if rows is None:
        return [], [], 0

    if header_row_idx is None or header_row_idx >= len(rows):
        return [], [], 0

    meta = {
        "public_body_id": item["public_body_id"],
        "name": item["name"],
        "file_url": item["file_url"],
        "file_type": item["file_type"],
    }

    headers = rows[header_row_idx]
    mapping = canonicalize_headers(headers)

    canonical_to_col_idx: dict[str, int] = {}
    for col_idx, header in enumerate(headers):
        canonical = mapping.get(header)
        if not canonical:
            continue
        existing = canonical_to_col_idx.get(canonical)
        if existing is None:
            canonical_to_col_idx[canonical] = col_idx
        elif _column_cardinality(rows, header_row_idx, col_idx) > \
                _column_cardinality(rows, header_row_idx, existing):
            # Collision (M1a): two headers claim the same canonical field. Keep the
            # column with more distinct values; discard the constant/generic one.
            # Ties keep the first-by-index column (stable, prior behaviour).
            canonical_to_col_idx[canonical] = col_idx

    if len(canonical_to_col_idx) < 2:
        return [], [{
            "error_type": "InsufficientColumns",
            "error_message": f"Only {len(canonical_to_col_idx)} canonical column(s) mapped",
            "context": {
                "file_url": item["file_url"],
                "mapped_columns": list(canonical_to_col_idx.keys()),
            },
        }], 0

    missing_columns = sorted(k for k in CANONICAL_COLUMNS if k not in canonical_to_col_idx)
    date_known_issues = item.get("date_known_issues") or {}
    file_swaps = column_swaps.get(item["file_url"], []) if column_swaps else []

    # Compute the "spacer column" position for row-length correction (Root Cause A / B).
    # Priority 1: an actual None/blank header — a physical blank spacer column in the PDF.
    # Priority 2: the first header that duplicates a canonical key already seen
    #             (e.g. two "Request Description" columns → the second is a spacer).
    # Unmapped string headers (e.g. an untranslated Irish column name) are NOT spacers;
    # skipping them prevents padding at the wrong position (body 1135 regression).
    _seen_for_dup: set[str] = set()
    none_header_idx: int | None = None
    for _i, _h in enumerate(headers):
        if not _h or not str(_h).strip():  # actual blank/None header (Priority 1)
            none_header_idx = _i
            break
        _c = mapping.get(_h)
        if _c is not None:
            if _c in _seen_for_dup:  # duplicate canonical key (Priority 2)
                none_header_idx = _i
                break
            _seen_for_dup.add(_c)

    results = []
    errors = []
    header_rows_dropped = 0
    for original_row_index, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 1):
        if not row:
            continue
        if _is_column_letter_row(row):
            continue
        if _is_repeated_header_row(row):
            header_rows_dropped += 1
            continue

        # Root Cause A: when a row is shorter than the header by exactly one cell,
        # restore the dropped spacer column so that all subsequent values align.
        if none_header_idx is not None and len(row) == len(headers) - 1:
            row = list(row)
            row.insert(none_header_idx, None)
        # Root Cause B (symmetric): when a row is longer than the header by exactly one
        # cell, pdfplumber added an extra blank column on this PDF page. Remove the first
        # None to restore alignment.
        elif len(row) == len(headers) + 1:
            for _extra_idx, _cell in enumerate(row):
                if _cell is None:
                    row = list(row)
                    del row[_extra_idx]
                    break
        elif len(row) > len(headers) + 1:
            non_blank = [cell for cell in row if cell not in (None, "")]
            if len(non_blank) == len(headers):
                # Root Cause D: a wrapped multi-line text cell (commonly the
                # description field) caused pdfplumber to inject extra blank
                # columns into this row, but every real value is still present,
                # blank-free, and in original column order. Collapse the blanks
                # instead of dropping a recoverable record.
                row = non_blank
            elif len(non_blank) <= 2:
                # Root Cause E: a stray continuation fragment of a wrapped line
                # bleeding into its own pseudo-row (e.g. "...vacan" / "t" split
                # off the previous row's description). Not a standalone record —
                # drop silently rather than logging a misleading
                # RowLengthMismatch error.
                header_rows_dropped += 1
                continue
            else:
                # Rows that are neither a clean blank-collapse nor an obvious
                # fragment cannot be reliably realigned (e.g. DEASP 2017 8-col
                # sub-table pages vs 6-col header). Drop and log rather than
                # emit a record with misaligned field values.
                errors.append({
                    "error_type": "RowLengthMismatch",
                    "error_message": (
                        f"Row has {len(row)} cells but header has {len(headers)}; "
                        "cannot reliably realign — row skipped"
                    ),
                    "context": {
                        "file_url": meta["file_url"],
                        "public_body_id": meta["public_body_id"],
                        "expected_cols": len(headers),
                        "actual_cols": len(row),
                        "row_preview": list(row[:8]),
                    },
                })
                continue

        record = {**meta}
        for key in CANONICAL_COLUMNS:
            if key in canonical_to_col_idx:
                col_idx = canonical_to_col_idx[key]
                record[key] = row[col_idx] if col_idx < len(row) else None
            else:
                record[key] = None
        for col_a, col_b in file_swaps:
            record[col_a], record[col_b] = record.get(col_b), record.get(col_a)
        if is_header_row(record):
            header_rows_dropped += 1
            continue

        if all(record.get(k) in (None, "") for k in CANONICAL_COLUMNS):
            errors.append({
                "error_type": "PhantomRecord",
                "error_message": "Record has no populated canonical fields; skipped",
                "context": {
                    "file_url": meta["file_url"],
                    "public_body_id": meta["public_body_id"],
                    "original_row_index": original_row_index,
                    "row_preview": list(row[:8]),
                },
            })
            continue

        # Root Cause B: drop rows where pdfplumber split a multi-word description
        # ("Request For Personal Information") across columns — every cell holds one word.
        req_desc = record.get("request_description")
        if req_desc and isinstance(req_desc, str) and req_desc.strip().lower() == "request":
            continue

        record["row_id"] = compute_row_id(item["file_url"], original_row_index)
        record["known_issues"] = list(date_known_issues.get(str(original_row_index), []))
        if missing_columns:
            record["missing_columns"] = missing_columns
        results.append(record)

    return results, errors, header_rows_dropped


def process(input_data, results_out, errors_out, column_swaps=None, column_mappings=None, verbose=False):
    total_dropped = 0
    for item in input_data["results"]:
        if item.get("rows") is None:
            continue
        file_records, file_errors, dropped = canonicalize_file(item, column_swaps, column_mappings)
        results_out.extend(file_records)
        errors_out.extend(file_errors)
        total_dropped += dropped
        if verbose:
            print(".", end="", flush=True)
    return total_dropped


def main():
    parser = argparse.ArgumentParser(
        description="Canonicalize disclosure log rows into flat FOI records"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)

    results: list = []
    errors: list = []

    column_swaps = load_column_swaps(step_dir)
    column_mappings = _load_column_mappings(step_dir)
    header_rows_dropped = process(input_data, results, errors, column_swaps=column_swaps, column_mappings=column_mappings, verbose=args.verbose)

    if args.public_body is not None and not args.force and output_path.exists():
        existing = read_json(output_path).get("results", [])
        results = merge_replacing_body(existing, results, args.public_body)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "header_rows_dropped": header_rows_dropped,
        },
        "results": results,
    })

    errors_path = step_dir / "errors.json"
    write_json(errors_path, errors)

    write_status(step_dir, len(results))
    if args.verbose:
        print()
    print(f"Wrote {len(results)} records to {output_path}")


if __name__ == "__main__":
    main()
