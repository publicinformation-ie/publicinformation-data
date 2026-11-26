#!/usr/bin/env python3
"""Resolve every printed attendee to a person ID in the committed register.

A meeting with an unresolved or contradictory name keeps its page, date and
rendered minutes, but publishes no attendance rows; the meeting is marked
``attendance_published: false`` and the reason is in ``errors.json``.
"""
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import append_errors, read_json, write_json, write_status

from steps.resolve_attendees.resolving import STEP_NAME, load_register, run

PIPELINE_DIR = Path(__file__).resolve().parents[2]
REGISTER_PATH = PIPELINE_DIR / "reference" / "people.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "errors.json", [])

    input_data = read_json(args.input)
    register = load_register(REGISTER_PATH)
    results, errors = run(input_data, register)
    append_errors(step_dir, errors)

    write_json(output_path, {"metadata": {"step": STEP_NAME}, "results": results})
    write_status(step_dir, len(results))

    withheld = [r["meeting_id"] for r in results if not r["attendance_published"]]
    print(f"Resolved {len(results)} meeting(s); {len(errors)} error(s)")
    for meeting_id in withheld:
        print(f"Attendance withheld: {meeting_id}", file=sys.stderr)
    # A withheld attendance is a designed, visible outcome (attendance_published
    # false), not a pipeline failure: the meeting's minutes still publish.
    if withheld and any(e["error_type"] not in
                        ("UnresolvedAttendee", "ContradictoryAttendance", "ContradictoryMode")
                        for e in errors):
        sys.exit(1)


if __name__ == "__main__":
    main()
