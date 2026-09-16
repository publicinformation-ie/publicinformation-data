#!/usr/bin/env python3
"""Write labels.csv skeleton rows for hand-labelling.

One row per (body, district) pair from find_local_authorities/output.json.
expected_url is pre-filled from the live search output.json where present;
has_log/verified are left empty for the human labeller. Re-running keeps
already-filled has_log values (matched on public_body_id + district).

Run from minutes_pipeline/:
    uv run python steps/find_meeting_minutes_pages_search/eval/gen_labels_scaffold.py
"""
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_STEP_DIR = _HERE.parent
_MINUTES_PIPELINE = _HERE.parents[2]
sys.path.insert(0, str(_MINUTES_PIPELINE))

LABELS_CSV = _HERE / "labels.csv"
HEADER = ["public_body_id", "municipal_district", "name", "has_log", "expected_url", "verified"]


def _existing_labels():
    if not LABELS_CSV.exists():
        return {}
    with open(LABELS_CSV, newline="") as f:
        return {(r["public_body_id"], r["municipal_district"]): r
                for r in csv.DictReader(f)}


def main():
    authorities = json.loads(
        (_MINUTES_PIPELINE / "steps" / "find_local_authorities" / "output.json").read_text()
    )["results"]
    live = {}
    live_path = _STEP_DIR / "output.json"
    if live_path.exists():
        for r in json.loads(live_path.read_text())["results"]:
            live[(str(r["public_body_id"]), r.get("municipal_district") or "")] = \
                r.get("minutes_page_url", "")
    existing = _existing_labels()
    rows = []
    for auth in authorities:
        bid = str(auth["public_body_id"])
        districts = [None] + list(auth.get("municipal_districts", []))
        for district in districts:
            dkey = district or ""
            key = (bid, dkey)
            old = existing.get(key, {})
            rows.append({
                "public_body_id": bid,
                "municipal_district": dkey,
                "name": auth.get("name", "") + (f" ({district})" if district else ""),
                "has_log": old.get("has_log", ""),
                "expected_url": old.get("expected_url", "") or live.get(key, ""),
                "verified": old.get("verified", ""),
            })
    with open(LABELS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} skeleton rows to {LABELS_CSV}")


if __name__ == "__main__":
    main()
