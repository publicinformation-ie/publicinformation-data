#!/usr/bin/env python3
"""Parse each meeting's header, date and attendance table from the fetched words.

A meeting whose header cannot be parsed, whose date disagrees with its link
text, or which collides with another file is withheld with an error.
"""
import argparse
import json
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import append_error, read_json, write_json, write_status

from steps.parse_meeting_header.header import run

STEP_NAME = "parse_meeting_header"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "errors.json", [])

    input_data = read_json(args.input)
    records, errors = run(input_data)
    for entry in errors:
        append_error(step_dir, entry)

    write_json(output_path, {"metadata": {"step": STEP_NAME}, "results": records})
    write_status(step_dir, len(records))
    print(f"Parsed {len(records)} meeting(s); {len(errors)} error(s)")
    if errors:
        for entry in errors:
            print(f"Fatal: {entry['error_type']}: {entry['error_message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
