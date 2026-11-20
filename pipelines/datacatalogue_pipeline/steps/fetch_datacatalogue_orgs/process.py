#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_datacatalogue_orgs"
API_URL = "https://datacatalogue.gov.ie/api/3/action/organization_list"
BASE_ORG_URL = "https://datacatalogue.gov.ie/organization"
# The CKAN instance caps organization_list?all_fields=true at 25 rows per
# request, whatever `limit` asks for, so the list must be paged.
PAGE_SIZE = 25
MAX_PAGES = 200  # safety stop against a source that never returns an empty page


def filter_orgs(raw_orgs: list) -> list:
    """Keep only active organisations; drops non-organization groups and
    deleted/draft entries."""
    return [o for o in raw_orgs if o.get("type") == "organization" and o.get("state") == "active"]


def build_record(org: dict) -> dict:
    """display_name is used rather than title, because title can be empty
    while display_name is always populated. Package count and description
    are included only where the source provides them."""
    slug = org["name"]
    record = {
        "datacatalogue_slug": slug,
        "datacatalogue_name": org["display_name"],
        "datacatalogue_url": f"{BASE_ORG_URL}/{slug}",
    }
    if org.get("package_count") is not None:
        record["datacatalogue_package_count"] = org["package_count"]
    description = (org.get("description") or "").strip()
    if description:
        record["datacatalogue_description"] = description
    return record


def _fatal(message: str):
    print(f"Fatal: {message}", file=sys.stderr)
    sys.exit(1)


def fetch_page(offset: int) -> list:
    """Fetch one page of the CKAN organization_list. Fatal-exits on request
    failure, HTTP error, unparseable JSON or success=false."""
    params = {"all_fields": "true", "limit": PAGE_SIZE, "offset": offset}
    try:
        response = fetch("GET", API_URL, params=params)
    except Exception as e:
        _fatal(f"request to datacatalogue.gov.ie failed: {e}")

    if not response.ok:
        _fatal(f"datacatalogue.gov.ie returned HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as e:
        _fatal(f"could not parse datacatalogue.gov.ie response as JSON: {e}")

    if not isinstance(payload, dict) or not payload.get("success"):
        _fatal(f"datacatalogue.gov.ie API reported success=false: {payload}")

    result = payload.get("result")
    if not isinstance(result, list):
        _fatal("datacatalogue.gov.ie response has no result list")
    return result


def fetch_orgs() -> list:
    """Fetch every organisation, following pages until an empty page comes
    back. A repeated slug (e.g. the source ignoring `offset`) is fatal, as
    is a final result of zero active organisations."""
    raw_orgs = []
    seen = set()
    offset = 0
    for _ in range(MAX_PAGES):
        page = fetch_page(offset)
        if not page:
            break
        for org in page:
            slug = org.get("name")
            if slug in seen:
                _fatal(f"duplicate organisation slug {slug!r} while paging datacatalogue.gov.ie")
            seen.add(slug)
        raw_orgs.extend(page)
        offset += len(page)
    else:
        _fatal(f"no empty page after {MAX_PAGES} pages from datacatalogue.gov.ie")

    active_orgs = filter_orgs(raw_orgs)
    if not active_orgs:
        _fatal("fetched 0 active organisations from datacatalogue.gov.ie")

    return [build_record(o) for o in active_orgs]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch datacatalogue.gov.ie's organisation list via its CKAN API"
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
        "datacatalogue_orgs": records,
    }
    write_json(output_path, output)
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} datacatalogue.gov.ie org records to {output_path}")


if __name__ == "__main__":
    main()
