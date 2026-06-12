#!/usr/bin/env python3
"""Profile header columns across all extracted disclosure files.

Reads output.json and emits a CSV of unique column header texts,
occurrence count, and the first file_url where each header appears.
Uses header_row_idx to find the correct header row (skips preamble rows).
Skips records with no rows, null header_row_idx, or non-FOI file URLs.

Usage:
    cd foi_pipeline
    uv run python steps/extract_disclosures_detect_header_row/profile_columns.py
    uv run python steps/extract_disclosures_detect_header_row/profile_columns.py --output columns.csv
    uv run python steps/extract_disclosures_detect_header_row/profile_columns.py --input path/to/other.json
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def profile(input_path: Path) -> list[dict]:
    data = json.loads(input_path.read_text())
    results = data.get("results", [])

    seen: dict[str, dict] = {}  # normalised header → {raw, count, first_url}

    for record in results:
        file_url = record.get("file_url", "")
        if "foi" not in file_url.lower():
            continue
        rows = record.get("rows")
        header_row_idx = record.get("header_row_idx")
        if not rows or header_row_idx is None:
            continue
        header_row = rows[header_row_idx]
        if not header_row:
            continue

        for cell in header_row:
            if cell is None:
                continue
            raw = re.sub(r'\s+', ' ', str(cell).strip())
            raw = re.sub(r'[:.]+$', '', raw).strip()
            raw = raw.replace('_', ' ')
            raw = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', raw)
            if not raw:
                continue
            key = raw.lower()
            if key not in seen:
                seen[key] = {"header": raw, "count": 0, "first_url": file_url}
            seen[key]["count"] += 1

    def _is_valid(header):
        if len(header) <= 2:
            return False
        if len(header) > 50:
            return False
        if not any(c.isalpha() for c in header):
            return False
        if sum(1 for w in header.split() if len(w) == 1) >= 3:
            return False
        return True

    rows = [r for r in seen.values() if _is_valid(r["header"])]
    return sorted(rows, key=lambda r: (-r["count"], r["header"].lower()))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--input",
        default=Path(__file__).parent / "output.json",
        type=Path,
        help="Path to extract_disclosures_detect_header_row output.json",
    )
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Write CSV to this path instead of stdout",
    )
    args = parser.parse_args()

    rows = profile(args.input)

    out = open(args.output, "w", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=["count", "header", "first_url"])
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()

    if args.output:
        print(f"Wrote {len(rows)} unique headers to {args.output}")
    else:
        print(f"\n({len(rows)} unique headers)", file=sys.stderr)


if __name__ == "__main__":
    main()
