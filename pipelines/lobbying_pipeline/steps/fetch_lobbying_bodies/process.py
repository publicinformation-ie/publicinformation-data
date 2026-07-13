#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_lobbying_bodies"
PUBLIC_BODY_URL = "https://api.lobbying.ie/api/PublicBody"
SEARCH_URL = "https://api.lobbying.ie/api/Search"
BASE_SEARCH_URL = "https://www.lobbying.ie/app/home/search"


def filter_active(raw_bodies: list) -> list:
    """Keep only IsActive bodies — the register also lists inactive/retired
    public bodies still visible for historical returns."""
    return [b for b in raw_bodies if b.get("IsActive") is True]


def build_record(body: dict, returns_count) -> dict:
    body_id = body["Id"]
    return {
        "lobbyingie_id": body_id,
        "lobbyingie_name": body["Name"],
        "lobbyingie_url": f"{BASE_SEARCH_URL}?publicBodys={body_id}",
        "lobbyingie_returns_count": returns_count,
    }


def fetch_return_count(body_id: int):
    """Fetch the Total count of lobbying returns for one public body.

    Not fatal on failure — a single flaky Search call must not block the
    other ~169 bodies. Returns None (logged as a stderr warning by the
    caller) on any request error, non-200, unparsable JSON, or a response
    missing the Total field.
    """
    try:
        response = fetch(
            "GET", SEARCH_URL,
            params={
                "currentPage": 0, "pageSize": 1, "queryText": "",
                "subjectMatters": "", "subjectMatterAreas": "",
                "publicBodys": body_id, "jobTitles": "",
                "returnDateFrom": "", "returnDateTo": "", "period": "",
                "dpo": "", "client": "", "responsible": "",
                "lobbyist": "", "lobbyistId": "",
            },
        )
    except Exception as e:
        print(f"Warning: Search request failed for public body {body_id}: {e}", file=sys.stderr)
        return None

    if not response.ok:
        print(f"Warning: Search returned HTTP {response.status_code} for public body {body_id}", file=sys.stderr)
        return None

    try:
        payload = response.json()
    except ValueError as e:
        print(f"Warning: could not parse Search response as JSON for public body {body_id}: {e}", file=sys.stderr)
        return None

    if "Total" not in payload:
        print(f"Warning: Search response missing Total for public body {body_id}", file=sys.stderr)
        return None

    return payload["Total"]


def fetch_bodies() -> list:
    """Fetch and parse the PublicBody list, then fetch a return count per
    active body. Fatal-exits on request failure, a non-list response, or
    zero active records after filtering — same guard style as
    fetch_datagovie_orgs. Per-record Search failures are not fatal (see
    fetch_return_count)."""
    try:
        response = fetch("GET", PUBLIC_BODY_URL)
    except Exception as e:
        print(f"Fatal: request to lobbying.ie PublicBody endpoint failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not response.ok:
        print(f"Fatal: lobbying.ie PublicBody endpoint returned HTTP {response.status_code}", file=sys.stderr)
        sys.exit(1)

    try:
        payload = response.json()
    except ValueError as e:
        print(f"Fatal: could not parse PublicBody response as JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(payload, list):
        print(f"Fatal: PublicBody response is not a JSON list: {type(payload)}", file=sys.stderr)
        sys.exit(1)

    active_bodies = filter_active(payload)

    if not active_bodies:
        print("Fatal: fetched 0 active public bodies from lobbying.ie", file=sys.stderr)
        sys.exit(1)

    records = []
    for body in active_bodies:
        returns_count = fetch_return_count(body["Id"])
        records.append(build_record(body, returns_count))
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Fetch lobbying.ie's public body list and per-body return counts"
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
        },
        "lobbyingie_bodies": records,
    }
    write_json(output_path, output)
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} lobbying.ie public body records to {output_path}")


if __name__ == "__main__":
    main()
