#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status
from scripts.http_utils import fetch

STEP_NAME = "find_disclosure_pages"
DISCLOSURE_KEYWORDS = ["disclosure", "log", "request"]


def find_disclosure_link(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        if any(kw in href or kw in text for kw in DISCLOSURE_KEYWORDS):
            return urljoin(base_url, link["href"])
    return None


def process(input_data, step_dir):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    results = []
    for item in input_data["results"]:
        url = item["foi_page_url"]
        name = item.get("name", "")
        try:
            response = fetch("GET", url, allow_redirects=True)
            disclosure_url = find_disclosure_link(response.text, url) or url
            results.append({
                "public_body_id": item["public_body_id"],
                "name": name,
                "foi_page_url": url,
                "disclosure_page_url": disclosure_url,
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
    parser = argparse.ArgumentParser(description="Find FOI disclosure log pages")
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
