#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from steps.find_meeting_minutes_pages.process import (
    ACCEPT_THRESHOLD,
    _score_link,
    _tokenize,
)

from lib.apify_search import batch_search
from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import is_safe_url, validate_url_or_raise

STEP_NAME = "find_meeting_minutes_pages_search"


def _build_query(website_url: str, name: str) -> str:
    domain = urlparse(website_url).netloc
    return f"site:{domain} {name} council meeting minutes"


def _pick_minutes_url(results: list) -> str | None:
    """Best Apify result URL per the crawl step's tiered scorer.

    Tokenises each candidate's URL + search-result title with the same
    vocabulary/weights as find_meeting_minutes_pages.find_minutes_link
    (single source of truth via import). Accepts only scores >=
    ACCEPT_THRESHOLD; skips /ga/ and unsafe URLs like the crawl does.
    No gov.ie path-prefix rule: every council has its own domain, and the
    site: query already constrains results to it.
    """
    best = None
    best_score = 0
    for r in results:
        link = r.get("link", "")
        if not link:
            continue
        if "/ga/" in urlparse(link).path:
            continue
        try:
            validate_url_or_raise(link, context="apify_result")
        except ValueError:
            continue
        if not is_safe_url(link):
            continue
        score = _score_link(_tokenize(link, r.get("title", "")))
        if score > best_score:
            best, best_score = link, score
    if best is not None and best_score >= ACCEPT_THRESHOLD:
        return best
    return None


def _error(step_dir, error_type, message, url, body_id, name):
    append_error(step_dir, {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": {"url": url, "public_body_id": body_id, "name": name,
                    "municipal_district": None},
    })


def process(input_data, step_dir, writer, crawl_errors=None,
            authorities_by_id=None, verbose=False):
    if crawl_errors is None:
        crawl_errors = []
    if authorities_by_id is None:
        authorities_by_id = {}

    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    for rec in input_data.get("results", []):
        if writer.is_processed(rec["minutes_page_url"]):
            continue
        writer.append([rec])

    # Per-body-only granularity (approved): one search per failed body.
    # Bodies already holding any page record are left untouched — partial
    # (body, district) coverage is NOT backfilled by this step.
    present_body_ids = {r["public_body_id"] for r in writer.results
                        if "public_body_id" in r}
    seen = set()
    need_search = []
    for e in crawl_errors:
        bid = e.get("context", {}).get("public_body_id")
        if bid is None or bid in present_body_ids or bid in seen:
            continue
        seen.add(bid)
        need_search.append(e)
    if not need_search:
        return

    query_map = {}
    for e in need_search:
        ctx = e["context"]
        bid = ctx["public_body_id"]
        auth = authorities_by_id.get(bid, {})
        name = auth.get("name") or ctx.get("name") or f"body {bid}"
        site_url = auth.get("official_website_url") or ctx.get("url")
        if not site_url:
            _error(step_dir, "MissingWebsiteUrl",
                   f"No website to search for minutes page: {name} ({bid})",
                   site_url, bid, name)
            continue
        try:
            validate_url_or_raise(site_url, context=f"search_{bid}")
        except ValueError as exc:
            _error(step_dir, "MissingWebsiteUrl", str(exc), site_url, bid, name)
            continue
        query_map[_build_query(site_url, name)] = (bid, name, site_url)

    if not query_map:
        return

    search_results = batch_search(list(query_map.keys()))

    for query, (bid, name, site_url) in query_map.items():
        minutes_url = _pick_minutes_url(search_results.get(query, []))
        if minutes_url is None:
            _error(step_dir, "MinutesPageNotFound",
                   f"No minutes page found via Apify search for {name} ({site_url})",
                   site_url, bid, name)
            continue
        writer.append([{
            "public_body_id": bid,
            "municipal_district": None,
            "minutes_page_url": minutes_url,
            "source_method": "apify",
        }])


def main():
    parser = argparse.ArgumentParser(
        description="Search for meeting minutes pages using Apify batch search")
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

    errors_src = step_dir.parent / "find_meeting_minutes_pages" / "errors.json"
    crawl_errors = read_json(errors_src) if errors_src.exists() else []
    authorities_src = step_dir.parent / "find_local_authorities" / "output.json"
    authorities_by_id = {}
    if authorities_src.exists():
        for a in read_json(authorities_src).get("results", []):
            if a.get("public_body_id") is not None:
                authorities_by_id[a["public_body_id"]] = a
    if args.public_body is not None:
        crawl_errors = [
            e for e in crawl_errors
            if e.get("context", {}).get("public_body_id") == args.public_body
        ]

    writer = IncrementalWriter(
        output_path, STEP_NAME,
        key_field="minutes_page_url",
        force=args.force,
        override_path=override_path,
        target_public_body=args.public_body,
    )

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, crawl_errors=crawl_errors,
            authorities_by_id=authorities_by_id, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
