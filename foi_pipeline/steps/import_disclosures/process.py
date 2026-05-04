#!/usr/bin/env python3
# Stub — backend API import not yet implemented
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.file_utils import write_json, write_status

STEP_NAME = "import_disclosures"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    step_dir = Path(__file__).parent

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    write_json(output_path, {
        "metadata": {"step": STEP_NAME, "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": [],
    })
    write_status(step_dir, 0)
    print(f"Stub: wrote empty results to {output_path}")


if __name__ == "__main__":
    main()
