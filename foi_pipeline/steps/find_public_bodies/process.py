#!/usr/bin/env python3
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, write_json, write_status
from scripts.http_utils import RATE_LIMIT_DELAY, fetch

STEP_NAME = "find_public_bodies"
SOURCE_URL = "https://www.gov.ie/en/departments/"
BASE_ID = 1000


def scrape_public_bodies(step_dir):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    response = fetch("GET", SOURCE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    bodies = []
    seen_urls = set()
    body_id = BASE_ID + 1

    for link in soup.find_all("a", href=True):
        href = link["href"]
        full_url = urljoin(SOURCE_URL, href)

        if "/en/organisation/" not in full_url:
            continue
        if full_url in seen_urls:
            continue

        name = link.get_text(strip=True)
        if not name:
            continue

        seen_urls.add(full_url)
        bodies.append(
            {
                "public_body_id": body_id,
                "name": name,
                "official_website_url": full_url,
            }
        )
        body_id += 1
        time.sleep(RATE_LIMIT_DELAY)

    return bodies


def main():
    parser = argparse.ArgumentParser(description="Scrape Irish public bodies from gov.ie")
    parser.add_argument("--input", required=True, help="Previous step output (unused for first step)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    try:
        bodies = scrape_public_bodies(step_dir)
    except Exception as e:
        append_error(
            step_dir,
            {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": SOURCE_URL},
            },
        )
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

    write_json(output_path, bodies)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
