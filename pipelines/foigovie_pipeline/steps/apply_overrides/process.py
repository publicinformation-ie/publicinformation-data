#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "apply_overrides"


def apply_overrides(records: list, overrides: dict) -> list:
    """Apply manual public_body_id corrections keyed by foigovie_slug.

    A present override value (including an explicit null) always wins over
    whatever match_public_bodies produced — a non-null value corrects a false
    negative or a coincidental false-positive match, null suppresses an
    incorrect >=0.90 fuzzy match. A slug absent from `overrides` keeps its
    Step 2 result unchanged. Records are copied, never mutated in place.
    """
    resolved = []
    for record in records:
        slug = record["foigovie_slug"]
        if slug in overrides:
            record = {**record, "public_body_id": overrides[slug]}
        resolved.append(record)
    return resolved


def find_unresolved(records: list, overrides: dict) -> list:
    """Return the foigovie_slugs still lacking a public_body_id AND absent from override.json.

    A slug explicitly present in override.json — even mapped to null — has been
    deliberately reviewed and marked as having no canonical counterpart; that is a
    resolved state, not a failure. Only a slug missing from override.json entirely
    (never reviewed) is unresolved.
    """
    return [
        r["foigovie_slug"] for r in records
        if r.get("public_body_id") is None and r["foigovie_slug"] not in overrides
    ]


def count_via_override(records: list, overrides: dict) -> int:
    """Count records whose foigovie_slug has a non-null value in `overrides`
    — used for the completion summary line."""
    return sum(1 for r in records if overrides.get(r["foigovie_slug"]) is not None)


def main():
    parser = argparse.ArgumentParser(
        description="Apply manual public_body_id overrides to foi.gov.ie matches; "
                    "fail if any body is still unresolved")
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

    resolved = apply_overrides(records, overrides)

    # Unlike datagovie_pipeline's apply_overrides, an unresolved record is
    # fatal here: every foi.gov.ie entry IS an FOI body, so a gap means a
    # new/renamed body or a matching failure. Dropping it would silently
    # shrink foi_pipeline's inclusion set.
    unresolved = find_unresolved(resolved, overrides)
    if unresolved:
        print(
            f"Fatal: {len(unresolved)} unresolved public_body_id for foigovie_slug(s): "
            f"{', '.join(unresolved)}\n"
            f"Add entries to {override_path} to resolve. Consult "
            f"{step_dir.parent / 'match_public_bodies' / 'match_log.json'} for near-misses.",
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
    print(f"Matched {len(resolved)}/{len(records)} ({override_count} via override)")


if __name__ == "__main__":
    main()
