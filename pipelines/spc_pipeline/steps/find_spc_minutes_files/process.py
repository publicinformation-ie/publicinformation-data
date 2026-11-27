#!/usr/bin/env python3
"""Discover each committed committee's minutes PDFs from its page.

Input: the local-authority list (cross-pipeline reference), used only to
validate that every committee's ``public_body_id`` is a real local authority.
Output: one record per minutes PDF, de-duplicated by URL.

Agenda PDFs and every other link are ignored. A committee may declare several
pages (``page_urls``) and a year window (``years``). A page that cannot be
fetched (including a bot-protection challenge, which is never bypassed), or a
committee list that does not validate, is fatal (fail closed).
"""
import argparse
import sys
from pathlib import Path

import requests

from lib.certs import requests_verify
from lib.cli_utils import add_common_args
from lib.file_utils import append_error, read_json, write_json, write_status

from steps.find_spc_minutes_files.discovery import (
    STEP_NAME,
    CommitteeConfigError,
    committee_pages,
    discover_page,
    error,
    is_bot_challenge,
    load_committees,
    validate_committees,
)

_BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_html(url: str) -> str:
    """Fetch a page with certificate verification on (plus our intermediates)."""
    response = requests.get(url, headers=_BROWSER_HEADERS,
                            verify=requests_verify(), timeout=60)
    response.raise_for_status()
    return response.text


def run(input_data, committees_path: Path, step_dir: Path, fetcher=fetch_html,
        public_body=None) -> tuple[list[dict], list[dict]]:
    """Return ``(records, errors)``; never writes files (test entry point)."""
    body_ids = {
        body.get("public_body_id")
        for body in input_data.get("results") or input_data.get("public_bodies") or []
    }
    committees = load_committees(committees_path)
    if public_body is not None:
        committees = [c for c in committees if c.get("public_body_id") == public_body]

    try:
        validate_committees(committees, body_ids)
    except CommitteeConfigError as exc:
        return [], [error(STEP_NAME, "CommitteeConfigError", str(exc))]

    records: list[dict] = []
    errors: list[dict] = []
    for committee in committees:
        found: list[dict] = []
        seen: set[str] = set()
        for page_url in committee_pages(committee):
            context = dict(committee_id=committee["committee_id"],
                           public_body_id=committee["public_body_id"], page_url=page_url)
            try:
                html = fetcher(page_url)
            except Exception as exc:  # network, TLS, HTTP status (including a 403 block)
                errors.append(error(
                    STEP_NAME, "PageFetchFailed",
                    f"could not fetch {page_url}: {exc}", **context))
                continue
            if is_bot_challenge(html):
                errors.append(error(
                    STEP_NAME, "PageFetchFailed",
                    f"{page_url} returned a bot-protection challenge; the pipeline "
                    "does not solve or bypass challenges", **context))
                continue
            page_records, page_errors = discover_page(committee, html, page_url, seen)
            found.extend(page_records)
            errors.extend(page_errors)
        if not found and not any(
                e["context"].get("committee_id") == committee["committee_id"] for e in errors):
            errors.append(error(
                STEP_NAME, "NoMinutesFound",
                f"no minutes links matched on {', '.join(committee_pages(committee))}",
                committee_id=committee["committee_id"],
                public_body_id=committee["public_body_id"],
            ))
        records.extend(found)
    return records, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    errors_path = step_dir / "errors.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(errors_path, [])

    input_data = read_json(args.input)
    records, errors = run(input_data, step_dir / "committees.json", step_dir,
                          public_body=args.public_body)
    for entry in errors:
        append_error(step_dir, entry)

    write_json(output_path, {
        "metadata": {"step": STEP_NAME},
        "results": records,
    })
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} minutes file(s) to {output_path}; {len(errors)} error(s)")
    if errors:
        for entry in errors:
            print(f"Fatal: {entry['error_type']}: {entry['error_message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
