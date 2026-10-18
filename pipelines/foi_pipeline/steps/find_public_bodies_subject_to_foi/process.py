#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "find_public_bodies_subject_to_foi"

FOIGOVIE_OUTPUT_PATH = "pipelines/foigovie_pipeline/steps/apply_overrides/output.json"
OVERRIDES_PATH = "inclusion_overrides.json"
INCLUSIONS_PATH = "inclusions.json"


def load_inclusions(foigovie_output_path, overrides_path=None, known_ids=None) -> set:
    """Return the set of public_body_ids that are subject to FOI.

    Primary source: foi.gov.ie's official directory, via the foigovie pipeline.
    Several foi.gov.ie entries can resolve to one canonical body (e.g. HSE
    regions), hence a set rather than a list.

    Curated additions (`inclusion_overrides.json`) are unioned in: the directory
    is not exhaustive, and a body it omits is still subject to FOI. Every
    addition must name a body that exists and state why it is being added.

    Fatal-exits on a missing or empty source, on an addition whose id matches no
    body, and on an addition with no reason -- any of those would silently
    distort the FOI pipeline rather than fail it.
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

    if overrides_path and Path(overrides_path).exists():
        for entry in read_json(overrides_path):
            body_id = entry.get("public_body_id")
            if body_id is None or not entry.get("reason"):
                print(
                    f"Fatal: every entry in {overrides_path} needs a "
                    f"'public_body_id' and a 'reason'; got {entry!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            if known_ids is not None and body_id not in known_ids:
                print(
                    f"Fatal: {overrides_path} lists public_body_id={body_id} "
                    f"({entry.get('name', 'unnamed')}), which is not in "
                    f"find_public_bodies/output.json. Check the id.",
                    file=sys.stderr,
                )
                sys.exit(1)
            ids.add(body_id)
    return ids


def main():
    parser = argparse.ArgumentParser(description="Filter public bodies to those subject to FOI")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    repo_root = step_dir.parent.parent.parent.parent  # steps/<name>/ -> foi_pipeline/ -> pipelines/ -> repo
    known_ids = {
        b["public_body_id"]
        for b in read_json(Path(args.input)).get("public_bodies", [])
    } if Path(args.input).exists() else set()
    inclusions = load_inclusions(
        repo_root / FOIGOVIE_OUTPUT_PATH,
        step_dir / OVERRIDES_PATH,
        known_ids or None,
    )

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
    write_json(step_dir / INCLUSIONS_PATH, sorted(inclusions))
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} FOI-subject public bodies to {output_path}")
    print(f"Wrote the resolved inclusion set ({len(inclusions)} ids) to {step_dir / INCLUSIONS_PATH}")


if __name__ == "__main__":
    main()
