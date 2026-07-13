#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "apply_overrides"


def apply_overrides(records: list, overrides: dict) -> list:
    """Apply manual public_body_id corrections keyed by str(lobbyingie_id).

    A present override value (including an explicit null) always wins
    over whatever match_public_bodies produced — a non-null value
    corrects a false negative/positive match, null suppresses an
    incorrect >=0.90 fuzzy match. An ID absent from `overrides` keeps
    its Step 2 result unchanged.
    """
    resolved = []
    for record in records:
        key = str(record["lobbyingie_id"])
        if key in overrides:
            record = {**record, "public_body_id": overrides[key]}
        resolved.append(record)
    return resolved


def drop_unresolved(records: list) -> tuple:
    """Split into (resolved, dropped_ids). Any record whose public_body_id
    is still null after overrides is dropped from the published output
    rather than failing the pipeline — a handful of register entries may
    not resolve to a canonical body (e.g. merged/renamed bodies still
    visible historically in the register), so partial resolution is the
    expected outcome here."""
    resolved = [r for r in records if r.get("public_body_id") is not None]
    dropped = [r["lobbyingie_id"] for r in records if r.get("public_body_id") is None]
    return resolved, dropped


def count_via_override(records: list, overrides: dict) -> int:
    """Count records whose lobbyingie_id has a non-null value in
    `overrides` — used for the completion summary line."""
    return sum(1 for r in records if overrides.get(str(r["lobbyingie_id"])) is not None)


def main():
    parser = argparse.ArgumentParser(
        description="Apply manual public_body_id overrides to lobbying.ie matches, "
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
