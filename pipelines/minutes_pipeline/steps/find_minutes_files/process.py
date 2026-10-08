#!/usr/bin/env python3
import argparse
import base64
import binascii
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url
from lib.date_parse import parse_date

STEP_NAME = "find_minutes_files"

_PDF_EXT = ".pdf"
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_YEAR_ANYWHERE_RE = re.compile(r"(19|20)\d{2}\b")
_LISTING_TOKENS = {
    "meeting", "meetings", "minutes", "minute", "council", "municipal",
    "district", "districts",
}
_NOT_MINUTES_TOKENS = {
    "agenda", "agendas", "report", "reports", "scheme", "annual",
    "published", "minutes-of-agenda", "notice", "notices", "publication",
    "publications",
    # Verbatim transcripts (Wicklow) duplicate the minutes of the same meeting.
    "transcript", "transcripts",
}

# Digitised archive collections (e.g. Wicklow's 1800s minute books) match the
# minutes keywords but are out of scope for a current-motions dataset.
# Deliberately NOT matching archiv*/archive*: councils file current minutes
# under "ArchivedMeetings"/"meetings archive" folders (Kildare, Longford) —
# those are real minutes. Heritage/collections/museum/library/digitised
# paths denote heritage collections instead.
_ARCHIVE_PATH_RE = re.compile(
    r"heritage|collections?|museums?|librar|digitised|digitized", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(1\d{3}|20\d{2})\b")
_HISTORICAL_CUTOFF_YEAR = 1990


def _tokens(*strings):
    toks = set()
    for s in strings:
        for t in re.split(r"[^a-z0-9]+", (s or "").lower()):
            if t:
                toks.add(t)
    return toks


def _is_year_listing(text, href):
    """True for an anchor that links to a year's meeting listing: link text
    contains a 4-digit year and the text/URL indicates a meeting listing
    (e.g. '2024', '2024 Council Meetings', 'Minutes 2021', '/minutes/2024')."""
    if not _YEAR_ANYWHERE_RE.search((text or "").strip()):
        return False
    return bool(_tokens(text, href) & _LISTING_TOKENS)


def _extract_date(text: str):
    """Return ISO date if `text` contains a deterministic date, else None."""
    if not text:
        return None
    # ISO YYYY-MM-DD
    m = re.search(r"(19|20)\d{2}-\d{2}-\d{2}", text)
    if m:
        iso = m.group(0)
        try:
            datetime.strptime(iso, "%Y-%m-%d")
            return iso
        except ValueError:
            return None
    # D Month YYYY  or  D MonthName YYYY
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if m:
        day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
        month = _MONTHS.get(month_name)
        if month is None:
            return None
        try:
            return datetime(int(year), month, int(day)).date().isoformat()
        except ValueError:
            return None
    return None


def parse_meeting_date(link_text, file_url):
    """Deterministic date from link text/URL, else None (extract_motions may
    resolve it from content; canonicalize fails closed if it stays None)."""
    iso = _extract_date(link_text) or _extract_date(file_url)
    return iso


def _looks_like_minutes(link_text, href):
    """Filter agendas/reports/public notices out where distinguishable; keep
    minutes PDFs. A vetoing folder name alone doesn't reject a file that
    names itself minutes: Longford files minutes under
    '.../2026-meeting-agendas-and-minutes/'. A neutral name in such a folder
    stays rejected (Wicklow's 'Minutes-Agendas/2021/Ordinary Meeting ...pdf'
    may be an agenda or a transcript)."""
    file_name = urlparse(href or "").path.rsplit("/", 1)[-1]
    own_tokens = _tokens(link_text, file_name)
    if own_tokens & _NOT_MINUTES_TOKENS:
        return False
    if _tokens(href) & _NOT_MINUTES_TOKENS:
        return bool(own_tokens & {"minutes", "minute"})
    if _tokens(link_text, href) & {"minutes", "meeting", "minute"}:
        return True
    return False


def _decode_b64(value):
    """`value` base64-decoded to text, or None when it isn't base64 text."""
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4),
                                validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None


def _pdf_name(url):
    """The PDF file name `url` points at, or None. Usually the path suffix,
    but file-manager download links carry the file name in a query param,
    plain (?file=Minutes.pdf) or base64-encoded (Galway City's
    ?r=/download&path=<base64>), under a path with no .pdf suffix."""
    parsed = urlparse(url)
    if parsed.path.lower().endswith(_PDF_EXT):
        return parsed.path
    for values in parse_qs(parsed.query).values():
        for value in values:
            for candidate in (value, _decode_b64(value)):
                if candidate and candidate.lower().endswith(_PDF_EXT):
                    return candidate
    return None


def _is_html(response):
    """False when the server says the body is not HTML (a PDF or other file
    behind a year-looking link). A missing Content-Type is treated as HTML."""
    content_type = response.headers.get("Content-Type", "")
    return not content_type or "html" in content_type.lower()


def _exclusion_reason(link_text, file_url):
    """Return (error_type, message) when a would-be-kept minutes link is
    out of scope, else None. Fail-open: links with no archive/year signal
    are kept — only positive archive-path or pre-cutoff-year evidence
    excludes. Every exclusion is logged to errors.json by the caller."""
    if _ARCHIVE_PATH_RE.search(file_url or ""):
        return ("ArchivedDocument",
                f"minutes link under an archive/heritage path: {file_url}")
    years = [int(y) for y in _YEAR_RE.findall(f"{link_text or ''} {file_url or ''}")]
    # Exclude only when EVERY year found predates the cutoff: a modern year
    # anywhere (meeting date, DDMM-YYYY like 1909-2021, filesize fragments
    # like 1016KB next to 2019) fails open to keep. No year at all also keeps.
    if years and all(y < _HISTORICAL_CUTOFF_YEAR for y in years):
        return ("HistoricalDocument",
                f"minutes link predates {_HISTORICAL_CUTOFF_YEAR}: "
                f"{link_text!r} {file_url}")
    return None


def _collect_pdf_link(link, full, source, records, excluded_out,
                      seen=None, minutes_token_required=False):
    """Classify one anchor `link` (resolved to `full`). Returns False when it
    isn't a PDF link; otherwise records it as minutes, logs it to
    `excluded_out` as archival/historical, or drops it as a non-minutes PDF,
    and returns True. `seen` (a set of file URLs) dedupes when given.
    `minutes_token_required` rejects links naming no minute(s): on a
    per-meeting detail page every link says "meeting", so that token is no
    signal there ("Replies to Questions - Full Meeting of ...")."""
    href = str(link["href"])
    text = link.get_text(strip=True)
    pdf_name = _pdf_name(full)
    if not pdf_name:
        return False
    # A name recovered from the query string is the only readable signal
    # (the href itself may be base64); a suffix-path link keeps classifying
    # on the raw href/URL as before.
    named_url = full
    if not urlparse(full).path.lower().endswith(_PDF_EXT):
        href = named_url = pdf_name
    if seen is not None and full in seen:
        return True
    if not _looks_like_minutes(text, href):
        return True
    if minutes_token_required and not _tokens(text, href) & {"minutes", "minute"}:
        return True
    if seen is not None:
        seen.add(full)
    reason = _exclusion_reason(text, named_url)
    if reason is None or excluded_out is None:
        # No out-list means no log sink: fail open and keep the record
        # rather than silently dropping it.
        records.append({
            "public_body_id": source["public_body_id"],
            "municipal_district": source.get("municipal_district"),
            "minutes_page_url": source["minutes_page_url"],
            "file_url": full,
            "meeting_date": parse_meeting_date(text, named_url),
            "link_text": text,
        })
    else:
        error_type, message = reason
        excluded_out.append({
            "step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": message,
            "context": {
                "file_url": full,
                "link_text": text,
                "minutes_page_url": source["minutes_page_url"],
                "public_body_id": source["public_body_id"],
                "municipal_district": source.get("municipal_district"),
            },
        })
    return True


def _fetch_soup(url):
    """Parsed HTML at `url`, or None when the response isn't HTML."""
    response = fetch("GET", url, allow_redirects=True)
    if not _is_html(response):
        return None
    return BeautifulSoup(response.text, "html.parser")


def _collect_walk(source, base_url, walk, excluded_out):
    """Opt-in listing walk, configured per source by the override's `walk`:
    listing pages yield only per-meeting detail links (same host, URL
    matching `detail_url` and link text matching `detail_text`, both regexes)
    plus one pagination direction (`paginate`: the rel="next"/"prev" link
    that leads back in time), for at most `max_listing_pages` listing pages.
    Detail pages yield minutes PDFs, deduplicated by file URL; an optional
    `file_text` regex further restricts them by link text (for detail pages
    that bundle other bodies' minutes). Matching the
    listing's link text is what filters mixed plenary/district calendars to
    plenary meetings without fetching the other detail pages."""
    detail_url = re.compile(walk["detail_url"], re.IGNORECASE)
    detail_text = re.compile(walk["detail_text"], re.IGNORECASE)
    file_text = re.compile(walk["file_text"], re.IGNORECASE) if walk.get("file_text") else None
    host = urlparse(base_url).hostname
    records, seen, details = [], set(), {}
    url, listing_pages = base_url, 0
    while url and listing_pages < walk["max_listing_pages"]:
        listing_pages += 1
        soup = _fetch_soup(url)
        if soup is None:
            break
        for link in soup.find_all("a", href=True):
            full = urljoin(url, str(link["href"]))
            if (is_safe_url(full) and urlparse(full).hostname == host
                    and detail_url.search(full)
                    and detail_text.search(link.get_text(" ", strip=True))
                    and full not in details):
                details[full] = link.get_text(" ", strip=True)
        nxt = soup.find("a", rel=walk["paginate"], href=True)
        url = urljoin(url, str(nxt["href"])) if nxt else None
        if url and (not is_safe_url(url) or urlparse(url).hostname != host):
            url = None
    selector = walk.get("html_selector")
    if selector:
        return [{
            "public_body_id": source["public_body_id"],
            "municipal_district": source.get("municipal_district"),
            "minutes_page_url": source["minutes_page_url"],
            "file_url": detail,
            "meeting_date": parse_meeting_date(text, detail),
            "link_text": text,
            "file_kind": "html",
            "text_selector": selector,
        } for detail, text in details.items()]
    for detail in details:
        soup = _fetch_soup(detail)
        if soup is None:
            continue
        for link in soup.find_all("a", href=True):
            full = urljoin(detail, str(link["href"]))
            if is_safe_url(full) and (
                    file_text is None
                    or file_text.search(link.get_text(" ", strip=True))):
                _collect_pdf_link(link, full, source, records, excluded_out,
                                  seen=seen, minutes_token_required=True)
    return records


def collect_minutes_links(source, base_url, excluded_out=None):
    """Collect minutes PDF links from a minutes page, following year-looking
    anchor links one level deep — or, when the source carries a `walk`
    config, walking its paginated listing into per-meeting detail pages
    (see `_collect_walk`). Returns a list of record dicts. Links
    excluded as archival/historical are appended to `excluded_out` (when
    given) as error dicts for the caller to log — never silently dropped."""
    if source.get("walk"):
        return _collect_walk(source, base_url, source["walk"], excluded_out)
    records = []
    visited = set()

    def _walk(url, depth):
        if url in visited:
            return
        visited.add(url)
        soup = _fetch_soup(url)
        if soup is None:
            return
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            full = urljoin(url, href)
            if not is_safe_url(full):
                continue
            if _collect_pdf_link(link, full, source, records, excluded_out):
                continue
            if depth == 0 and _is_year_listing(link.get_text(strip=True), href):
                _walk(full, depth=1)

    _walk(base_url, depth=0)
    return records


def _fetch_one(item):
    url = item["minutes_page_url"]
    try:
        excluded = []
        items = collect_minutes_links(item, url, excluded_out=excluded)
        return item["public_body_id"], url, items, excluded, None
    except Exception as e:
        return item["public_body_id"], url, [], [], e


def pending_sources(writer, items):
    """Source pages not yet collected: an item is pending unless a record
    carrying its `minutes_page_url` is already held by the writer. Keying on
    `minutes_page_url` (one per district/council page) instead of
    `public_body_id` prevents a resumed run from skipping the remaining
    district pages of a body after one page has been collected."""
    processed = {r.get("minutes_page_url") for r in writer.results
                 if r.get("minutes_page_url")}
    return [item for item in items if item.get("minutes_page_url") not in processed]


def process(input_data, step_dir, writer, verbose=False, max_workers=6):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    pending = pending_sources(writer, input_data["results"])

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, item): item for item in pending}
        for future in as_completed(futures):
            body_id, url, items, excluded, exc = future.result()
            if exc is not None:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "context": {"url": url, "public_body_id": body_id},
                })
                writer.append([])
            else:
                for entry in excluded:
                    append_error(step_dir, entry)
                writer.append(items)
            if verbose:
                print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Find meeting minutes PDFs")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

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

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()