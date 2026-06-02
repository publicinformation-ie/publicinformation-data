#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.cli_utils import add_common_args, filter_by_public_body
from scripts.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from scripts.http_utils import fetch

STEP_NAME = "validate_websites"


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for body in input_data["results"]:
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = body["official_website_url"]
        try:
            response = fetch("GET", url, allow_redirects=True)
            writer.append([{
                "public_body_id": body_id,
                "name": body.get("name", ""),
                "official_website_url": url,
                "is_reachable": response.ok,
                "http_status": response.status_code,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }])
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": body_id},
            })
            writer.append([{
                "public_body_id": body_id,
                "name": body.get("name", ""),
                "official_website_url": url,
                "is_reachable": False,
                "http_status": None,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Validate public body websites")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (
        input_data.get("results") or input_data.get("public_bodies")
    ):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               override_path=override_path,
                               target_public_body=args.public_body)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
