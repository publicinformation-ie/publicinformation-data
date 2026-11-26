#!/usr/bin/env python3
"""Assemble meetings, people, attendance, items and decisions for publication.

Withheld attendance, topics or decisions stay withheld and are counted by
error type. A meeting whose render failed is not published at all.
"""
import argparse
import json
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import read_json, write_json, write_status

from steps.export_spc_meetings.exporting import STEP_NAME, export
from steps.resolve_attendees.resolving import load_register

PIPELINE_DIR = Path(__file__).resolve().parents[2]
REGISTER_PATH = PIPELINE_DIR / "reference" / "people.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_data = read_json(args.input)
    register = load_register(REGISTER_PATH)
    dataset, report = export(input_data, register)

    write_json(output_path, {"metadata": {"step": STEP_NAME},
                             "results": dataset, "report": report})
    write_status(step_dir, report["meetings"])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
