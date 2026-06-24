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
)

STEP_NAME = "extract_disclosures_canonicalize"


def load_column_swaps(step_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """Load column swap overrides from column_swaps.json."""
    swaps_path = step_dir / "column_swaps.json"
    if not swaps_path.exists():
        return {}
    raw = read_json(swaps_path)
    return {url: [tuple(pair) for pair in pairs] for url, pairs in raw.items()}


def is_header_row(row: dict, threshold: int = 2) -> bool:
    """Return True if 2+ field values in the row match known column header synonyms."""
    matches = sum(
        1 for key in CANONICAL_COLUMNS
        if canonicalize_header(str(row.get(key) or "")) is not None
    )
    return matches >= threshold


def canonicalize_file(item, column_swaps=None):
    """Convert one file record into a list of canonical FOI row dicts.

    Returns (results, errors, header_rows_dropped).
    """
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
        if canonical and canonical not in canonical_to_col_idx:
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

    missing_required = sorted(k for k in REQUIRED_COLUMNS if k not in canonical_to_col_idx)
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
    for row in rows[header_row_idx + 1:]:
        if not row:
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
        # Root Cause C: rows more than one cell longer than the header cannot be
        # reliably realigned (e.g. DEASP 2017 8-col sub-table pages vs 6-col header).
        # Drop and log rather than emit a record with misaligned field values.
        elif len(row) > len(headers) + 1:
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

        # Root Cause B: drop rows where pdfplumber split a multi-word description
        # ("Request For Personal Information") across columns — every cell holds one word.
        req_desc = record.get("request_description")
        if req_desc and isinstance(req_desc, str) and req_desc.strip().lower() == "request":
            continue

        if missing_required:
            record["missing_columns"] = missing_required
        results.append(record)

    return results, errors, header_rows_dropped


def process(input_data, results_out, errors_out, column_swaps=None, verbose=False):
    total_dropped = 0
    for item in input_data["results"]:
        if item.get("rows") is None:
            continue
        file_records, file_errors, dropped = canonicalize_file(item, column_swaps)
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
    header_rows_dropped = process(input_data, results, errors, column_swaps=column_swaps, verbose=args.verbose)

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
