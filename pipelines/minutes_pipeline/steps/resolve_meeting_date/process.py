#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body, merge_replacing_body
from lib.file_utils import read_json, write_json, write_status

from steps.resolve_meeting_date.date_resolver import resolve

STEP_NAME = "resolve_meeting_date"


def resolve_records(input_records, body_id=None):
    """Return (resolved_records, errors). meeting_date is overwritten with the
    resolved ISO date (or None); stated_date is dropped."""
    resolved, errors = [], []
    for record in input_records:
        if body_id is not None and str(record.get("public_body_id")) != str(body_id):
            continue
        iso, err = resolve(record)
        if err is not None:
            err.setdefault("step", STEP_NAME)
            err.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            errors.append(err)
        out = {k: v for k, v in record.items() if k != "stated_date"}
        out["meeting_date"] = iso
        resolved.append(out)
    return resolved, errors


def run(input_path, output_path, step_dir, public_body=None, force=False):
    input_data = filter_by_public_body(read_json(input_path), public_body)
    resolved, errors = resolve_records(input_data.get("results", []),
                                       body_id=public_body)

    output_path = Path(output_path)
    if public_body is not None and not force and output_path.exists():
        existing = read_json(output_path).get("results", [])
        resolved = merge_replacing_body(existing, resolved, public_body)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "total_records_output": len(resolved),
        },
        "results": resolved,
    })
    write_json(Path(step_dir) / "errors.json", errors)
    write_status(step_dir, len(resolved))
    return len(resolved)


def main():
    parser = argparse.ArgumentParser(
        description="Resolve each minutes document's meeting_date (deterministic)")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    try:
        count = run(args.input, args.output, step_dir,
                    public_body=args.public_body, force=args.force)
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {count} records to {args.output}")


if __name__ == "__main__":
    main()
