#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_status, IncrementalWriter

STEP_NAME = "filter_phantom_rows"

# Ratio of multi-value data rows below which a file is treated as having a
# "sparse layout" (its shape, not fragmentation) rather than leaked splits.
# See the guard in _merge_continuation_rows for the derivation. Shared with
# eval/evaluate.py so the eval's leak detection matches the step's own guard.
MULTI_ROW_TOLERANCE = 0.1


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
    cell text wraps. A continuation row has exactly 1 non-blank cell across >= 3
    columns; its string value is appended (with a space) to the same column in
    the preceding row. Returns (rows, n_merged).

    Blank means None *or* an empty/whitespace string — pdfplumber uses both
    sentinels interchangeably, often within one file (see _is_blank_cell).
    """
    if not rows or max(len(r) for r in rows) < 3:
        return rows, 0

    # Sparse-layout guard: if >50% of data rows are single-value rows AND
    # multi-value rows are rare (not just "none"), this is the file's shape
    # (not fragmentation). Merging would collapse distinct records. Files with
    # continuation rows will have a substantial fraction of rows with 2+ non-None cells.
    data_rows = rows[1:]
    if data_rows:
        single = sum(
            1 for r in data_rows
            if len(r) >= 3 and sum(1 for c in r if c is not None) == 1
        )
        multi = sum(
            1 for r in data_rows
            if len(r) >= 3 and sum(1 for c in r if c is not None) >= 2
        )
        # Ratio-based (not exact-zero) multi-row check: an exact `multi == 0` guard is
        # too brittle — a single incidental multi-value row in an otherwise sparse file
        # (e.g. 19 single-value rows + 1 multi-value row) would fully disable the guard
        # and chain-collapse the whole file. Constraining ratios from the test suite:
        #   test_merge_continuation_rows_consecutive:            multi/len = 1/3  = 0.333 (guard must NOT fire)
        #   test_merge_continuation_rows_does_not_corrupt_header: multi/len = 1/4  = 0.25  (guard must NOT fire)
        #   test_merge_skips_sparse_layout_files:                 multi/len = 0/4  = 0.0   (guard must fire)
        #   test_merge_skips_sparse_layout_with_one_incidental_multi_row: multi/len = 1/20 = 0.05 (guard must fire)
        # A threshold of 0.1 satisfies 0.05 < 0.1 <= 0.25, keeping all four cases correct.
        #
        # NOTE: this guard deliberately counts `is not None` while the merge loop below
        # is blank-aware. The 0.1 threshold was calibrated against None-only ratios;
        # switching the guard to _is_blank_cell shifts every ratio and re-fires the
        # guard on files that do need merging (measured: +9 files fully skipped,
        # orphan fragments 5,006 -> 7,088 across the PDF corpus). Retuning the
        # threshold is a separate, evidence-backed change — do not "tidy" this to
        # match the loop without re-deriving the constant.
        if single / len(data_rows) > 0.5 and multi / len(data_rows) < MULTI_ROW_TOLERANCE:
            return rows, 0  # sparse layout is this file's shape, not fragmentation

    merged = 0
    out = [list(rows[0])]
    for row in rows[1:]:
        # Blank-aware: pdfplumber emits a mix of None and '' for empty cells within
        # the same file, so a None-only count reads a continuation row as multi-value
        # and lets it survive as an orphan fragment.
        non_blank = [(i, v) for i, v in enumerate(row) if not _is_blank_cell(v)]
        if len(row) >= 3 and len(non_blank) == 1:
            col_idx, val = non_blank[0]
            prev = out[-1]
            if len(out) > 1 and col_idx < len(prev) and isinstance(val, str):
                if isinstance(prev[col_idx], str) and prev[col_idx].strip():
                    prev[col_idx] = prev[col_idx] + " " + val
                    merged += 1
                    continue
                if _is_blank_cell(prev[col_idx]):
                    prev[col_idx] = val
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
