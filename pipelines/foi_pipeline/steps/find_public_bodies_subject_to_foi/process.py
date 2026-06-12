#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "find_public_bodies_subject_to_foi"


def main():
    parser = argparse.ArgumentParser(description="Filter public bodies to those subject to FOI")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    inclusions = set(read_json(step_dir / "inclusions.json"))

    if args.public_body is not None and not args.force and output_path.exists():
        bodies = read_json(output_path).get("public_bodies", [])
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
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} FOI-subject public bodies to {output_path}")


if __name__ == "__main__":
    main()
