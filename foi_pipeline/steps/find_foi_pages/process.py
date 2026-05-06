#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status
from scripts.http_utils import fetch, search_serper

STEP_NAME = "find_foi_pages"
FOI_KEYWORDS = ["foi", "freedom of information", "freedom-of-information", "freedom_of_information"]


def find_foi_link_on_page(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        if href.startswith("mailto:"):
            continue
        text = link.get_text(strip=True).lower()
        if any(kw in href or kw in text for kw in FOI_KEYWORDS):
            return urljoin(base_url, link["href"])
    return None


def find_foi_via_serper(website_url, name):
    domain = urlparse(website_url).netloc
    query = f"site:{domain} {name} freedom of information"
    results = search_serper(query)
    if not results:
        return None

    parsed = urlparse(website_url)
    if parsed.netloc == "www.gov.ie":
        path_prefix = parsed.path
        results = [r for r in results if urlparse(r.get("link", "")).path.startswith(path_prefix)]

    if results:
        return results[0].get("link")
    return None


def process(input_data, step_dir):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    reachable = [r for r in input_data["results"] if r["is_reachable"]]
    results = []

    for body in reachable:
        url = body["official_website_url"]
        name = body.get("name", "")
        try:
            response = fetch("GET", url, allow_redirects=True)
            foi_url = find_foi_link_on_page(response.text, url)
            source_method = "crawl"

            if foi_url is None:
                # Need to use Serper - check if API key is available
                if not os.environ.get("SERPER_API_KEY"):
                    raise ValueError(
                        f"SERPER_API_KEY not set and FOI page not found via crawl for {name} ({url}). "
                        "Set SERPER_API_KEY environment variable or fix crawl logic."
                    )
                foi_url = find_foi_via_serper(url, name)
                source_method = "serper"

            if foi_url is None:
                continue

            results.append({
                "public_body_id": body["public_body_id"],
                "name": name,
                "official_website_url": url,
                "foi_page_url": foi_url,
                "source_method": source_method,
            })
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": body["public_body_id"], "name": name},
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="Find FOI pages for public bodies")
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
