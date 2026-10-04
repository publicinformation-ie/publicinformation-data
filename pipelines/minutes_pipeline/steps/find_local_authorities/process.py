#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "find_local_authorities"


def load_committed_authorities(path) -> list:
    """Read the committed, hand-authored authority list."""
    return read_json(path)


def join_with_cso(authorities, cso_output):
    """Join committed authorities to CSO records by name.

    Returns (records, unmatched_names). Any committed name missing from the
    CSO output is reported (never silently dropped); the caller decides
    whether that is fatal.
    """
    by_name = {r["name"]: r
               for r in (cso_output.get("results")
                         or cso_output.get("public_bodies", []))}
    records = []
    unmatched = []
    for auth in authorities:
        cso = by_name.get(auth["name"])
        if cso is None:
            unmatched.append(auth["name"])
            continue
        records.append({
            "public_body_id": cso["public_body_id"],
            "name": auth["name"],
            "slug": auth["slug"],
            "official_website_url": cso.get("official_website_url"),
            "municipal_districts": auth.get("municipal_districts", []),
        })
    return records, unmatched


def process(input_data, authorities_path, writer, step_dir, verbose=False,
            public_body=None):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    authorities = load_committed_authorities(authorities_path)
    records, unmatched = join_with_cso(authorities, input_data)

    # Scoped runs: emit only the target body. The writer has already evicted
    # that body's existing record, so appending the full list here would add
    # duplicates of every other authority on each scoped re-run.
    if public_body is not None:
        records = [r for r in records if r["public_body_id"] == public_body]

    for name in unmatched:
        append_error(step_dir, {
            "step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": "UnmatchedAuthorityName",
            "error_message": f"Authority name '{name}' from local_authorities.json "
                             f"not found in resolve_website_urls/output.json — "
                             f"rename/removal needs human attention",
            "context": {"name": name},
        })
        print(f"Fatal: authority name '{name}' not found in CSO output", file=sys.stderr)

    if unmatched:
        sys.exit(1)

    # Replace-if-changed: a re-run (e.g. after CSO website fixes) must update
    # records whose join result moved (new official_website_url) without
    # duplicating the unchanged ones. Eviction marks changed bodies dirty so
    # downstream steps re-crawl exactly those bodies via dirty_ids.json.
    existing_by_id = {r["public_body_id"]: r for r in writer.results
                      if "public_body_id" in r}
    changed = [r for r in records
               if existing_by_id.get(r["public_body_id"]) != r]
    if changed:
        writer._evict_keys({r["public_body_id"] for r in changed})
        writer.append(changed)


def main():
    parser = argparse.ArgumentParser(
        description="Emit the 31 local authorities joined with their CSO public_body_ids"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    # First step (no --input from an upstream step): the runner passes its own
    # step_dir as --input; load the CSO output and committed list from there.
    input_path = Path(args.input)
    if input_path.is_dir():
        cso_out = read_json(
            step_dir.parent.parent.parent
            / "cso_pipeline/steps/resolve_website_urls/output.json"
        )
    else:
        cso_out = read_json(args.input)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               target_public_body=args.public_body)

    process(cso_out, step_dir / "local_authorities.json", writer, step_dir=step_dir,
            verbose=args.verbose, public_body=args.public_body)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} authorities to {output_path}")


if __name__ == "__main__":
    main()
