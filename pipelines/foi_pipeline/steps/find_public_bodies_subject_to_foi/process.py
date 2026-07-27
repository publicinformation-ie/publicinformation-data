#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "find_public_bodies_subject_to_foi"

FOIGOVIE_OUTPUT_PATH = "pipelines/foigovie_pipeline/steps/apply_overrides/output.json"


def load_inclusions(foigovie_output_path) -> set:
    """Return the set of public_body_ids foi.gov.ie lists as subject to FOI.

    Replaces the hand-maintained inclusions.json: the inclusion set is now
    derived from foi.gov.ie's official directory on every run, so it is
    auditable and self-updating. Several foi.gov.ie entries can resolve to
    one canonical body (e.g. HSE regions), hence a set rather than a list.

    Fatal-exits on a missing file or an empty set — either would silently
    empty the FOI pipeline rather than failing loudly.
    """
    path = Path(foigovie_output_path)
    if not path.exists():
        print(f"Fatal: foigovie inclusion source not found at {path}\n"
              f"Run foigovie_pipeline first.", file=sys.stderr)
        sys.exit(1)
    ids = {
        r["public_body_id"]
        for r in read_json(path).get("results", [])
        if r.get("public_body_id") is not None
    }
    if not ids:
        print(f"Fatal: {path} yielded 0 FOI-subject public bodies", file=sys.stderr)
        sys.exit(1)
    return ids


def main():
    parser = argparse.ArgumentParser(description="Filter public bodies to those subject to FOI")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    repo_root = step_dir.parent.parent.parent.parent  # steps/<name>/ -> foi_pipeline/ -> pipelines/ -> repo
    inclusions = load_inclusions(repo_root / FOIGOVIE_OUTPUT_PATH)

    if args.public_body is not None and not args.force and output_path.exists():
        saved = read_json(output_path)
        bodies = saved.get("public_bodies") or saved.get("results", [])
        match = next((b for b in bodies if b.get("public_body_id") == args.public_body), None)
        if match is None:
            print(
                f"Error: public body {args.public_body} is not subject to FOI "
                f"or not found in {output_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Scoped run: confirmed body {args.public_body}; leaving {output_path} untouched")
        sys.exit(0)

    if not args.force and output_path.exists() and args.public_body is None:
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    input_data = read_json(args.input)
    input_data = filter_by_public_body(input_data, args.public_body)

    bodies = [b for b in input_data["public_bodies"] if b["public_body_id"] in inclusions]

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": bodies,
        "results": bodies,
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} FOI-subject public bodies to {output_path}")


if __name__ == "__main__":
    main()
