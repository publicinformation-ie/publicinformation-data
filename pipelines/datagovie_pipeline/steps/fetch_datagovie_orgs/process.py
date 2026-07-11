#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_datagovie_orgs"
API_URL = "https://data.gov.ie/api/3/action/organization_list?all_fields=true"
BASE_ORG_URL = "https://data.gov.ie/organization"


def filter_orgs(raw_orgs: list) -> list:
    """Keep only active organisations. The same CKAN endpoint can also
    return non-organization groups and deleted/draft orgs, both of which
    are excluded here."""
    return [o for o in raw_orgs if o.get("type") == "organization" and o.get("state") == "active"]


def build_record(org: dict) -> dict:
    """display_name is used rather than title, because title is sometimes
    empty (e.g. org "3d" has title: "") while display_name is always
    populated."""
    slug = org["name"]
    return {
        "datagovie_slug": slug,
        "datagovie_name": org["display_name"],
        "datagovie_url": f"{BASE_ORG_URL}/{slug}",
        "datagovie_package_count": org.get("package_count", 0),
    }


def fetch_orgs() -> list:
    """Fetch and parse the CKAN organization_list response. Fatal-exits
    on request failure, a non-true `success` field, or zero returned
    records after filtering — same guard style as parse_wdw_bodies's
    first-step-in-pipeline HTML parse."""
    try:
        response = fetch("GET", API_URL)
    except Exception as e:
        print(f"Fatal: request to data.gov.ie failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not response.ok:
        print(f"Fatal: data.gov.ie returned HTTP {response.status_code}", file=sys.stderr)
        sys.exit(1)

    try:
        payload = response.json()
    except ValueError as e:
        print(f"Fatal: could not parse data.gov.ie response as JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not payload.get("success"):
        print(f"Fatal: data.gov.ie API reported success=false: {payload}", file=sys.stderr)
        sys.exit(1)

    raw_orgs = payload.get("result", [])
    active_orgs = filter_orgs(raw_orgs)

    if not active_orgs:
        print("Fatal: fetched 0 active organisations from data.gov.ie", file=sys.stderr)
        sys.exit(1)

    return [build_record(o) for o in active_orgs]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch data.gov.ie's organisation list via its CKAN API"
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

    records = fetch_orgs()

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "datagovie_orgs": records,
    }
    write_json(output_path, output)
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} data.gov.ie org records to {output_path}")


if __name__ == "__main__":
    main()
