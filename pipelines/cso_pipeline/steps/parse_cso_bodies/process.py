#!/usr/bin/env python3
import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "parse_cso_bodies"
CSO_CSV_FILENAME = "CSO_PRPBI2025H1TBL1.1csv.csv"


def normalize(name: str) -> str:
    return name.lower().strip()


def parse_rows(rows: list, id_map: dict) -> tuple:
    """
    Assign stable public_body_id values and resolve parent_id references.

    On first run (empty id_map): sorts by normalized entity_name, assigns IDs
    from 1000 upward. On subsequent runs: existing entities keep their IDs;
    new entities are appended at max(existing_ids) + 1.

    Returns (records, updated_id_map).
    """
    next_id = max(id_map.values(), default=999) + 1

    # Assign IDs to new entities. Sort for stable first-run ordering.
    updated_map = dict(id_map)
    for row in sorted(rows, key=lambda r: normalize(r["entity_name"])):
        norm = normalize(row["entity_name"])
        if norm not in updated_map:
            updated_map[norm] = next_id
            next_id += 1

    # Build output records in original CSV order
    records = []
    for row in rows:
        norm = normalize(row["entity_name"])
        raw_parent = row.get("parent", "").strip()
        parent_name = raw_parent if raw_parent else None
        parent_id = updated_map.get(normalize(parent_name)) if parent_name else None
        govt_dept = row.get("government_department_or_local_authority", "").strip() or None
        govt_dept_id = updated_map.get(normalize(govt_dept)) if govt_dept else None

        records.append({
            "public_body_id": updated_map[norm],
            "name": row["entity_name"].strip(),
            "parent_name": parent_name,
            "parent_id": parent_id,
            "sector": row.get("sector", "").strip() or None,
            "legal_status": row.get("legal_status", "").strip() or None,
            "government_department": govt_dept,
            "government_department_id": govt_dept_id,
            "nace_code": row.get("nace_code", "").strip() or None,
            "cro": row.get("cro", "").strip() or None,
            "data_vintage": int(row["data_vintage"]) if row.get("data_vintage", "").strip() else None,
            "description_for_sub_sector": row.get("description_for_sub_sector", "").strip() or None,
            "official_website_url": None,
        })

    return records, updated_map


def main():
    parser = argparse.ArgumentParser(
        description="Parse CSO public bodies CSV and assign stable IDs"
    )
    parser.add_argument("--input", required=True,
                        help="Previous step output (unused — first step in pipeline)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body",
                        help="Scoped run: confirm body exists, leave output untouched")
    parser.add_argument("--data-dir", default=None,
                        help="Directory containing the CSO CSV "
                             "(defaults to <pipeline_dir>/data/)")
    parser.add_argument("--id-map", default=None, dest="id_map",
                        help="Path to id_map.json "
                             "(defaults to <step_dir>/id_map.json)")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    pipeline_dir = step_dir.parent.parent  # pipelines/cso_pipeline/
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    id_map_path = Path(args.id_map) if args.id_map else step_dir / "id_map.json"
    data_dir = Path(args.data_dir) if args.data_dir else pipeline_dir / "data"
    csv_path = data_dir / CSO_CSV_FILENAME

    if args.public_body is not None and not args.force and output_path.exists():
        bodies = read_json(output_path).get("public_bodies", [])
        if not any(b.get("public_body_id") == args.public_body for b in bodies):
            print(f"Error: public body {args.public_body} not found in {output_path}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"Scoped run: confirmed body {args.public_body}; leaving {output_path} untouched")
        sys.exit(0)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    if not csv_path.exists():
        print(f"Fatal: CSO CSV not found at {csv_path}\n"
              f"Place {CSO_CSV_FILENAME} in {data_dir}/", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, encoding="latin-1", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Fatal: CSV is empty", file=sys.stderr)
        sys.exit(1)

    id_map = read_json(id_map_path) if id_map_path.exists() else {}
    records, updated_map = parse_rows(rows, id_map)

    write_json(id_map_path, updated_map)

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": records,
    }
    write_json(output_path, output)
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
