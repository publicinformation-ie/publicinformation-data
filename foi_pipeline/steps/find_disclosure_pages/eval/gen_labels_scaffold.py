#!/usr/bin/env python3
"""
Seed eval/labels.csv from three sources, in priority order:
  1. override.json          -> label=distinct_log, expected=disclosure_page_url (verified)
  2. ground-truth CSV       -> label=distinct_log, expected=source_page_url (verified, gov.ie)
  3. current output.json     -> label=UNVERIFIED, expected=disclosure_page_url

Rows from sources 1-2 are marked verified=yes. Source 3 rows are verified=no:
a human must inspect each and set label to one of distinct_log / use_foi_page /
no_log_exists and correct expected_url. The slug usually makes this obvious
(foi-disclosure-log -> distinct_log; login/logo/geology -> use_foi_page).

Usage (from foi_pipeline/):
    uv run python steps/find_disclosure_pages/eval/gen_labels_scaffold.py
"""
import csv
import json
from pathlib import Path

STEP_DIR = Path(__file__).parent.parent
DATA_DIR = STEP_DIR.parent.parent / "data"
OUT = Path(__file__).parent / "labels.csv"


def main():
    rows = {}  # public_body_id -> dict

    # Source 3 (lowest priority): current output, unverified.
    output = json.loads((STEP_DIR / "output.json").read_text())
    for r in output["results"]:
        pid = str(r["public_body_id"])
        distinct = r["disclosure_page_url"].rstrip("/") != r["foi_page_url"].rstrip("/")
        rows[pid] = {
            "public_body_id": pid,
            "name": r.get("name", ""),
            "label": "distinct_log" if distinct else "use_foi_page",
            "expected_url": r["disclosure_page_url"] if distinct else "",
            "verified": "no",
        }

    # Source 2: ground-truth CSV (gov.ie), verified.
    gt = DATA_DIR / "public_body_foi_disclosure_files.csv"
    seen = set()
    with open(gt, newline="") as f:
        for row in csv.DictReader(f):
            pid = str(row["public_body_id"])
            if pid in seen:
                continue
            seen.add(pid)
            rows[pid] = {
                "public_body_id": pid,
                "name": row["public_body_name"],
                "label": "distinct_log",
                "expected_url": row["source_page_url"],
                "verified": "yes",
            }

    # Source 1 (highest priority): manual overrides, verified.
    overrides = json.loads((STEP_DIR / "override.json").read_text())
    for o in overrides:
        pid = str(o["public_body_id"])
        distinct = o["disclosure_page_url"].rstrip("/") != o["foi_page_url"].rstrip("/")
        rows[pid] = {
            "public_body_id": pid,
            "name": o.get("name", ""),
            "label": "distinct_log" if distinct else "use_foi_page",
            "expected_url": o["disclosure_page_url"] if distinct else "",
            "verified": "yes",
        }

    fields = ["public_body_id", "name", "label", "expected_url", "verified"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for pid in sorted(rows, key=int):
            w.writerow(rows[pid])

    verified = sum(1 for r in rows.values() if r["verified"] == "yes")
    print(f"Wrote {len(rows)} rows to {OUT} ({verified} verified, {len(rows) - verified} need manual review)")


if __name__ == "__main__":
    main()
