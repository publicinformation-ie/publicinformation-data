#!/usr/bin/env python3
# Stub — disclosure record extraction not yet implemented
import argparse
import sys
from pathlib import Path

from scripts.file_utils import IncrementalWriter, write_status

STEP_NAME = "extract_disclosures"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    step_dir = Path(__file__).parent
    override_path = step_dir / "override.json"

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="file_url", force=args.force,
                               override_path=override_path)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Stub: wrote {count} results to {output_path}")


if __name__ == "__main__":
    main()
