#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url, validate_url_or_raise

STEP_NAME = "resolve_website_urls"
STUB_MARKER = "There is a separate website for"


def resolve_stub_url(html, original_url):
    """Return external URL if page is a gov.ie stub portal, else original_url."""
    # Validate original URL
    validate_url_or_raise(original_url, context="resolve_stub_url")

    if STUB_MARKER not in html:
        return original_url
    soup = BeautifulSoup(html, "html.parser")
    for text_node in soup.find_all(string=lambda t: t and STUB_MARKER in t):
        next_a = text_node.find_next("a", href=True)
        if next_a:
            resolved = urljoin(original_url, next_a["href"])
            # Validate resolved URL
            if is_safe_url(resolved):
                return resolved
    return original_url


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for body in input_data["public_bodies"]:
        if body.get("exclusion_reason"):
            continue
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = body["official_website_url"]
        try:
            response = fetch("GET", url, allow_redirects=True)
            resolved_url = resolve_stub_url(response.text, url)
            writer.append([{**body, "official_website_url": resolved_url}])
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": body_id},
            })
            writer.append([body])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Resolve gov.ie stub portal URLs to real external websites")
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
