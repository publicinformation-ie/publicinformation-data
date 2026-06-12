#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status, IncrementalWriter
from lib.text_utils import normalize_cell

STEP_NAME = "normalize_disclosure_cells"

_CID_RE = re.compile(r'\(cid:\d+\)')
_MULTI_SPACE_RE = re.compile(r' {2,}')


def _merge_continuation_rows(rows):
    """Merge PDF continuation rows into their preceding row.

    pdfplumber sometimes splits a single table row across two physical rows when
    cell text wraps. A continuation row has exactly 1 non-None cell across >= 3
    columns; its string value is appended (with a space) to the same column in
    the preceding row. Non-string values in the continuation position are kept
    as separate rows.
    """
    if not rows or max(len(r) for r in rows) < 3:
        return rows
    out = [list(rows[0])]
    for row in rows[1:]:
        non_none = [(i, v) for i, v in enumerate(row) if v is not None]
        if len(row) >= 3 and len(non_none) == 1:
            col_idx, val = non_none[0]
            prev = out[-1]
            if col_idx < len(prev) and isinstance(prev[col_idx], str) and isinstance(val, str):
                prev[col_idx] = prev[col_idx] + " " + val
                continue
        out.append(list(row))
    return out


def _prune_null_columns(rows):
    """Remove all-None columns from extracted PDF rows.

    Drops any column index where every row has None at that position (and the
    column is present in all rows). Jagged rows are left untouched.
    """
    if not rows:
        return rows
    ncols = max(len(r) for r in rows)
    to_drop = {
        col for col in range(ncols)
        if all(col < len(row) and row[col] is None for row in rows)
    }
    if not to_drop:
        return rows
    return [[v for i, v in enumerate(row) if i not in to_drop] for row in rows]


def _normalize_cell(file_type, value):
    """Normalize a single cell value. Delegates to shared utility.
    
    Maintains backward compatibility by tracking which rules were applied.
    """
    if not isinstance(value, str):
        return value, []

    rules = []
    result = value

    if file_type == "pdf":
        new = _CID_RE.sub("", result)
        if new != result:
            rules.append("cid_stripped")
            result = new

        new = result.replace("\n", " ").replace("\r", " ")
        if new != result:
            rules.append("newline_to_space")
            result = new

        new = _MULTI_SPACE_RE.sub(" ", result)
        if new != result:
            rules.append("collapse_spaces")
            result = new

    new = result.strip()
    if new != result:
        rules.append("strip_whitespace")
        result = new

    # Verify we produce the same output as the shared utility
    assert result == normalize_cell(value, file_type=file_type)

    return result, rules


def process(input_data, step_dir, writer, force=False, verbose=False):
    changes_path = Path(step_dir) / "changes.json"

    if not force and changes_path.exists():
        try:
            changes = read_json(changes_path)
        except Exception:
            changes = []
    else:
        changes = []

    write_json(changes_path, changes)

    for item in input_data["results"]:
        file_url = item["file_url"]
        if writer.is_processed(file_url):
            continue

        file_type = item.get("file_type", "")
        rows = item.get("rows")

        if rows is None:
            writer.append([{**item}])
            if verbose:
                print(".", end="", flush=True)
            continue

        normalized_rows = []
        for row_idx, row in enumerate(rows):
            normalized_row = []
            for col_idx, cell in enumerate(row):
                normalized, rules = _normalize_cell(file_type, cell)
                normalized_row.append(normalized)
                if rules:
                    changes.append({
                        "file_url": file_url,
                        "file_type": file_type,
                        "row_idx": row_idx,
                        "col_idx": col_idx,
                        "rules_applied": rules,
                        "before": cell,
                        "after": normalized,
                    })
            normalized_rows.append(normalized_row)

        if file_type == "pdf":
            normalized_rows = _merge_continuation_rows(normalized_rows)
            normalized_rows = _prune_null_columns(normalized_rows)

        write_json(changes_path, changes)
        writer.append([{**item, "rows": normalized_rows}])

        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize cell values in extracted disclosure log data"
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

    process(input_data, step_dir, writer, force=args.force, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
