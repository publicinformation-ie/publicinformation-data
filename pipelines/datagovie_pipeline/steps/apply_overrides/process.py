#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "apply_overrides"


def apply_overrides(records: list, overrides: dict) -> list:
    """Apply manual public_body_id corrections keyed by datagovie_slug.

    A present override value (including an explicit null) always wins
    over whatever match_public_bodies produced — a non-null value
    corrects a false negative/positive match, null suppresses an
    incorrect >=0.90 fuzzy match. A slug absent from `overrides` keeps
    its Step 2 result unchanged.
    """
    resolved = []
    for record in records:
        slug = record["datagovie_slug"]
        if slug in overrides:
            record = {**record, "public_body_id": overrides[slug]}
        resolved.append(record)
    return resolved


def drop_unresolved(records: list) -> tuple:
    """Split into (resolved, dropped_slugs). Any record whose
    public_body_id is still null after overrides is dropped from the
    published output rather than failing the pipeline — most data.gov.ie
    organisations are not public bodies at all, so partial resolution is
    the expected, normal outcome here (unlike WDW's apply_overrides,
    which fatal-exits on any gap)."""
    resolved = [r for r in records if r.get("public_body_id") is not None]
    dropped = [r["datagovie_slug"] for r in records if r.get("public_body_id") is None]
    return resolved, dropped


def count_via_override(records: list, overrides: dict) -> int:
    """Count records whose datagovie_slug has a non-null value in
    `overrides` — used for the completion summary line."""
    return sum(1 for r in records if overrides.get(r["datagovie_slug"]) is not None)


def main():
    parser = argparse.ArgumentParser(
        description="Apply manual public_body_id overrides to data.gov.ie matches, "
                     "dropping any record still unresolved"
    )
    parser.add_argument("--input", required=True, help="match_public_bodies output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    override_path = step_dir / "override.json"

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    records = input_data.get("results", [])
    overrides = read_json(override_path) if override_path.exists() else {}
    override_count = count_via_override(records, overrides)

    overridden = apply_overrides(records, overrides)
    resolved, dropped = drop_unresolved(overridden)

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": resolved,
    }
    write_json(output_path, output)
    write_status(step_dir, len(resolved))
    print(
        f"Matched {len(resolved)}/{len(records)} ({override_count} via override), "
        f"dropped {len(dropped)} unmatched"
    )


if __name__ == "__main__":
    main()
