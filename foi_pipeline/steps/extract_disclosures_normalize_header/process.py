#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "extract_disclosures_normalize_header"
_CONTINUATION_NULL_THRESHOLD = 0.5  # row is a continuation if > 50% of cells are None
_MAX_CONTINUATION_ROWS = 3


def normalize_header_row(rows, header_row_idx, max_continuation_rows=_MAX_CONTINUATION_ROWS):
    """Repair null cells in the detected header row.

    Two repairs are applied in order:
    1. Continuation-row merge: high-null rows immediately after the header are
       merged into it (column values joined with a space), then removed from rows.
    2. Forward-fill: remaining None cells in the header are replaced with the
       nearest preceding non-None value (repairing PDF merged-cell spans).

    Returns (new_rows, header_row_idx) — header_row_idx is always unchanged.
    """
    if not rows or header_row_idx >= len(rows):
        return rows, header_row_idx

    header = list(rows[header_row_idx])
    ncols = len(header)

    # Step 1: detect and merge continuation rows
    continuation_end = header_row_idx + 1
    for i in range(header_row_idx + 1,
                   min(header_row_idx + 1 + max_continuation_rows, len(rows))):
        row = rows[i]
        if not row:
            break
        non_null = sum(1 for c in row if c is not None)
        null_fraction = 1 - (non_null / len(row))
        if null_fraction <= _CONTINUATION_NULL_THRESHOLD:
            break  # too many populated cells — this is real data
        for col_idx, cell in enumerate(row):
            if cell is not None and col_idx < ncols:
                if header[col_idx] is not None:
                    header[col_idx] = header[col_idx] + " " + str(cell)
                else:
                    header[col_idx] = str(cell)
        continuation_end = i + 1

    # Step 2: forward-fill None cells left-to-right
    last_val = None
    for i, cell in enumerate(header):
        if cell is not None:
            last_val = cell
        elif last_val is not None:
            header[i] = last_val

    new_rows = list(rows[:header_row_idx]) + [header] + list(rows[continuation_end:])
    return new_rows, header_row_idx


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for item in input_data["results"]:
        file_url = item["file_url"]
        if writer.is_processed(file_url):
            continue

        rows = item.get("rows")
        header_row_idx = item.get("header_row_idx")

        if rows is None or header_row_idx is None:
            writer.append([{**item}])
            if verbose:
                print(".", end="", flush=True)
            continue

        new_rows, new_idx = normalize_header_row(rows, header_row_idx)
        writer.append([{**item, "rows": new_rows, "header_row_idx": new_idx}])

        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize header rows: merge continuations and forward-fill nulls"
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
