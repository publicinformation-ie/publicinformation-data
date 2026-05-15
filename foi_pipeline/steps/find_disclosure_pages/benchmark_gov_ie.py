#!/usr/bin/env python3
"""
Benchmark _find_gov_ie against the 18 known-correct gov.ie disclosure page URLs.

Usage (from repo root):
    cd foi_pipeline && python steps/find_disclosure_pages/benchmark_gov_ie.py

Requires SERPER_API_KEY to be set in the environment.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "foi_pipeline"))

from steps.find_disclosure_pages.domains import _find_gov_ie

STEP_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent.parent / "foi_pipeline" / "data"

CSV_PATH = DATA_DIR / "public_body_foi_disclosure_files.csv"
OUTPUT_PATH = STEP_DIR / "output.json"


def load_ground_truth():
    """Returns {public_body_id: (name, expected_disclosure_url)} for gov.ie bodies."""
    seen = {}
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            source = row["source_page_url"]
            if "gov.ie" not in source:
                continue
            pid = row["public_body_id"]
            if pid not in seen:
                seen[pid] = (row["public_body_name"], source)
    return seen


def load_foi_urls():
    """Returns {public_body_id: foi_page_url} from output.json."""
    data = json.loads(OUTPUT_PATH.read_text())
    return {str(r["public_body_id"]): r["foi_page_url"] for r in data["results"]}


def main():
    ground_truth = load_ground_truth()
    foi_urls = load_foi_urls()

    correct = wrong = missing_foi = none_returned = 0

    for pid, (name, expected_url) in sorted(ground_truth.items()):
        foi_url = foi_urls.get(pid)
        if foi_url is None:
            print(f"  SKIP  [{pid}] {name[:50]} — not in output.json")
            missing_foi += 1
            continue

        actual_url = _find_gov_ie(name, foi_url)

        if actual_url is None:
            status = "NONE "
            none_returned += 1
        elif actual_url == expected_url:
            status = "OK   "
            correct += 1
        else:
            status = "WRONG"
            wrong += 1

        print(f"  {status} [{pid}] {name[:50]}")
        if actual_url and actual_url != expected_url:
            print(f"         expected: {expected_url}")
            print(f"         got:      {actual_url}")

    total = len(ground_truth)
    print(f"\nResults: {correct}/{total} correct, {wrong} wrong, {none_returned} None, {missing_foi} skipped")


if __name__ == "__main__":
    main()
