#!/usr/bin/env python3
"""
Seed eval/labels.csv from two sources, in priority order:
  1. Known verified results from the manual 47-body experiment that this
     step's design was based on (see docs/superpowers/specs/2026-07-24-find-
     foi-email-pages-design.md) — looked up by name against
     find_public_bodies/output.json so ids are never hardcoded from memory
     ([[feedback_verify_override_ids]]).
  2. Current output.json — every other body this step attempted, marked
     UNVERIFIED for a human to inspect and confirm no_email_exists vs.
     should_have_found (page content changed, or scorer missed a valid link).

Usage (from foi_pipeline/):
    uv run python steps/find_foi_email_pages/eval/gen_labels_scaffold.py
"""
import csv
import json
from pathlib import Path

STEP_DIR = Path(__file__).parent.parent
PIPELINE_DIR = STEP_DIR.parent.parent
OUT = Path(__file__).parent / "labels.csv"

# name substring (case-insensitive) -> (label, expected_email)
# From the 2026-07-24 manual experiment: 5 reliable foi-keyword hits + 4
# confirmed-wrong link-scorer matches.
KNOWN_RESULTS = [
    ("Courts Service", "found", "foi@courts.ie"),
    ("Dublin City University", "found", "foi@dcu.ie"),
    ("National Asset Management Agency", "found", "foi@nama.ie"),
    ("Central Bank of Ireland", "found", "foi@centralbank.ie"),
    ("St. Vincent's University Hospital", "found", "foi@sivuh.ie"),
    ("Cork City Council", "wrong_match", ""),
    ("Louth County Council", "wrong_match", ""),
    ("Offaly County Council", "wrong_match", ""),
    ("Quality and Qualifications Ireland", "wrong_match", ""),
]


def _find_body_id(bodies, name_substring):
    matches = [b for b in bodies if name_substring.lower() in b.get("name", "").lower()]
    if len(matches) != 1:
        print(f"  WARNING: {len(matches)} match(es) for '{name_substring}' — skipping")
        return None
    return matches[0]["public_body_id"], matches[0]["name"]


def main():
    bodies_path = PIPELINE_DIR / "steps" / "find_public_bodies" / "output.json"
    bodies = json.loads(bodies_path.read_text()).get("public_bodies", [])

    rows = {}
    for name_substring, label, expected_email in KNOWN_RESULTS:
        found = _find_body_id(bodies, name_substring)
        if found is None:
            continue
        pid, name = found
        rows[str(pid)] = {
            "public_body_id": str(pid),
            "name": name,
            "label": label,
            "expected_url": expected_email,
            "verified": "yes",
        }

    output = json.loads((STEP_DIR / "output.json").read_text())
    for r in output["results"]:
        pid = str(r["public_body_id"])
        if pid in rows:
            continue  # known result takes priority
        if r.get("email_status") != "not_found" and "confidence" not in r:
            continue  # untouched pass-through record, not in scope for this eval
        rows[pid] = {
            "public_body_id": pid,
            "name": r.get("name", ""),
            "label": "UNVERIFIED",
            "expected_url": r.get("foi_email") or "",
            "verified": "no",
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
