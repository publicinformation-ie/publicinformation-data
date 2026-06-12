#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "match_gov_urls"
SOURCE_URL = "https://www.gov.ie/en/departments/"
SECTION_IDS = ["departments", "agencies", "local-authorities"]
MATCH_THRESHOLD = 0.85

_SUFFIX_RE = re.compile(
    r"\s*\b(clg|ltd|limited|dac|plc|teo|teoranta|cpt|uc)\b\.?\s*$",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\s*\(.*?\)\s*")
_WS_RE = re.compile(r"\s+")


def normalise(name: str) -> str:
    name = _PAREN_RE.sub(" ", name)
    name = _SUFFIX_RE.sub("", name)
    return _WS_RE.sub(" ", name).strip().lower()


def best_match(query_norm: str, candidates: list) -> tuple:
    """Return (url, score) for the best match at or above MATCH_THRESHOLD, else (None, best_score).

    candidates: list of (gov_ie_name, normalised_name, url)
    """
    best_score = 0.0
    best_url = None
    for _, norm, url in candidates:
        score = SequenceMatcher(None, query_norm, norm).ratio()
        if score > best_score:
            best_score = score
            best_url = url
    if best_score >= MATCH_THRESHOLD:
        return best_url, best_score
    return None, best_score


def scrape_gov_ie() -> list:
    """Fetch gov.ie departments page; return list of (name, stub_url) pairs."""
    response = fetch("GET", SOURCE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    seen = set()
    result = []
    for section_id in SECTION_IDS:
        section = soup.find("section", id=section_id)
        if not section:
            continue
        for link in section.find_all("a", href=True):
            name = link.get_text(strip=True)
            url = urljoin(SOURCE_URL, link["href"])
            if name and url not in seen:
                seen.add(url)
                result.append((name, url))
    return result


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    try:
        gov_entries = scrape_gov_ie()
    except Exception as e:
        print(f"Fatal: could not scrape gov.ie: {e}", file=sys.stderr)
        sys.exit(1)

    if not gov_entries:
        print("Fatal: gov.ie scrape returned 0 entries — page structure may have changed",
              file=sys.stderr)
        sys.exit(1)

    candidates = [(name, normalise(name), url) for name, url in gov_entries]

    match_log = []
    bodies = input_data.get("public_bodies") or input_data.get("results", [])
    for body in bodies:
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        norm = normalise(body["name"])
        matched_url, score = best_match(norm, candidates)
        match_log.append({
            "public_body_id": body_id,
            "name": body["name"],
            "normalised": norm,
            "matched_url": matched_url,
            "match_score": round(score, 4),
        })
        writer.append([{**body, "official_website_url": matched_url}])
        if verbose:
            print(".", end="", flush=True)

    write_json(Path(step_dir) / "match_log.json", match_log)


def main():
    parser = argparse.ArgumentParser(
        description="Match CSO public bodies to gov.ie URLs via fuzzy name matching"
    )
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
    if args.public_body is not None and not (
        input_data.get("results") or input_data.get("public_bodies")
    ):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               override_path=override_path)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
