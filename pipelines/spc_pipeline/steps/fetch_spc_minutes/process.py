#!/usr/bin/env python3
"""Download the discovered minutes PDFs and record their text with coordinates.

The PDF cache lives in ``pipelines/spc_pipeline/cache/`` (git-ignored). A
warm cache makes no HTTP request. Failures produce an error and no record;
a PDF without a text layer is a ``NoTextLayer`` error, never OCR.
"""
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import append_error, read_json, write_json, write_status

from steps.fetch_spc_minutes.fetching import STEP_NAME, run

PIPELINE_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = PIPELINE_DIR / "cache"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "errors.json", [])

    input_data = read_json(args.input)
    records, errors = run(input_data, CACHE_DIR)
    for entry in errors:
        append_error(step_dir, entry)

    write_json(output_path, {"metadata": {"step": STEP_NAME}, "results": records})
    write_status(step_dir, len(records))
    print(f"Fetched {len(records)} minutes PDF(s); {len(errors)} error(s)")
    if errors:
        for entry in errors:
            print(f"Fatal: {entry['error_type']}: {entry['error_message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
