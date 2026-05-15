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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    step_dir = Path(__file__).parent
    override_path = step_dir / "override.json"

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="file_url", force=args.force,
                               override_path=override_path,
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json")
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Stub: wrote {count} results to {output_path}")


if __name__ == "__main__":
    main()
