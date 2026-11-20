#!/usr/bin/env python3
"""Fetch the Department of Public Expenditure's public service numbers CSV
and keep the rows for its most recent quarter.

The source gives the body name at an inconsistent depth: agencies carry it in
Level_6, but civil service offices, local authorities and the education/health
aggregates leave Level_6 empty and carry it in Level_5. `source_name` is
Level_6 when present, else Level_5 -- nothing more. Resolving it to a canonical
public body is match_public_bodies' job.
"""
import argparse
import csv
import hashlib
import io
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lib.file_utils import append_error, write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_staff_numbers"
SOURCE_URL = "https://databank.per.gov.ie/OpenData/Open%20Data%20PS%20Numbers%20Source.csv"
EXPECTED_COLUMNS = ["Year", "Quarter", "Level_1", "Level_2", "Level_3",
                    "Level_4", "Level_5", "Level_6", "FTE"]
_QUARTER_RE = re.compile(r"^Qtr\s*([1-4])$", re.IGNORECASE)


def parse_fte(text: str):
    """'3,960.56' -> 3960.56. Returns None when the cell is not a plain
    non-negative number; the caller logs that rather than guessing."""
    cleaned = (text or "").strip().replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return float(value)


def parse_quarter(text: str):
    m = _QUARTER_RE.match((text or "").strip())
    return int(m.group(1)) if m else None


def read_source(raw: bytes) -> list:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != EXPECTED_COLUMNS:
        raise ValueError(f"unexpected columns {reader.fieldnames!r}; expected {EXPECTED_COLUMNS!r}")
    return list(reader)


def latest_period(rows: list):
    periods = set()
    for r in rows:
        q = parse_quarter(r["Quarter"])
        if q is None or not r["Year"].strip().isdigit():
            raise ValueError(f"unparseable period {r['Year']!r} {r['Quarter']!r}")
        periods.add((int(r["Year"]), q))
    if not periods:
        raise ValueError("source has no rows")
    return max(periods)


def build_records(rows: list, year: int, quarter: int, source_url: str, step_dir=None) -> list:
    """Records for one period. Duplicate source keys are fatal: a key that is
    not unique cannot carry a reviewed override safely."""
    records, seen = [], {}
    for r in rows:
        if (int(r["Year"]), parse_quarter(r["Quarter"])) != (year, quarter):
            continue
        levels = {f"level_{i}": r[f"Level_{i}"].strip() for i in range(1, 7)}
        source_name = levels["level_6"] or levels["level_5"]
        if not source_name:
            raise ValueError(f"row has neither Level_5 nor Level_6: {r!r}")
        source_key = " | ".join(p for p in (levels["level_4"], levels["level_5"], levels["level_6"]) if p)
        if source_key in seen:
            raise ValueError(f"duplicate source key {source_key!r}")
        fte = parse_fte(r["FTE"])
        if fte is None and step_dir is not None:
            append_error(step_dir, {
                "step": STEP_NAME, "error_type": "unparseable_fte",
                "error_message": f"FTE cell {r['FTE']!r} is not a plain number; fte left null",
                "context": {"source_key": source_key},
            })
        record = {"source_key": source_key, "year": year, "quarter": quarter,
                  "source_name": source_name, **levels, "fte": fte,
                  "source_url": source_url}
        seen[source_key] = record
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description="Fetch PER public service numbers (latest quarter)")
    parser.add_argument("--input", default=None, help="Unused (first step in pipeline)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body")
    parser.add_argument("--source", default=os.environ.get("STAFF_NUMBERS_SOURCE_FILE"),
                        help="Read this local copy of the CSV instead of downloading it "
                             "(default: $STAFF_NUMBERS_SOURCE_FILE, else download)")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    errors_path = step_dir / "errors.json"
    if errors_path.exists():
        errors_path.unlink()

    try:
        if args.source:
            raw = Path(args.source).read_bytes()
        else:
            response = fetch("GET", SOURCE_URL)
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status_code}")
            raw = response.content
        rows = read_source(raw)
        year, quarter = latest_period(rows)
        records = build_records(rows, year, quarter, SOURCE_URL, step_dir)
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "source_url": SOURCE_URL,
            "source_downloaded": not args.source,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_rows": len(rows),
            "year": year,
            "quarter": quarter,
        },
        "results": records,
    })
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} staff-number records for {year} Q{quarter} to {output_path}")


if __name__ == "__main__":
    main()
