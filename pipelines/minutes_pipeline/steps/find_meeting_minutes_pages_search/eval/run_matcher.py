#!/usr/bin/env python3
"""Reproduce minutes-page discovery URLs offline and write matcher_output.json.

Crawl leg is reproduced: find_minutes_link over fixtures/home/<key>.html.
Search leg is NOT reproduced offline (Apify results are not persisted by the
step): on a crawl miss the live search output.json URL is copied and marked
source_method="apify" so the eval still scores the final URL end to end.
Fully offline — no network.

Usage (from minutes_pipeline/):
    uv run python steps/find_meeting_minutes_pages_search/eval/run_matcher.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_STEP_DIR = _HERE.parent
_MINUTES_PIPELINE = _HERE.parents[2]
_REPO_ROOT = _MINUTES_PIPELINE.parents[1]
sys.path.insert(0, str(_MINUTES_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from steps.find_meeting_minutes_pages.process import find_minutes_link  # noqa: E402

from capture_fixtures import fixture_key  # noqa: E402

FIXTURES_HOME = _HERE / "fixtures" / "home"
OUT = _HERE / "matcher_output.json"


def build_records(home_by_key, authorities_by_id, live_by_key):
    """Pure core: map fixture keys to final-URL records."""
    records = []
    for key, home_html in home_by_key.items():
        bid_str, _, _slug = key.partition("__")
        bid = int(bid_str)
        auth = authorities_by_id.get(bid, {})
        website = auth.get("official_website_url", "")
        name = auth.get("name", "")
        match = find_minutes_link(home_html or "", website) if website else None
        if match:
            url, _score = match
            method = "crawl"
        else:
            url = live_by_key.get((bid, ""))
            method = "apify"
        if not url:
            continue
        records.append({
            "public_body_id": bid,
            "municipal_district": None,
            "minutes_page_url": url,
            "source_method": method,
            "name": name,
        })
    return records


def main():
    import csv
    with open(_HERE / "labels.csv", newline="") as f:
        labels = [r for r in csv.DictReader(f) if r.get("has_log")]
    authorities = {int(a["public_body_id"]): a for a in json.loads(
        (_MINUTES_PIPELINE / "steps" / "find_local_authorities" / "output.json").read_text()
    )["results"]}
    live = {}
    live_path = _STEP_DIR / "output.json"
    if live_path.exists():
        for r in json.loads(live_path.read_text())["results"]:
            if r.get("municipal_district") is None:
                live[(r["public_body_id"], "")] = r.get("minutes_page_url", "")
    home_by_key = {}
    skipped = 0
    for row in labels:
        if row["municipal_district"]:
            continue  # district pages are crawl-only overrides; covered by pages fixtures
        key = fixture_key(row["public_body_id"], None)
        path = FIXTURES_HOME / f"{key}.html"
        if not path.exists():
            skipped += 1
            continue
        home_by_key[key] = path.read_text(encoding="utf-8")
    records = build_records(home_by_key, authorities, live)
    OUT.write_text(json.dumps({
        "metadata": {"step": "find_meeting_minutes_pages_search_matcher_eval",
                     "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": records,
    }, indent=2))
    msg = f"Wrote {len(records)} matcher results to {OUT}"
    if skipped:
        msg += f" ({skipped} keys skipped — no home fixture)"
    print(msg)


if __name__ == "__main__":
    main()
