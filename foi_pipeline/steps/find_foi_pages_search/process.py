#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from lib.apify_search import batch_search
from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import is_safe_url, validate_url_or_raise

STEP_NAME = "find_foi_pages_search"
FOI_URL_KEYWORDS = [
    "foi", "freedom-of-information", "freedom_of_information",
    "freedom-information", "access-to-information",
]
FOI_PAGE_BLOCKLIST = {
    "https://www.gov.ie/en/topics/freedom-of-information",
    "https://www.gov.ie/en/topics/freedom-of-information/",
}


def _build_query(website_url: str, name: str) -> str:
    domain = urlparse(website_url).netloc
    return f"site:{domain} {name} freedom of information"


def _pick_foi_url(results: list, website_url: str) -> str | None:
    parsed_site = urlparse(website_url)
    is_gov_ie = parsed_site.netloc == "www.gov.ie"
    path_prefix = parsed_site.path if is_gov_ie else None

    for r in results:
        link = r.get("link", "")
        if not link:
            continue
        try:
            validate_url_or_raise(link, context="apify_result")
        except ValueError:
            continue
        parsed_link = urlparse(link)
        if is_gov_ie and not parsed_link.path.startswith(path_prefix):
            continue
        if any(kw in parsed_link.path.lower() for kw in FOI_URL_KEYWORDS):
            return link
    return None


def process(input_data, step_dir, writer, crawl_errors=None, verbose=False):
    if crawl_errors is None:
        crawl_errors = []

    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for body in input_data.get("results", []):
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        writer.append([body])

    need_search = [
        e for e in crawl_errors
        if not writer.is_processed(e["context"]["public_body_id"])
    ]
    if not need_search:
        return

    query_map = {}
    for e in need_search:
        ctx = e["context"]
        query = _build_query(ctx["url"], ctx["name"])
        query_map[query] = e

    search_results = batch_search(list(query_map.keys()))

    for query, e in query_map.items():
        ctx = e["context"]
        body_id = ctx["public_body_id"]
        name = ctx["name"]
        url = ctx["url"]

        results = search_results.get(query, [])
        foi_url = _pick_foi_url(results, url)

        if foi_url is None or foi_url in FOI_PAGE_BLOCKLIST:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "FoiPageNotFound",
                "error_message": f"No FOI page found via Apify search for {name} ({url})",
                "context": {"url": url, "public_body_id": body_id, "name": name},
            })
            continue

        writer.append([{
            "public_body_id": body_id,
            "name": name,
            "official_website_url": url,
            "foi_page_url": foi_url,
            "source_method": "apify",
        }])


def main():
    parser = argparse.ArgumentParser(description="Search for FOI pages using Apify batch search")
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

    errors_src = step_dir.parent / "find_foi_pages" / "errors.json"
    crawl_errors = read_json(errors_src) if errors_src.exists() else []
    if args.public_body is not None:
        crawl_errors = [
            e for e in crawl_errors
            if e.get("context", {}).get("public_body_id") == args.public_body
        ]

    writer = IncrementalWriter(
        output_path, STEP_NAME,
        force=args.force,
        override_path=override_path,
        target_public_body=args.public_body,
    )

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, crawl_errors=crawl_errors, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
