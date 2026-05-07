#!/usr/bin/env python3
import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from scripts.http_utils import fetch, is_safe_url, search_serper, validate_url_or_raise

STEP_NAME = "find_foi_pages"
FOI_KEYWORDS = ["foi", "freedom of information", "freedom-of-information", "freedom_of_information"]
FOI_URL_KEYWORDS = [
    "foi", "freedom-of-information", "freedom_of_information",
    "freedom-information", "access-to-information",
]
FOI_PAGE_BLOCKLIST = {
    "https://www.gov.ie/en/topics/freedom-of-information",
    "https://www.gov.ie/en/topics/freedom-of-information/",
}


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


SECONDARY_CRAWL_KEYWORDS = ["contact", "about", "our-organisation", "organisation-information"]


def find_secondary_crawl_url(html, base_url):
    """Find a contact/about page URL from the homepage for secondary crawl."""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        if any(kw in href for kw in SECONDARY_CRAWL_KEYWORDS):
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

    for r in results:
        link = r.get("link", "")
        if not link:
            continue
        try:
            validate_url_or_raise(link, context="serper_result")
        except ValueError:
            continue
        path = urlparse(link).path.lower()
        if any(kw in path for kw in FOI_URL_KEYWORDS):
            return link

    return None


def process(input_data, step_dir, writer):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    reachable = [r for r in input_data["results"] if r["is_reachable"]]

    for body in reachable:
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = body["official_website_url"]
        name = body.get("name", "")
        try:
            validate_url_or_raise(url, context=f"process_{body_id}")
            response = fetch("GET", url, allow_redirects=True)
            foi_url = find_foi_link_on_page(response.text, url)
            source_method = "crawl"

            if foi_url is None:
                secondary_url = find_secondary_crawl_url(response.text, url)
                if secondary_url:
                    try:
                        secondary_response = fetch("GET", secondary_url, allow_redirects=True)
                        foi_url = find_foi_link_on_page(secondary_response.text, secondary_url)
                    except Exception:
                        pass

            if foi_url is None:
                if not os.environ.get("SERPER_API_KEY"):
                    raise ValueError(
                        f"SERPER_API_KEY not set and FOI page not found via crawl for {name} ({url}). "
                        "Set SERPER_API_KEY environment variable or fix crawl logic."
                    )
                foi_url = find_foi_via_serper(url, name)
                source_method = "serper"

            if foi_url is None:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "FoiPageNotFound",
                    "error_message": f"No FOI page found via crawl or serper for {name} ({url})",
                    "context": {"url": url, "public_body_id": body_id, "name": name},
                })
                writer.append([])
                continue

            validate_url_or_raise(foi_url, context=f"foi_url_{body_id}")

            if foi_url in FOI_PAGE_BLOCKLIST:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "BlocklistedFoiPageUrl",
                    "error_message": f"FOI page URL is blocklisted for {name}: {foi_url}",
                    "context": {"url": url, "public_body_id": body_id, "name": name, "foi_page_url": foi_url},
                })
                writer.append([])
                continue

            writer.append([{
                "public_body_id": body_id,
                "name": name,
                "official_website_url": url,
                "foi_page_url": foi_url,
                "source_method": source_method,
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

    # Uniqueness pass: remove candidates whose foi_page_url appears more than once
    url_counts = Counter(r["foi_page_url"] for r in writer.results)
    filtered = []
    for r in writer.results:
        if url_counts[r["foi_page_url"]] > 1:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "DuplicateFoiPageUrl",
                "error_message": f"foi_page_url appears for multiple bodies: {r['foi_page_url']}",
                "context": {
                    "url": r["official_website_url"],
                    "public_body_id": r["public_body_id"],
                    "name": r["name"],
                    "foi_page_url": r["foi_page_url"],
                },
            })
        else:
            filtered.append(r)
    writer.results = filtered


def retry(input_path, output_path, step_dir):
    """Re-process bodies listed in errors.json and merge into existing output.json."""
    errors_path = Path(step_dir) / "errors.json"

    if not errors_path.exists():
        print("No errors to retry")
        return

    errors = read_json(errors_path)
    if not errors:
        print("No errors to retry")
        return

    failed_ids = {e["context"]["public_body_id"] for e in errors}
    input_data = read_json(input_path)
    retry_input = {
        **input_data,
        "results": [r for r in input_data["results"] if r["public_body_id"] in failed_ids],
    }

    existing_results = read_json(output_path)["results"]

    # Process retry subset using a temporary writer
    tmp_output = output_path.with_suffix(".retry.tmp.json")
    try:
        retry_writer = IncrementalWriter(tmp_output, STEP_NAME, force=True)
        process(retry_input, step_dir, retry_writer)
        new_results = retry_writer.results
    finally:
        if tmp_output.exists():
            tmp_output.unlink()

    # Merge and re-check uniqueness across combined set
    all_candidates = existing_results + new_results
    url_counts = Counter(r["foi_page_url"] for r in all_candidates)
    merged = []
    for r in all_candidates:
        if url_counts[r["foi_page_url"]] > 1:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "DuplicateFoiPageUrl",
                "error_message": f"foi_page_url appears for multiple bodies: {r['foi_page_url']}",
                "context": {
                    "url": r["official_website_url"],
                    "public_body_id": r["public_body_id"],
                    "name": r["name"],
                    "foi_page_url": r["foi_page_url"],
                },
            })
        else:
            merged.append(r)

    output = {
        "metadata": {"step": STEP_NAME, "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": merged,
    }
    write_json(output_path, output)
    write_status(step_dir, len(merged))
    print(f"Retry: merged {len(merged)} records to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Find FOI pages for public bodies")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--force", action="store_true")
    group.add_argument("--retry", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if args.retry:
        retry(args.input, output_path, step_dir)
        sys.exit(0)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
