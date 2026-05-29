#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "normalize_disclosure_cells"

_CID_RE = re.compile(r'\(cid:\d+\)')
_MULTI_SPACE_RE = re.compile(r' {2,}')


def _normalize_cell(file_type, value):
    """Normalize a single cell value. Returns (normalized_value, rules_applied).

    PDF: strip (cid:X) glyphs, replace newlines with spaces, collapse
    multi-spaces, then strip whitespace. XLSX/XLS: strip whitespace only.
    Non-string values pass through unchanged with an empty rules list.
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

        write_json(changes_path, changes)
        writer.append([{**item, "rows": normalized_rows}])

        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize cell values in extracted disclosure log data"
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

    process(input_data, step_dir, writer, force=args.force, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
