#!/usr/bin/env python3
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.disclosure_link_utils import FILE_EXTENSIONS, YEAR_PATTERN, find_file_links
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url

STEP_NAME = "find_disclosure_files"


def _fetch_one(item):
    """Fetch disclosure files for one body. Returns (body_id, name, url, items, exc)."""
    body_id = item["public_body_id"]
    url = item["disclosure_page_url"]
    name = item.get("name", "")
    try:
        ext = Path(urlparse(url).path).suffix.lower()
        if ext in FILE_EXTENSIONS:
            return body_id, name, url, [{
                "public_body_id": body_id,
                "name": name,
                "disclosure_page_url": url,
                "file_url": url,
                "file_type": FILE_EXTENSIONS[ext],
                "link_text": "",
            }], None
        response = fetch("GET", url, allow_redirects=True)
        items = [
            {"public_body_id": body_id, "name": name, "disclosure_page_url": url, **f}
            for f in find_file_links(response.text, url)
        ]
        return body_id, name, url, items, None
    except Exception as e:
        return body_id, name, url, [], e


def process(input_data, step_dir, writer, verbose=False, max_workers=10):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["public_body_id"])]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, item): item for item in pending}
        for future in as_completed(futures):
            body_id, name, url, items, exc = future.result()
            if exc is not None:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "context": {"url": url, "public_body_id": body_id, "name": name},
                })
                writer.append([])
            else:
                writer.append(items)
            if verbose:
                print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Find disclosure log files on disclosure pages")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=10)
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
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
                               target_public_body=args.public_body)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
