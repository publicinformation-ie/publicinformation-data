#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urldefrag, urlparse

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, errors_outside_bodies, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url, validate_url_or_raise
from steps.minutes_scoring import collect_yield  # noqa: E402

STEP_NAME = "find_meeting_minutes_pages"

ACCEPT_THRESHOLD = 60

NEGATIVE_TOKENS = {
    "login", "logo", "blog", "annual", "report", "reports", "archive",
    "agenda", "agendas", "publication", "publications", "scheme",
    # Committees that publish yield-rich minutes pages but are not the
    # council: LCDC, Local Community Safety Partnership, Local Traveller
    # Accommodation Consultative Committee, Joint Policing Committee.
    "lcdc", "lcsp", "ltacc", "jpc",
}
_MINUTES = {"minutes", "minute"}
_MEETING = {"meeting", "meetings"}
_MUNICIPAL = {"municipal"}
_DISTRICT = {"district", "districts"}


def _tokenize(*strings):
    tokens = set()
    for s in strings:
        # Decode first: "Minutes%20JPC" must yield "jpc", not "20jpc".
        for tok in re.split(r"[^a-z0-9]+", unquote(s or "").lower()):
            if tok:
                tokens.add(tok)
    return tokens


def _score_link(tokens):
    """Higher = more confidently a minutes page. 0 = reject.

    An explicit 'minutes' link (e.g. "Council Minutes") scores at least 70 and
    is always accepted; a bare 'meeting' page (e.g. "Meeting stuff") scores
    below ACCEPT_THRESHOLD and is rejected. Municipal-district meeting pages
    keep a meeting+municipal tier above the threshold. Combined
    "Minutes & Agendas" listings are valid minutes sources, so agenda tokens
    disqualify only when no minutes token is present; every other negative
    token still disqualifies outright.
    """
    if tokens & (NEGATIVE_TOKENS - {"agenda", "agendas"}):
        return 0
    if (tokens & {"agenda", "agendas"}) and not (tokens & _MINUTES):
        return 0
    minutes = bool(tokens & _MINUTES)
    meeting = bool(tokens & _MEETING)
    municipal = bool(tokens & _MUNICIPAL)
    district = bool(tokens & _DISTRICT)
    if minutes and meeting:
        return 100
    if minutes and district:
        return 90
    if meeting and municipal:
        return 70
    if minutes:
        return 80
    if meeting:
        return 50
    return 0


def find_minutes_link(html, base_url):
    """Return (best_url, score) for the highest-scoring minutes-page link, or None."""
    soup = BeautifulSoup(html, "html.parser")
    best = None
    best_score = 0
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:
            continue
        tokens = _tokenize(href, link.get_text(strip=True))
        sc = _score_link(tokens)
        if sc <= best_score:
            continue
        full_url = urljoin(base_url, href)
        if not is_safe_url(full_url):
            continue
        if urldefrag(full_url)[0] == urldefrag(base_url)[0]:
            continue
        best, best_score = full_url, sc
    if best is not None and best_score >= ACCEPT_THRESHOLD:
        return best, best_score
    return None


def _best_hub_link(html, base_url):
    """Highest-scoring sub-threshold hub link (score > 0), same skips as find_minutes_link."""
    soup = BeautifulSoup(html or "", "html.parser")
    best = None
    best_score = 0
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:
            continue
        sc = _score_link(_tokenize(href, link.get_text(strip=True)))
        if sc <= best_score:
            continue
        full_url = urljoin(base_url, href)
        if not is_safe_url(full_url):
            continue
        if urldefrag(full_url)[0] == urldefrag(base_url)[0]:
            continue
        best, best_score = full_url, sc
    return best


def _try_one_hop(home_html, home_url, bid, district, step_dir):
    """Follow the single best hub link once; accept its minutes hit iff the
    hub page is PDF-yield positive. Returns (url or None, "crawl").
    Fetch failures are fail-closed (error logged, None). step_dir may be
    None in tests (error logging skipped)."""
    hub_url = _best_hub_link(home_html or "", home_url)
    if not hub_url:
        return None, "crawl"
    try:
        hub_html = fetch("GET", hub_url, allow_redirects=True).text
    except Exception as e:
        if step_dir is not None:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "HubFetchFailed",
                "error_message": str(e),
                "context": {"url": hub_url, "public_body_id": bid,
                            "municipal_district": district},
            })
        return None, "crawl"
    hit = find_minutes_link(hub_html, hub_url)
    if not hit:
        return None, "crawl"
    dest_url, _score = hit
    if not collect_yield(hub_html, hub_url)["positive"]:
        return None, "crawl"
    return dest_url, "crawl"


def override_sources(authorities, overrides):
    """Map override.json entries to minutes_source records for the given authorities."""
    records = []
    for rec in overrides:
        bid = rec.get("public_body_id")
        if bid is None:
            continue
        record = {
            "public_body_id": bid,
            "municipal_district": rec.get("municipal_district"),
            "minutes_page_url": rec["minutes_page_url"],
            "source_method": "override",
            "overridden": True,
        }
        # Optional per-source listing-walk config for find_minutes_files.
        if rec.get("walk"):
            record["walk"] = rec["walk"]
        records.append(record)
    return records


def unemitted_sources(writer, records):
    """Records not yet persisted: a record is unemitted unless its
    `minutes_page_url` is already held by the writer. Keying on
    `minutes_page_url` (unique per district/council page) instead of
    `public_body_id` lets a resumed run keep every district page of a body."""
    processed = {r.get("minutes_page_url") for r in writer.results
                 if r.get("minutes_page_url")}
    return [r for r in records if r.get("minutes_page_url") not in processed]


def child_page_urls(html, base_url, pattern):
    """URLs of links whose href matches the `pattern` regex, de-duplicated in
    page order. Skips the parent itself and anything unsafe."""
    rx = re.compile(pattern)
    soup = BeautifulSoup(html or "", "html.parser")
    base = urldefrag(base_url)[0]
    urls = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if not rx.search(href):
            continue
        full = urldefrag(urljoin(base_url, href))[0]
        if full == base or full in urls or not is_safe_url(full):
            continue
        urls.append(full)
    return urls


def expand_child_pages(overrides, step_dir):
    """Replace each override carrying `child_pages` (a regex matched against
    link hrefs on its parent page) with one override per child page, so a
    parent index like Sligo's /Minutes/ yields every year's minutes page.
    A failed or empty parent fetch is logged and yields no records (fail-closed)."""
    expanded = []
    for rec in overrides:
        pattern = rec.get("child_pages")
        if not pattern:
            expanded.append(rec)
            continue
        parent = rec["minutes_page_url"]
        try:
            html = fetch("GET", parent, allow_redirects=True).text
            children = child_page_urls(html, parent, pattern)
            if not children:
                raise ValueError(f"no child pages matching {pattern!r}")
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": parent, "public_body_id": rec.get("public_body_id"),
                            "municipal_district": rec.get("municipal_district")},
            })
            continue
        for child in children:
            child_rec = {k: v for k, v in rec.items() if k != "child_pages"}
            child_rec["minutes_page_url"] = child
            expanded.append(child_rec)
    return expanded


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    authorities = input_data["results"]
    scoped_ids = {a["public_body_id"] for a in authorities}
    # A --public-body run replaces only its own bodies' errors.
    write_json(errors_path, errors_outside_bodies(errors_path, scoped_ids))

    override_path = step_dir / "override.json"
    overrides = read_json(override_path) if override_path.exists() else []
    # Scoped runs must not fetch or emit other bodies' overrides.
    overrides = [o for o in overrides if o.get("public_body_id") in scoped_ids]
    overrides = expand_child_pages(overrides, step_dir)

    records = override_sources(authorities, overrides)

    # For bodies/districts NOT covered by an override, crawl the homepage.
    covered = {(r["public_body_id"], r["municipal_district"]) for r in records}
    pending = []
    for auth in authorities:
        bid = auth["public_body_id"]
        for district in [None] + list(auth.get("municipal_districts", [])):
            if (bid, district) not in covered:
                pending.append((auth, district))

    for auth, district in pending:
        bid = auth["public_body_id"]
        try:
            url = auth.get("official_website_url")
            validate_url_or_raise(url, context=f"minutes_page_{bid}")
            response = fetch("GET", url, allow_redirects=True)
            match = find_minutes_link(response.text, url)
            if match:
                minutes_url, score = match
                source_method = "crawl"
            else:
                minutes_url, source_method = _try_one_hop(
                    response.text, url, bid, district, step_dir)
                if minutes_url is None:
                    raise ValueError("no minutes page link above threshold on homepage")
            records.append({
                "public_body_id": bid,
                "municipal_district": district,
                "minutes_page_url": minutes_url,
                "source_method": source_method,
            })
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": auth.get("official_website_url"),
                            "public_body_id": bid, "municipal_district": district},
            })
        if verbose:
            print(".", end="", flush=True)

    # Never re-emit records the writer already holds (resume / scoped runs).
    writer.append(unemitted_sources(writer, records))


def main():
    parser = argparse.ArgumentParser(
        description="Locate the page(s) publishing meeting minutes for each authority"
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
    if args.public_body is not None and not (input_data.get("results")):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
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
