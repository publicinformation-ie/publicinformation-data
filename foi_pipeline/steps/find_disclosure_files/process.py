#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status
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


def process(input_data, step_dir):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    results = []
    for item in input_data["results"]:
        url = item["disclosure_page_url"]
        name = item.get("name", "")
        try:
            response = fetch("GET", url, allow_redirects=True)
            for file_info in find_file_links(response.text, url):
                results.append({
                    "public_body_id": item["public_body_id"],
                    "name": name,
                    "disclosure_page_url": url,
                    **file_info,
                })
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": item["public_body_id"], "name": name},
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="Find disclosure log files on disclosure pages")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    results = process(input_data, step_dir)
    output = {
        "metadata": {"step": STEP_NAME, "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": results,
    }
    write_json(output_path, output)
    write_status(step_dir, len(results))
    print(f"Wrote {len(results)} records to {output_path}")


if __name__ == "__main__":
    main()
