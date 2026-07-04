#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "filter_phantom_rows"


def _is_blank_cell(cell) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip())


def _drop_blank_rows(rows):
    """Remove rows with no real content in any cell (all file types).

    Blank rows come from empty spreadsheet rows (xlsx/csv) and from PDF
    extraction artifacts. Returns (kept_rows, dropped_indices).
    """
    kept, dropped = [], []
    for i, row in enumerate(rows):
        if row and not all(_is_blank_cell(c) for c in row):
            kept.append(row)
        else:
            dropped.append(i)
    return kept, dropped


def _merge_continuation_rows(rows):
    """Merge PDF continuation rows into their preceding row.

    pdfplumber sometimes splits a single table row across two physical rows when
    cell text wraps. A continuation row has exactly 1 non-None cell across >= 3
    columns; its string value is appended (with a space) to the same column in
    the preceding row. Returns (rows, n_merged).
    """
    if not rows or max(len(r) for r in rows) < 3:
        return rows, 0
    merged = 0
    out = [list(rows[0])]
    for row in rows[1:]:
        non_none = [(i, v) for i, v in enumerate(row) if v is not None]
        if len(row) >= 3 and len(non_none) == 1:
            col_idx, val = non_none[0]
            prev = out[-1]
            if len(out) > 1 and col_idx < len(prev) and isinstance(prev[col_idx], str) and isinstance(val, str):
                prev[col_idx] = prev[col_idx] + " " + val
                merged += 1
                continue
        out.append(list(row))
    return out, merged


def _prune_null_columns(rows):
    """Remove all-None columns from extracted PDF rows. Returns (rows, n_pruned)."""
    if not rows:
        return rows, 0
    ncols = max(len(r) for r in rows)
    to_drop = {
        col for col in range(ncols)
        if all(col < len(row) and row[col] is None for row in rows)
    }
    if not to_drop:
        return rows, 0
    return [[v for i, v in enumerate(row) if i not in to_drop] for row in rows], len(to_drop)


def process(input_data, writer, verbose=False):
    for item in input_data["results"]:
        file_url = item["file_url"]
        if writer.is_processed(file_url):
            continue

        rows = item.get("rows")
        if rows is None:
            writer.append([{**item}])
            if verbose:
                print(".", end="", flush=True)
            continue

        stats = {}
        if item.get("file_type") == "pdf":
            rows, merged = _merge_continuation_rows(rows)
            if merged:
                stats["fragments_merged"] = merged
        rows, dropped = _drop_blank_rows(rows)
        if dropped:
            stats["blank_rows_dropped"] = len(dropped)
        if item.get("file_type") == "pdf":
            rows, pruned = _prune_null_columns(rows)
            if pruned:
                stats["null_columns_pruned"] = pruned

        out = {**item, "rows": rows}
        if stats:
            out["filter_stats"] = stats
        writer.append([out])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Drop blank rows and merge wrapped-cell fragments (phantom-row filter)"
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

    process(input_data, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
