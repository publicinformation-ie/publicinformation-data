#!/usr/bin/env python3
"""Render each meeting's minutes as verbatim Markdown with a word check.

A meeting whose render loses, adds or reorders a word is not published.
Page-furniture removals are counted in the step output.
"""
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import append_errors, read_json, write_json, write_status

from steps.render_spc_minutes.rendering import STEP_NAME, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "errors.json", [])

    input_data = read_json(args.input)
    results, errors = run(input_data)
    append_errors(step_dir, errors)

    write_json(output_path, {"metadata": {"step": STEP_NAME}, "results": results})
    write_status(step_dir, len(results))
    removed = sum(r["furniture_removed"]["total"] for r in results)
    print(f"Rendered {len(results)} meeting(s); {len(errors)} error(s); "
          f"{removed} furniture line(s) removed")
    if errors:
        for entry in errors:
            print(f"Fatal: {entry['error_type']}: {entry['error_message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
