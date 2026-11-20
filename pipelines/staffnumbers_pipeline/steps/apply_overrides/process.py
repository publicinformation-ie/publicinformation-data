#!/usr/bin/env python3
"""Apply reviewed manual decisions from override.json, then keep every row.

override.json maps a source_key to either:
  * an integer public_body_id -- a human confirmed this row is that body
    (match_status becomes 'override'); or
  * null -- a human confirmed the row has no canonical body (an aggregate such
    as 'Second Level Education', or a sub-unit). It stays unmatched but is
    recorded as reviewed, so it is not reported again.

Unmatched rows are never dropped: their FTE is real headcount and removing it
would break the totals. Rows that are unmatched *and not yet reviewed* are
written to errors.json for a human.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "apply_overrides"
CANDIDATES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"


def apply_overrides(records: list, overrides: dict, valid_ids: set):
    """Returns (records, unreviewed_source_keys). Raises ValueError on an
    override that targets an unknown body or an unknown source row, so a
    stale or mistyped decision cannot pass silently."""
    keys = {r["source_key"] for r in records}
    stale = sorted(set(overrides) - keys)
    if stale:
        raise ValueError(f"override.json has keys not in the source: {stale}")
    out, unreviewed = [], []
    for rec in records:
        key = rec["source_key"]
        if key in overrides:
            target = overrides[key]
            if target is not None and target not in valid_ids:
                raise ValueError(f"override for {key!r} targets unknown public_body_id {target!r}")
            if rec["match_status"] in ("exact", "rule"):
                raise ValueError(f"override for {key!r} is redundant: already matched deterministically")
            rec = {**rec, "public_body_id": target,
                   "match_status": "override" if target is not None else "unmatched",
                   "match_method": "manual_override" if target is not None else "manual_no_body"}
        elif rec["public_body_id"] is None:
            unreviewed.append(key)
        out.append(rec)
    return out, unreviewed


def main():
    parser = argparse.ArgumentParser(description="Apply manual public_body_id decisions to staff-number matches")
    parser.add_argument("--input", required=True, help="match_public_bodies output.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body")
    parser.add_argument("--candidates", default=None)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    repo_root = step_dir.parent.parent.parent.parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    candidates_path = Path(args.candidates) if args.candidates else repo_root / CANDIDATES_PATH
    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    try:
        data = read_json(args.input)
        valid_ids = {b["public_body_id"] for b in read_json(candidates_path)["public_bodies"]}
        override_path = step_dir / "override.json"
        overrides = read_json(override_path) if override_path.exists() else {}
        records, unreviewed = apply_overrides(data["results"], overrides, valid_ids)
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)

    errors_path = step_dir / "errors.json"
    if errors_path.exists():
        errors_path.unlink()
    append_errors(step_dir, [{
        "step": STEP_NAME, "error_type": "unmatched_unreviewed",
        "error_message": "no canonical body matched and no override recorded; "
                         "add an id or null to override.json",
        "context": {"source_key": k}} for k in unreviewed])
    write_json(output_path, {
        "metadata": {**data["metadata"], "step": STEP_NAME,
                     "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": records,
    })
    write_status(step_dir, len(records))
    matched = sum(1 for r in records if r["public_body_id"] is not None)
    print(f"{matched}/{len(records)} rows matched to a public body; "
          f"{len(unreviewed)} unmatched rows awaiting review")


if __name__ == "__main__":
    main()
