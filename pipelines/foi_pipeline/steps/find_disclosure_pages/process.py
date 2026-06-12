#!/usr/bin/env python3
import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

from bs4 import BeautifulSoup

from lib.apify_search import batch_search
from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url, validate_url_or_raise
from steps.find_disclosure_pages.domains import find_disclosure_page as domain_find, _gov_ie_query

STEP_NAME = "find_disclosure_pages"


def _tokenize(*strings):
    """Lowercase, split on non-alphanumeric runs, return the set of word tokens.

    Token matching (vs. substring matching) is what stops 'log' from matching
    login / blog / logo / technology / geology / catalogue.
    """
    tokens = set()
    for s in strings:
        for tok in re.split(r"[^a-z0-9]+", (s or "").lower()):
            if tok:
                tokens.add(tok)
    return tokens


# Tokens that, if present, immediately disqualify a link. These are the words
# that historically caused false positives (publication-scheme, protected
# disclosures, how-to/make-a-request forms, annual reports, login/logo/blog).
NEGATIVE_TOKENS = {
    "protected", "scheme", "form", "login", "logo", "blog",
    "annual", "report", "reports",
    "how", "make", "apply", "guide", "guidance",
}

_DISCLOSURE = {"disclosure", "disclosures"}
_LOG = {"log", "logs"}
_DECISION = {"decision", "decisions"}
_REQUEST = {"request", "requests"}
_PUBLISHED = {"published"}

ACCEPT_THRESHOLD = 40  # links scoring below this are treated as "no match"


def _score_link(tokens):
    """Score a candidate link's combined href+anchor tokens. Higher = more
    confidently a disclosure log. 0 = reject."""
    if tokens & NEGATIVE_TOKENS:
        return 0
    disclosure = bool(tokens & _DISCLOSURE)
    log = bool(tokens & _LOG)
    foi = "foi" in tokens
    decision = bool(tokens & _DECISION)
    request = bool(tokens & _REQUEST)
    published = bool(tokens & _PUBLISHED)

    if disclosure and log:
        return 100
    if foi and log:
        return 90
    if foi and decision:
        return 80
    if published and foi:
        return 70
    if disclosure:
        return 40
    if foi and request:
        return 10
    return 0


def find_disclosure_link(html, base_url):
    """Return (best_url, score) for the highest-scoring disclosure-log link on
    the page, or None if nothing scores at or above ACCEPT_THRESHOLD.

    Unlike the old first-match-wins behaviour, this scores every candidate and
    returns the best, so a real 'foi-disclosure-log' link beats a 'login' link
    that happens to appear earlier in the DOM.
    """
    soup = BeautifulSoup(html, "html.parser")
    best = None
    best_score = 0
    _DOC_EXTS = (".pdf", ".docx", ".xlsx", ".xls", ".odt", ".doc")
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:  # Irish-language mirror pages
            continue
        if href.lower().split("?")[0].endswith(_DOC_EXTS):
            continue
        tokens = _tokenize(href, link.get_text(strip=True))
        sc = _score_link(tokens)
        if sc <= best_score:
            continue
        full_url = urljoin(base_url, href)
        if not is_safe_url(full_url):
            continue
        if urldefrag(full_url)[0] == urldefrag(base_url)[0]:
            continue  # same-page anchor only
        best, best_score = full_url, sc
    if best is not None and best_score >= ACCEPT_THRESHOLD:
        return best, best_score
    return None


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    items = input_data["results"]

    # Pre-pass: collect queries for gov.ie bodies not yet processed
    gov_ie_queries = {}
    for item in items:
        body_id = item["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = item["foi_page_url"]
        if urlparse(url).netloc.endswith("gov.ie"):
            name = item.get("name", "")
            gov_ie_queries[body_id] = _gov_ie_query(name)

    batch_results = {}
    if gov_ie_queries:
        batch_results = batch_search(list(gov_ie_queries.values()))

    for item in items:
        body_id = item["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = item["foi_page_url"]
        name = item.get("name", "")
        is_gov_ie = urlparse(url).netloc.endswith("gov.ie")
        if verbose:
            print(f"  {name} ({url}) ...", end=" ", flush=True)
        t_start = time.perf_counter()
        method = "unknown"
        try:
            validate_url_or_raise(url, context=f"disclosure_page_{body_id}")

            # 1. Crawl first for all bodies
            response = fetch("GET", url, allow_redirects=True)
            match = find_disclosure_link(response.text, url)
            if match:
                disclosure_url, link_score = match
                method = "crawl"
                confidence = "high" if link_score >= 70 else "medium"
            elif is_gov_ie:
                # 2. Apify fallback for gov.ie only — score the result and reject below threshold
                apify_url = domain_find(name, url, batch_results=batch_results)
                if apify_url is not None and _score_link(_tokenize(apify_url)) >= ACCEPT_THRESHOLD:
                    disclosure_url = apify_url
                    method = "domain"
                    confidence = "high"
                else:
                    disclosure_url = url
                    method = "foi_page_fallback"
                    confidence = "none"
            else:
                # 3. FOI page fallback for non-gov.ie bodies
                disclosure_url = url
                method = "foi_page_fallback"
                confidence = "none"

            validate_url_or_raise(disclosure_url, context=f"disclosure_url_{body_id}")
            writer.append([{
                "public_body_id": body_id,
                "name": name,
                "foi_page_url": url,
                "disclosure_page_url": disclosure_url,
                "confidence": confidence,
                "source_method": method,
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
        if verbose:
            elapsed = time.perf_counter() - t_start
            print(f"[{method:6s}] {elapsed:5.1f}s", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Find FOI disclosure log pages")
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
                               override_path=override_path,
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
                               target_public_body=args.public_body)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
