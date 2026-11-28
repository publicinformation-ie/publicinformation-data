"""Discovery of a committee's minutes PDFs from its published page.

Pure, testable functions; ``process.py`` supplies the HTTP fetcher and file
paths. The committed committee list is the only place a committee can be
declared, and every entry's ``public_body_id`` must exist in the
local-authority list.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

STEP_NAME = "find_spc_minutes_files"

# Header layout profiles the parse_meeting_header step defines (kept equal to
# that step's registry by a test). A committee naming any other layout is fatal.
KNOWN_LAYOUTS = frozenset({"meath-table", "kildare-table", "westmeath-list"})

_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
# Markers of bot-protection challenge pages. The pipeline never solves or
# evades them: such a page is a PageFetchFailed error.
_CHALLENGE_MARKERS = (
    "sucuri_cloudproxy", "cf-browser-verification", "cdn-cgi/challenge-platform",
    "just a moment...", "attention required! | cloudflare",
)


class CommitteeConfigError(ValueError):
    """The committed committee list is invalid (fatal)."""


def load_committees(path: Path) -> list[dict]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise CommitteeConfigError(f"{path}: expected a non-empty JSON list")
    return data


def validate_committees(committees: list[dict], body_ids: set[int]) -> None:
    """Raise CommitteeConfigError on a bad entry.

    Checks required fields, unique committee IDs, a derived council/committee
    slug pair, a compiling minutes pattern, and membership in the
    local-authority list (an unknown body is fatal, never skipped).
    """
    seen: set[str] = set()
    for entry in committees:
        for field in ("committee_id", "name", "public_body_id", "minutes_link_pattern", "layout"):
            if field not in entry:
                raise CommitteeConfigError(f"committee entry missing '{field}': {entry!r}")
        if "page_url" not in entry and "page_urls" not in entry:
            raise CommitteeConfigError(f"committee entry missing 'page_url' or 'page_urls': {entry!r}")
        committee_id = entry["committee_id"]
        if "page_url" in entry and "page_urls" in entry:
            raise CommitteeConfigError(
                f"committee {committee_id} declares both page_url and page_urls")
        pages = committee_pages(entry)
        if not pages or not all(isinstance(p, str) and p for p in pages):
            raise CommitteeConfigError(
                f"committee {committee_id} needs one or more non-empty page URLs")
        if len(set(pages)) != len(pages):
            raise CommitteeConfigError(f"committee {committee_id} lists a page URL twice")
        if entry["layout"] not in KNOWN_LAYOUTS:
            raise CommitteeConfigError(
                f"committee {committee_id} names unknown layout {entry['layout']!r}; "
                f"known layouts: {', '.join(sorted(KNOWN_LAYOUTS))}")
        years = entry.get("years")
        if years is not None and (
                not isinstance(years, list) or not years
                or not all(isinstance(y, int) and not isinstance(y, bool) for y in years)):
            raise CommitteeConfigError(
                f"committee {committee_id} years must be a non-empty list of integers")
        if "site_name" in entry and not isinstance(entry["site_name"], str):
            raise CommitteeConfigError(f"committee {committee_id} site_name must be a string")
        if committee_id in seen:
            raise CommitteeConfigError(f"duplicate committee_id: {committee_id}")
        seen.add(committee_id)
        parts = str(committee_id).split("/")
        if len(parts) != 2 or not all(parts):
            raise CommitteeConfigError(
                f"committee_id must be '<council>/<committee>': {committee_id!r}"
            )
        if not isinstance(entry["public_body_id"], int) or isinstance(entry["public_body_id"], bool):
            raise CommitteeConfigError(f"public_body_id must be an integer: {committee_id}")
        if entry["public_body_id"] not in body_ids:
            raise CommitteeConfigError(
                f"committee {committee_id} names public_body_id "
                f"{entry['public_body_id']}, which is not in the local-authority list"
            )
        try:
            re.compile(entry["minutes_link_pattern"])
        except re.error as exc:
            raise CommitteeConfigError(
                f"committee {committee_id} has an invalid minutes_link_pattern: {exc}"
            ) from exc


def committee_pages(committee: dict) -> list[str]:
    """The pages a committee declares: ``page_urls``, or the single ``page_url``."""
    if "page_urls" in committee:
        return list(committee["page_urls"])
    return [committee["page_url"]]


def encode_url(url: str) -> str:
    """Percent-encode spaces and other unsafe path characters exactly once.

    Existing ``%XX`` escapes are kept as they are, so an already-encoded URL
    is unchanged and a raw space becomes ``%20`` (never ``%2520``).
    """
    parts = urlparse(url)
    path = quote(parts.path, safe="/%:@!$&'()*+,;=~-._")
    return urlunparse(parts._replace(path=path))


def is_bot_challenge(html: str) -> bool:
    """True when the page is a bot-protection challenge, not the real page."""
    lowered = html.lower()
    return any(marker in lowered for marker in _CHALLENGE_MARKERS)


def extract_pdf_links(html: str, page_url: str) -> list[dict]:
    """Every PDF link on the page, as ``{url, link_text}``, in page order."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[dict] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or not urlparse(href).path.lower().endswith(".pdf"):
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        links.append({"url": encode_url(urljoin(page_url, href)), "link_text": text})
    return links


def is_minutes_link(link: dict, pattern: str) -> bool:
    """True when the link text (or, failing that, the file name) says minutes."""
    regex = re.compile(pattern)
    if regex.search(link["link_text"] or ""):
        return True
    file_name = urlparse(link["url"]).path.rsplit("/", 1)[-1]
    return bool(regex.search(file_name))


def link_year(link_text: str) -> int | None:
    """The single four-digit year in the link text, else None.

    Two different years in one link text are ambiguous and give None too: the
    year is never inferred from the file name or URL.
    """
    years = {int(match) for match in _YEAR.findall(link_text or "")}
    return years.pop() if len(years) == 1 else None


def discover_page(committee: dict, html: str, page_url: str | None = None,
                  seen: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """One page's minutes records and errors, in page order.

    ``seen`` carries the URLs already collected from the committee's other
    pages so a file linked twice is collected once. When the committee declares
    ``years``, only links whose text gives one of those years are collected; a
    minutes link whose text gives no (single) year is an ``UndatedMinutesLink``
    error and no record.
    """
    page_url = page_url or committee_pages(committee)[0]
    seen = seen if seen is not None else set()
    years = committee.get("years")
    pattern = committee["minutes_link_pattern"]
    records: list[dict] = []
    errors: list[dict] = []
    for link in extract_pdf_links(html, page_url):
        if not is_minutes_link(link, pattern):
            continue
        if link["url"] in seen:
            continue
        if years is not None:
            year = link_year(link["link_text"])
            if year is None:
                errors.append(error(
                    STEP_NAME, "UndatedMinutesLink",
                    f"{link['url']}: the link text {link['link_text']!r} gives no single "
                    f"year, so it cannot be checked against years {years}",
                    committee_id=committee["committee_id"],
                    public_body_id=committee["public_body_id"],
                    page_url=page_url, file_url=link["url"],
                ))
                continue
            if year not in years:
                continue
        seen.add(link["url"])
        records.append({
            "committee_id": committee["committee_id"],
            "committee_name": committee["name"],
            "public_body_id": committee["public_body_id"],
            "page_url": page_url,
            "layout": committee["layout"],
            "file_url": link["url"],
            "link_text": link["link_text"],
        })
    return records, errors


def error(step, error_type: str, message: str, **context) -> dict:
    return {
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": context,
    }
