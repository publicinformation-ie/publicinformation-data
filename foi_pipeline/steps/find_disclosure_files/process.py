#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from scripts.http_utils import fetch, is_safe_url

STEP_NAME = "find_disclosure_files"
FILE_EXTENSIONS = {".pdf": "pdf", ".xlsx": "xlsx", ".xls": "xls"}
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def find_file_links(html, base_url, follow_year_pages=True):
    soup = BeautifulSoup(html, "html.parser")
    files = []
    year_page_urls = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        full_url = urljoin(base_url, href)
        
        # Skip non-HTTP URLs
        if not is_safe_url(full_url):
            continue
        
        ext = Path(urlparse(href).path).suffix.lower()

        if ext in FILE_EXTENSIONS:
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                files.append({"file_url": full_url, "file_type": FILE_EXTENSIONS[ext]})
        elif follow_year_pages and YEAR_PATTERN.search(link.get_text(strip=True)):
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                year_page_urls.append(full_url)

    if follow_year_pages:
        for year_url in year_page_urls:
            try:
                resp = fetch("GET", year_url, allow_redirects=True)
                for f in find_file_links(resp.text, year_url, follow_year_pages=False):
                    if f["file_url"] not in seen_urls:
                        seen_urls.add(f["file_url"])
                        files.append(f)
            except Exception:
                pass

    return files


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for item in input_data["results"]:
        body_id = item["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = item["disclosure_page_url"]
        name = item.get("name", "")
        try:
            response = fetch("GET", url, allow_redirects=True)
            new_items = [
                {
                    "public_body_id": body_id,
                    "name": name,
                    "disclosure_page_url": url,
                    **file_info,
                }
                for file_info in find_file_links(response.text, url)
            ]
            writer.append(new_items)
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
    parser = argparse.ArgumentParser(description="Find disclosure log files on disclosure pages")
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
                               override_path=override_path)

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
