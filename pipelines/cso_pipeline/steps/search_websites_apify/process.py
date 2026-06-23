#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from lib.apify_search import batch_search
from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "search_websites_apify"
STOP_WORDS = frozenset({"ireland", "limited", "authority", "board", "office", "the", "and", "of"})
_TOKEN_RE = re.compile(r"[a-z]+")


def build_query(body: dict) -> str:
    name = body.get("name", "")
    gov_dept = body.get("government_department")
    if gov_dept:
        return f'"{name}" {gov_dept} Ireland official website'
    return f'"{name}" Ireland public body'


def score_confidence(domain: str, body_name: str) -> str:
    """Return "high" if domain contains a meaningful name token, else "low"."""
    domain_lower = domain.lower()
    name_tokens = _TOKEN_RE.findall(body_name.lower())
    meaningful = [t for t in name_tokens if len(t) > 4 and t not in STOP_WORDS]
    for token in meaningful:
        if token in domain_lower:
            return "high"
    return "low"


def process(input_data, step_dir, writer, verbose=False):
    bodies = input_data.get("public_bodies") or input_data.get("results", [])

    to_search = []
    passthrough = []
    for body in bodies:
        if writer.is_processed(body["public_body_id"]):
            continue
        if body.get("llm_confidence") == "high":
            passthrough.append(body)
        else:
            to_search.append(body)

    for body in passthrough:
        writer.append([{**body, "apify_website_url": None, "apify_confidence": None}])

    if not to_search:
        return

    queries = [build_query(b) for b in to_search]
    try:
        results = batch_search(queries)
    except Exception as e:
        append_error(step_dir, {
            "step": STEP_NAME, "error_type": "ApifyError",
            "error_message": str(e), "context": {},
        })
        print(f"Fatal: Apify error: {e}", file=sys.stderr)
        sys.exit(1)

    for body, query in zip(to_search, queries):
        body_id = body["public_body_id"]
        organic = results.get(query, [])
        if not organic:
            append_error(step_dir, {
                "step": STEP_NAME, "error_type": "WebsiteNotFound",
                "error_message": "Apify returned no results",
                "context": {"public_body_id": body_id, "query": query},
            })
            enriched = {**body, "apify_website_url": None, "apify_confidence": "not_found"}
        else:
            url = organic[0].get("link") or organic[0].get("url", "")
            domain = urlparse(url).netloc
            enriched = {
                **body,
                "apify_website_url": url,
                "apify_confidence": score_confidence(domain, body.get("name", "")),
            }
        writer.append([enriched])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Apify website search for CSO public bodies")
    add_common_args(parser)
    args = parser.parse_args()
    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               override_path=step_dir / "override.json")
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")
    if args.force:
        write_json(step_dir / "errors.json", [])
    process(input_data, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
