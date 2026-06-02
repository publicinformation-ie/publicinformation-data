#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.cli_utils import add_common_args, filter_by_public_body, merge_replacing_body
from scripts.file_utils import read_json, write_json, write_status
from steps.extract_disclosures_canonicalize.column_map import (
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
    canonicalize_headers,
)

STEP_NAME = "extract_disclosures_canonicalize"


def canonicalize_file(item):
    """Convert one file record into a list of canonical FOI row dicts.

    Returns (results, errors) — errors are dicts ready for errors.json.
    """
    rows = item.get("rows")
    header_row_idx = item.get("header_row_idx")
    if rows is None:
        return [], []

    if header_row_idx is None or header_row_idx >= len(rows):
        return [], []

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
        }]

    missing_required = sorted(k for k in REQUIRED_COLUMNS if k not in canonical_to_col_idx)

    results = []
    for row in rows[header_row_idx + 1:]:
        if not row:
            continue
        record = {**meta}
        for key in CANONICAL_COLUMNS:
            if key in canonical_to_col_idx:
                col_idx = canonical_to_col_idx[key]
                record[key] = row[col_idx] if col_idx < len(row) else None
            else:
                record[key] = None
        if missing_required:
            record["missing_columns"] = missing_required
        results.append(record)

    return results, []


def process(input_data, results_out, errors_out, verbose=False):
    for item in input_data["results"]:
        if item.get("rows") is None:
            continue
        file_records, file_errors = canonicalize_file(item)
        results_out.extend(file_records)
        errors_out.extend(file_errors)
        if verbose:
            print(".", end="", flush=True)


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

    process(input_data, results, errors, verbose=args.verbose)

    if args.public_body is not None and not args.force and output_path.exists():
        existing = read_json(output_path).get("results", [])
        results = merge_replacing_body(existing, results, args.public_body)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
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
