#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "apply_overrides"


def apply_overrides(records: list, overrides: dict) -> list:
    """Fill in public_body_id from overrides (keyed by wdw_slug) for any
    record left null by match_public_bodies. Never overwrites a
    public_body_id that already matched."""
    resolved = []
    for record in records:
        if record.get("public_body_id") is None and record["wdw_slug"] in overrides:
            record = {**record, "public_body_id": overrides[record["wdw_slug"]]}
        resolved.append(record)
    return resolved


def find_unresolved(records: list) -> list:
    return [r["wdw_slug"] for r in records if r.get("public_body_id") is None]


def main():
    parser = argparse.ArgumentParser(
        description="Apply manual public_body_id overrides to unresolved WDW matches"
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

    resolved = apply_overrides(records, overrides)

    unresolved = find_unresolved(resolved)
    if unresolved:
        print(
            "Fatal: unresolved public_body_id for wdw_slug(s): "
            f"{', '.join(unresolved)}\n"
            f"Add entries to {override_path} to resolve.",
            file=sys.stderr,
        )
        sys.exit(1)

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": resolved,
    }
    write_json(output_path, output)
    write_status(step_dir, len(resolved))
    print(f"Wrote {len(resolved)} records to {output_path}")


if __name__ == "__main__":
    main()
