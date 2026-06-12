#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "find_public_bodies"
_LOCAL_AUTHORITY_PATTERNS = ("County Council", "City Council", "City and County Council")


def derive_category(body):
    sector = body.get("sector") or ""
    govt_dept = body.get("government_department") or ""
    if sector.startswith("S1313"):
        return "local authority"
    if sector.startswith("S1311"):
        return "government department"
    for pat in _LOCAL_AUTHORITY_PATTERNS:
        if pat in govt_dept:
            return "local authority"
    return "public service body"


def ingest_bodies(hub_records):
    bodies = []
    for r in hub_records:
        url = r.get("official_website_url")
        bodies.append({
            "public_body_id": r["public_body_id"],
            "name": r["name"],
            "official_website_url": url,
            "category": derive_category(r),
            "status": {
                "website_url": {"url": url, "status": "not_attempted"},
                "foi_page": {"url": None, "status": "not_attempted"},
                "foi_email": {"email": None, "status": "not_attempted"},
                "disclosures_page": {"url": None, "status": "not_attempted"},
                "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "not_attempted"},
                "foi_requests": {"valid": 0, "errors": 0, "status": "not_attempted"},
            },
        })
    return bodies


def main():
    parser = argparse.ArgumentParser(description="Ingest public bodies from CSO hub output")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if args.public_body is not None and not args.force and output_path.exists():
        bodies = read_json(output_path).get("public_bodies", [])
        if not any(b.get("public_body_id") == args.public_body for b in bodies):
            print(f"Error: public body {args.public_body} not found in {output_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Scoped run: confirmed body {args.public_body}; leaving {output_path} untouched")
        sys.exit(0)

    if not args.force and output_path.exists() and args.public_body is None:
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    hub_data = read_json(args.input)
    hub_records = hub_data.get("results") or hub_data.get("public_bodies", [])

    if args.public_body is not None:
        hub_records = [r for r in hub_records if r.get("public_body_id") == args.public_body]

    bodies = ingest_bodies(hub_records)

    if not bodies and args.public_body is None:
        print("Fatal error: hub output contains 0 bodies", file=sys.stderr)
        sys.exit(1)

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": bodies,
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
