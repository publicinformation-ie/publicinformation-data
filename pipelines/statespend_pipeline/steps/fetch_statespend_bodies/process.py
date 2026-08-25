#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_statespend_bodies"
API_URL = "https://statespend.ie/api/rank"
BASE_BODY_URL = "https://statespend.ie/body"
PAGE_SIZE = 500
# statespend.ie served 217 bodies on 2026-08-25. The id space is dense and
# unversioned, so do NOT pin an exact count (a benign upstream change must not
# fatal) — but a collapse far below the known population means the API shape
# changed and the run should stop loudly.
MIN_BODY_COUNT = 200


def fetch_page(offset: int) -> list:
    """Fetch one page of the /api/rank body list. Fatal-exits on request
    failure, non-JSON, or an unexpected payload shape — same guard style as
    fetch_datagovie_orgs."""
    url = f"{API_URL}?dim=bodies&metric=count&limit={PAGE_SIZE}&offset={offset}"
    try:
        response = fetch("GET", url)
    except Exception as e:
        print(f"Fatal: request to statespend.ie failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not response.ok:
        print(f"Fatal: statespend.ie returned HTTP {response.status_code}", file=sys.stderr)
        sys.exit(1)

    try:
        payload = response.json()
    except ValueError as e:
        print(f"Fatal: could not parse statespend.ie response as JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(payload, list):
        print(f"Fatal: unexpected /api/rank payload (expected a list, got "
              f"{type(payload).__name__})", file=sys.stderr)
        sys.exit(1)

    return payload


def build_record(row: dict) -> dict:
    """`label` is statespend's display name at rank level; `label_raw` /
    `display_name` only exist on the per-body /api/body/{id} endpoint and are
    optional enrichment, deliberately not fetched here."""
    sid = row["id"]
    return {
        "statespend_id": sid,
        "statespend_name": row["label"],
        "statespend_entity_type": row.get("entity_type"),
        "statespend_url": f"{BASE_BODY_URL}/{sid}",
    }


def fetch_bodies() -> list:
    """Paginate /api/rank until exhausted. Fatal-exits if fewer than
    MIN_BODY_COUNT bodies come back, or on duplicate ids (which would mean
    the dense-id assumption behind IncrementalWriter keys broke)."""
    records = []
    offset = 0
    while True:
        page = fetch_page(offset)
        records.extend(build_record(r) for r in page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    if len(records) < MIN_BODY_COUNT:
        print(f"Fatal: fetched only {len(records)} bodies from statespend.ie "
              f"(minimum expected {MIN_BODY_COUNT}) — API shape likely changed",
              file=sys.stderr)
        sys.exit(1)

    ids = [r["statespend_id"] for r in records]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        print(f"Fatal: duplicate statespend ids returned by /api/rank: {dupes}",
              file=sys.stderr)
        sys.exit(1)

    return records


def main():
    parser = argparse.ArgumentParser(
        description="Fetch statespend.ie's public-body list via its internal JSON API"
    )
    parser.add_argument("--input", required=True,
                        help="Previous step output (unused — first step in pipeline)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    records = fetch_bodies()

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "source_api": API_URL,
        },
        "results": records,
    }
    write_json(output_path, output)
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} statespend.ie body records to {output_path}")


if __name__ == "__main__":
    main()
