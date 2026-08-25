#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import read_json, write_json, write_status

CANDIDATES_PATH = "pipelines/cso_pipeline/steps/resolve_website_urls/output.json"


def apply_overrides(records: list, overrides: dict) -> list:
    """Apply manual public_body_id corrections keyed by **str(statespend_id)**.

    Key-type convention (pin this): JSON object keys are strings, while the
    record's `statespend_id` and IncrementalWriter's processed_keys are ints.
    Every lookup therefore goes through `str(record["statespend_id"])`. A miss
    caused by forgetting the conversion is silent, so tests cover both key
    forms explicitly.

    A present override value (including an explicit null) always wins over
    whatever match_public_bodies produced — a non-null value corrects a false
    negative/positive match, null suppresses an incorrect >=0.90 fuzzy match.
    An id absent from `overrides` keeps its Step 2 result unchanged.
    """
    resolved = []
    for record in records:
        sid = str(record["statespend_id"])
        if sid in overrides:
            record = {**record, "public_body_id": overrides[sid]}
        resolved.append(record)
    return resolved


def verify_override_ids(overrides: dict, valid_ids: set) -> None:
    """Guard against the documented wrong-id incident class: every non-null
    override must exist in the canonical candidate register. Fatal-exits
    otherwise — a stale or typo'd id would silently merge a statespend body
    into an unrelated public body."""
    bad = {k: v for k, v in overrides.items()
           if v is not None and v not in valid_ids}
    if bad:
        print(f"Fatal: override ids not present in the canonical register "
              f"(run cso_pipeline through resolve_website_urls first): {bad}",
              file=sys.stderr)
        sys.exit(1)


def drop_unresolved(records: list, overrides: dict) -> tuple:
    """Split into (resolved, dropped). Any record whose public_body_id is
    still null after overrides is dropped from the output rather than failing
    the pipeline — Tier D rows (NTMA internal fund accounts, DPER pseudo-offices,
    bodies with no canonical counterpart) are genuinely unmappable, so partial
    resolution is expected. Unlike datagovie's silent drop, every drop is
    logged with its reason per the fail-closed rule in AGENTS.md."""
    resolved = []
    dropped = []
    for r in records:
        if r.get("public_body_id") is not None:
            resolved.append(r)
            continue
        sid = str(r["statespend_id"])
        if sid in overrides and overrides[sid] is None:
            reason = "explicit null override (no canonical counterpart / suppressed)"
        else:
            reason = "unresolved after matching (below 0.90 threshold, no override)"
        dropped.append({
            "statespend_id": r["statespend_id"],
            "statespend_name": r.get("statespend_name"),
            "reason": reason,
        })
    return resolved, dropped


def count_via_override(records: list, overrides: dict) -> int:
    """Count records whose str(statespend_id) has a non-null value in
    `overrides` — used for the completion summary line."""
    return sum(1 for r in records if overrides.get(str(r["statespend_id"])) is not None)


def main():
    parser = argparse.ArgumentParser(
        description="Apply manual public_body_id overrides to statespend matches, "
                     "dropping any record still unresolved (logged to errors.json)"
    )
    add_common_args(parser)
    parser.add_argument("--candidates", default=None,
                        help="Path to resolve_website_urls output.json "
                             f"(defaults to <repo_root>/{CANDIDATES_PATH})")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    pipeline_dir = step_dir.parent.parent  # pipelines/statespend_pipeline/
    repo_root = pipeline_dir.parent.parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"
    candidates_path = Path(args.candidates) if args.candidates else repo_root / CANDIDATES_PATH

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    records = input_data.get("results", [])
    overrides = read_json(override_path) if override_path.exists() else {}

    # Existence guard needs the canonical register; skip only when there are
    # no non-null overrides at all (e.g. isolated local testing).
    if any(v is not None for v in overrides.values()):
        if not candidates_path.exists():
            print(f"Fatal: candidates file not found at {candidates_path}\n"
                  f"Run cso_pipeline through resolve_website_urls first.", file=sys.stderr)
            sys.exit(1)
        data = read_json(candidates_path)
        bodies = data.get("results") or data.get("public_bodies", [])
        verify_override_ids(overrides, {b["public_body_id"] for b in bodies})

    override_count = count_via_override(records, overrides)

    overridden = apply_overrides(records, overrides)
    resolved, dropped = drop_unresolved(overridden, overrides)

    output = {
        "metadata": {
            "step": "apply_overrides",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": resolved,
    }
    write_json(output_path, output)
    write_json(output_path.parent / "errors.json", {
        "metadata": {
            "step": "apply_overrides",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "errors": dropped,
    })
    write_status(step_dir, len(resolved))
    print(
        f"Matched {len(resolved)}/{len(records)} ({override_count} via override), "
        f"dropped {len(dropped)} unmatched (see errors.json)"
    )


if __name__ == "__main__":
    main()
