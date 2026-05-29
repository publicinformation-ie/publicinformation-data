#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status, IncrementalWriter
from scripts.text_utils import normalize_cell

STEP_NAME = "extract_disclosures_detect_header_row"


def detect_header_row(rows, max_look_ahead=5):
    """Return index of the first row with 2+ non-null, non-empty cells.
    
    Normalizes cells (especially PDF cells with newlines) before counting
    to ensure consistent detection regardless of PDF extraction artefacts.
    """
    for idx, row in enumerate(rows[:max_look_ahead]):
        # Normalize each cell for consistent counting
        normalized_row = [
            normalize_cell(v) if v else v
            for v in row
        ]
        non_empty = [v for v in normalized_row if v is not None and v != ""]
        if len(non_empty) >= 2:
            return idx
    return 0


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for item in input_data["results"]:
        file_url = item["file_url"]
        if writer.is_processed(file_url):
            continue

        rows = item.get("rows")
        if rows is None:
            writer.append([{**item, "header_row_idx": None}])
            if verbose:
                print(".", end="", flush=True)
            continue

        header_row_idx = detect_header_row(rows)
        writer.append([{**item, "header_row_idx": header_row_idx}])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Detect header row index in disclosure log row data"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    writer = IncrementalWriter(
        output_path, STEP_NAME, key_field="file_url", force=args.force,
        override_path=override_path,
        upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
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
