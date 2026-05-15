#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from scripts.http_utils import fetch, is_safe_url, validate_url_or_raise
from steps.find_disclosure_pages.domains import find_disclosure_page as domain_find

STEP_NAME = "find_disclosure_pages"
DISCLOSURE_KEYWORDS = ["disclosure", "log", "request"]


def find_disclosure_link(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        if any(kw in href or kw in text for kw in DISCLOSURE_KEYWORDS):
            full_url = urljoin(base_url, link["href"])
            # Validate URL before returning
            if is_safe_url(full_url):
                return full_url
    return None


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for item in input_data["results"]:
        body_id = item["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = item["foi_page_url"]
        name = item.get("name", "")
        try:
            validate_url_or_raise(url, context=f"disclosure_page_{body_id}")
            disclosure_url = domain_find(name, url)
            if disclosure_url is None:
                response = fetch("GET", url, allow_redirects=True)
                disclosure_url = find_disclosure_link(response.text, url) or url
            if disclosure_url:
                validate_url_or_raise(disclosure_url, context=f"disclosure_url_{body_id}")
            writer.append([{
                "public_body_id": body_id,
                "name": name,
                "foi_page_url": url,
                "disclosure_page_url": disclosure_url,
            }])
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": body_id, "name": name},
            })
            writer.append([])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Find FOI disclosure log pages")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               override_path=override_path,
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json")

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
