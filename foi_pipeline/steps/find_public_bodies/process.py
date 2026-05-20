#!/usr/bin/env python3
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, write_json, write_status
from scripts.http_utils import fetch


def find_actual_homepage(page_url):
    """Find the actual homepage URL if the gov.ie page contains a 'separate website' link."""
    try:
        response = fetch("GET", page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        pattern = re.compile(r'there is a separate website for', re.IGNORECASE)
        elements = soup.find_all(string=pattern)

        for elem in elements:
            next_a = elem.find_next("a", href=True)
            if next_a:
                return urljoin(page_url, next_a["href"])

    except Exception as e:
        print(f"Warning: Could not check for separate website link on {page_url}: {e}", file=sys.stderr)

    return page_url


STEP_NAME = "find_public_bodies"
SOURCE_URL = "https://www.gov.ie/en/departments/"
SECTION_IDS = ["departments", "agencies", "local-authorities"]
SECTION_CATEGORIES = {
    "departments": "government department",
    "agencies": "public service body",
    "local-authorities": "local authority",
}
BASE_ID = 1000
MAX_WORKERS = 10

# These entries appear on the canonical source page but are not subject to FOI.
# Keyed by gov.ie source URL (before homepage resolution).
NOT_SUBJECT_TO_FOI_URLS = {
    "https://www.gov.ie/en/circulars-archive/",         # not a public body
    "https://www.gov.ie/en/coillte/",                   # AIE only, not FOI
    "https://www.gov.ie/en/coroner/",                   # not subject to FOI
    "https://www.gov.ie/en/criminal-assets-bureau/",    # not subject to FOI
    "https://www.gov.ie/en/criminal-injuries-compensation-scheme/",  # not a public body
}


def scrape_public_bodies(step_dir, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    response = fetch("GET", SOURCE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Phase 1: collect all (name, url, category) candidates — no HTTP calls
    candidates = []
    for section_id in SECTION_IDS:
        category = SECTION_CATEGORIES[section_id]
        section = soup.find("section", id=section_id)
        if not section:
            print(f"Warning: section '{section_id}' not found on page", file=sys.stderr)
            continue
        for link in section.find_all("a", href=True):
            full_url = urljoin(SOURCE_URL, link["href"])
            name = link.get_text(strip=True)
            if name:
                candidates.append((name, full_url, category))

    # Phase 2: resolve actual homepages in parallel (preserves order via executor.map)
    def resolve(item):
        name, full_url, category = item
        if urlparse(full_url).netloc.endswith("gov.ie"):
            actual_url = find_actual_homepage(full_url)
        else:
            actual_url = full_url
        return name, actual_url, category

    bodies = []
    seen_urls = set()
    body_id = BASE_ID + 1

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for (name, source_url, category), (_, actual_url, _) in zip(
            candidates, executor.map(resolve, candidates)
        ):
            if actual_url in seen_urls:
                continue
            if verbose:
                print(".", end="", flush=True)
            seen_urls.add(actual_url)
            entry = {
                "public_body_id": body_id,
                "name": name,
                "official_website_url": actual_url,
                "category": category,
                "status": {
                    "website_url": {"url": actual_url, "status": "not_attempted"},
                    "foi_page": {"url": None, "status": "not_attempted"},
                    "foi_email": {"email": None, "status": "not_attempted"},
                    "disclosures_page": {"url": None, "status": "not_attempted"},
                    "disclosure_files": {
                        "total": 0, "valid": 0, "failed": 0, "status": "not_attempted"
                    },
                    "foi_requests": {"valid": 0, "errors": 0, "status": "not_attempted"},
                },
            }
            if source_url in NOT_SUBJECT_TO_FOI_URLS:
                entry["not_subject_to_foi"] = True
            bodies.append(entry)
            body_id += 1

    return bodies


def main():
    parser = argparse.ArgumentParser(description="Scrape Irish public bodies from gov.ie")
    parser.add_argument("--input", required=True, help="Previous step output (unused for first step)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--verbose", action="store_true", help="Print a dot per website checked to show progress")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    try:
        bodies = scrape_public_bodies(step_dir, verbose=args.verbose)
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

    if not bodies:
        print("Fatal error: scrape returned 0 bodies - page structure may have changed", file=sys.stderr)
        sys.exit(1)

    output = {
        "metadata": {
            "step": "find_public_bodies",
            "completed_at": datetime.now(timezone.utc).isoformat()
        },
        "public_bodies": bodies
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    if args.verbose:
        print()
    print(f"Wrote {len(bodies)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
