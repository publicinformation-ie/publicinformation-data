#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from lib.file_utils import append_error, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "fetch_foigovie_bodies"
DIRECTORY_URL = "https://foi.gov.ie/all-foi-bodies/"

# Every body's detail page lives under /foi_units/<slug>/. The directory page
# also links to editorial pages (/about/, /publication-scheme/ etc.), so this
# marker is what separates body links from site chrome.
_DETAIL_SEGMENT = "foi_units"

# foi.gov.ie emits every table row on every detail page and writes a literal
# "n/a" into the cells it has no value for, rather than omitting the row. These
# are treated as "not published" and become null — publishing the string "n/a"
# as a phone number or website would be a silent data-quality defect.
_ABSENT_VALUES = {"", "n/a", "n\\a", "na", "-", "none"}

# Detail-page row label (lowercased, trailing colon stripped) -> output field.
# "Organisation:" is skipped because it duplicates the directory listing's name,
# and "Network:" because sector/category extraction is explicitly out of scope.
_FIELD_LABELS = {
    "address": "foigovie_address",
    "name": "foigovie_officer_name",
    "telephone": "foigovie_phone",
    "email": "foigovie_email",
    "web address": "foigovie_website",
}


def slug_from_url(url: str):
    """Return the <slug> from a /foi_units/<slug>/ detail URL, else None.

    Used verbatim as the natural key for this pipeline — the same role
    datagovie_slug/wdw_slug play in the sibling pipelines.
    """
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 2 or parts[-2] != _DETAIL_SEGMENT:
        return None
    return parts[-1]


def parse_directory(html: str) -> list:
    """Parse the all-foi-bodies listing into one entry per body.

    Deduplicates by slug: the listing is grouped by letter and a body can
    legitimately be linked more than once.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        slug = slug_from_url(anchor["href"])
        name = anchor.get_text(" ", strip=True)
        if not slug or not name or slug in seen:
            continue
        seen.add(slug)
        entries.append({
            "foigovie_slug": slug,
            "foigovie_name": name,
            "foigovie_url": anchor["href"],
        })
    return entries


def _clean(text):
    """Normalise a cell value, mapping foi.gov.ie's absent-value sentinels to None."""
    value = (text or "").strip()
    return None if value.lower() in _ABSENT_VALUES else value


def parse_detail(html: str) -> dict:
    """Extract the FOI-contact fields from a detail page's contact table.

    Rows are <td><strong>Label:</strong></td><td>value</td>. Unrecognised
    labels are ignored. A field whose row is absent, blank, or "n/a" comes
    back as None — these are optional, not confirmed-bad, values, so they
    are nulled rather than raised.
    """
    soup = BeautifulSoup(html, "html.parser")
    fields = {field: None for field in _FIELD_LABELS.values()}
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(" ", strip=True).rstrip(":").strip().lower()
        field = _FIELD_LABELS.get(label)
        if field is None:
            continue
        fields[field] = _clean(cells[1].get_text(" ", strip=True))
    return fields


def fetch_directory() -> list:
    """Fetch and parse the master directory once.

    Fatal-exits on request failure, a non-2xx response, or zero parsed
    bodies — same guard style as fetch_datagovie_orgs. A silently-empty
    directory would otherwise wipe the whole downstream inclusion set.
    """
    try:
        response = fetch("GET", DIRECTORY_URL)
    except Exception as e:
        print(f"Fatal: request to {DIRECTORY_URL} failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not response.ok:
        print(f"Fatal: foi.gov.ie returned HTTP {response.status_code} for {DIRECTORY_URL}",
              file=sys.stderr)
        sys.exit(1)

    entries = parse_directory(response.text)
    if not entries:
        print(f"Fatal: parsed 0 FOI bodies from {DIRECTORY_URL}", file=sys.stderr)
        sys.exit(1)
    return entries


def process(entries, step_dir, writer, verbose=False):
    """Crawl each body's detail page, appending a merged record per body.

    A failing detail page logs an error and is left unprocessed so the next
    run retries it — the crawl is resumable per slug, like get_foi_emails'.
    """
    write_json(Path(step_dir) / "errors.json", [])

    for entry in entries:
        slug = entry["foigovie_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {entry['foigovie_name']} ...", end=" ", flush=True)
        try:
            response = fetch("GET", entry["foigovie_url"])
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status_code}")
            writer.append([{**entry, **parse_detail(response.text)}])
            if verbose:
                print("[ok]", flush=True)
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": entry["foigovie_url"], "foigovie_slug": slug},
            })
            writer.append([])
            if verbose:
                print("[error]", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch foi.gov.ie's FOI-body directory and each body's detail page")
    parser.add_argument("--input", required=True,
                        help="Previous step output (unused — first step in pipeline)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-crawl every body")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    entries = fetch_directory()

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="foigovie_slug",
                               force=args.force)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(entries, step_dir, writer, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(entries)} foi.gov.ie body records to {output_path}")


if __name__ == "__main__":
    main()
