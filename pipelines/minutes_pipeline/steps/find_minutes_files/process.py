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
    minutes PDFs."""
    tokens = _tokens(link_text, href)
    if tokens & _NOT_MINUTES_TOKENS:
        return False
    if tokens & {"minutes", "meeting", "minute"}:
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


def collect_minutes_links(source, base_url, excluded_out=None):
    """Collect minutes PDF links from a minutes page, following year-looking
    anchor links one level deep. Returns a list of record dicts. Links
    excluded as archival/historical are appended to `excluded_out` (when
    given) as error dicts for the caller to log — never silently dropped."""
    records = []
    visited = set()

    def _walk(url, depth):
        if url in visited:
            return
        visited.add(url)
        response = fetch("GET", url, allow_redirects=True)
        if not _is_html(response):
            return
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            full = urljoin(url, href)
            if not is_safe_url(full):
                continue
            text = link.get_text(strip=True)
            pdf_name = _pdf_name(full)
            if pdf_name:
                # A name recovered from the query string is the only readable
                # signal (the href itself may be base64); a suffix-path link
                # keeps classifying on the raw href/URL as before.
                named_url = full
                if not urlparse(full).path.lower().endswith(_PDF_EXT):
                    href = named_url = pdf_name
                if _looks_like_minutes(text, href):
                    reason = _exclusion_reason(text, named_url)
                    if reason is None or excluded_out is None:
                        # No out-list means no log sink: fail open and keep
                        # the record rather than silently dropping it.
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
            elif depth == 0 and _is_year_listing(text, href):
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