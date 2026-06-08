#!/usr/bin/env python3
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url

STEP_NAME = "find_disclosure_files"
FILE_EXTENSIONS = {".pdf": "pdf", ".xlsx": "xlsx", ".xls": "xls"}
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

_FOI_KEYWORDS = ['disclosure', 'foi-log', 'foi_log', 'published-foi-requests', 'foi-decisions', 'foi-request', 'freedom-of-information']
_NEGATIVE_KEYWORDS = [
    'policy', 'scheme', 'guide', 'minutes', 'report', 'annual', 'agenda',
    'protected-disclosure', 'annual-report', 'debaterecord', 'governance',
    'committee_on', 'strategic-plan', 'climate-action', 'expense',
    'diary', 'mou', 'lrd-opinion', 'planningapplicationsrefused',
    'fiscal', 'committee', 'planning-application', 'code', 'statement', 'plan', 'press', 'elections',
    'strategy', 'leaflet', 'article', 'application form', '-form', '_form', 'assessment', 'tax', 'grants',
    'template', 'award', 'irishstatute', 'conference', 'training', 'guidance',
    'media-release', 'transcript', 'video-transcript', 'video',
    'audit', 'disability', 'complaints', 'procedure', 'customer-charter', 'lobbying',
    'data-privacy', 'data-protection', 'privacy', 'privacy-notice', 'terms-of-reference',
    'model-contract', 'written-resolution', 'board-resolution',
    'circular', 'bill', 'legislation', 'act', 'image', 'exhibit', 'worksheet',
    'book-list', 'booklist', 'newsletter', 'brochure', 'pamphlet', 'poster',
    'presentation', 'slides', 'meeting', 'session',
    'financial-stability-review', 'financial-stability-notes', 'quarterly-bulletin',
    'economic-letter',
]


def _url_score(url):
    """Score a URL for whether it's likely an FOI disclosure log.

    Returns 1 (accept) or -1000 (reject). Negative keywords are matched
    against the URL path only — not the domain — so bodies whose domain
    contains a negative word (e.g. audit.gov.ie) are not incorrectly
    filtered.
    
    Protected Disclosures (whistleblowing) is a different legal framework
    from FOI and must be explicitly filtered even though it contains
    the word "disclosure".
    """
    url_lower = str(url).lower()
    url_path = urlparse(url_lower).path

    # Protected Disclosures is NOT FOI - filter it out even if it has positive keywords
    if 'protected' in url_lower and 'disclosure' in url_lower:
        return -1000

    has_positive = any(k in url_lower for k in _FOI_KEYWORDS)

    if not has_positive:
        for k in _NEGATIVE_KEYWORDS:
            if k in url_path:
                return -1000

    return 1


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

        if _url_score(full_url) < 0:
            continue

        link_text = link.get_text(strip=True)
        ext = Path(urlparse(href).path).suffix.lower()

        if ext in FILE_EXTENSIONS:
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                files.append({"file_url": full_url, "file_type": FILE_EXTENSIONS[ext]})
        elif follow_year_pages and YEAR_PATTERN.search(link_text):
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
