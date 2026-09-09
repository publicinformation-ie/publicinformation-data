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
_YEAR_LINK_RE = re.compile(r"^(19|20)\d{2}$")


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
    """Filter agendas/reports out where distinguishable; keep minutes PDFs."""
    tokens = set(re.split(r"[^a-z0-9]+", f"{link_text} {href}".lower()))
    if tokens & {"agenda", "agendas", "report", "reports", "scheme",
                 "annual", "published", "minutes-of-agenda"}:
        return False
    if tokens & {"minutes", "meeting", "minute"}:
        return True
    return False


def collect_minutes_links(source, base_url):
    """Collect minutes PDF links from a minutes page, following year-looking
    anchor links one level deep. Returns a list of record dicts."""
    records = []

    def _walk(url, depth):
        response = fetch("GET", url, allow_redirects=True)
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            full = urljoin(url, href)
            if not is_safe_url(full):
                continue
            text = link.get_text(strip=True)
            path = urlparse(full).path.lower()
            if path.endswith(_PDF_EXT):
                if _looks_like_minutes(text, href):
                    records.append({
                        "public_body_id": source["public_body_id"],
                        "municipal_district": source.get("municipal_district"),
                        "minutes_page_url": source["minutes_page_url"],
                        "file_url": full,
                        "meeting_date": parse_meeting_date(text, full),
                        "link_text": text,
                    })
            elif depth == 0 and _YEAR_LINK_RE.match(text.strip()):
                _walk(full, depth=1)

    _walk(base_url, depth=0)
    return records


def _fetch_one(item):
    url = item["minutes_page_url"]
    try:
        items = collect_minutes_links(item, url)
        return item["public_body_id"], url, items, None
    except Exception as e:
        return item["public_body_id"], url, [], e


def process(input_data, step_dir, writer, verbose=False, max_workers=6):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["public_body_id"])]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, item): item for item in pending}
        for future in as_completed(futures):
            body_id, url, items, exc = future.result()
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