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
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

STEP_NAME = "find_spc_minutes_files"


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
        for field in ("committee_id", "name", "public_body_id", "page_url", "minutes_link_pattern"):
            if field not in entry:
                raise CommitteeConfigError(f"committee entry missing '{field}': {entry!r}")
        committee_id = entry["committee_id"]
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


def extract_pdf_links(html: str, page_url: str) -> list[dict]:
    """Every PDF link on the page, as ``{url, link_text}``, in page order."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[dict] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or not urlparse(href).path.lower().endswith(".pdf"):
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        links.append({"url": urljoin(page_url, href), "link_text": text})
    return links


def is_minutes_link(link: dict, pattern: str) -> bool:
    """True when the link text (or, failing that, the file name) says minutes."""
    regex = re.compile(pattern)
    if regex.search(link["link_text"] or ""):
        return True
    file_name = urlparse(link["url"]).path.rsplit("/", 1)[-1]
    return bool(regex.search(file_name))


def discover_committee(committee: dict, html: str) -> list[dict]:
    """The committee's minutes records, de-duplicated by URL, in page order."""
    records: list[dict] = []
    seen: set[str] = set()
    pattern = committee["minutes_link_pattern"]
    for link in extract_pdf_links(html, committee["page_url"]):
        if not is_minutes_link(link, pattern):
            continue
        if link["url"] in seen:
            continue
        seen.add(link["url"])
        records.append({
            "committee_id": committee["committee_id"],
            "committee_name": committee["name"],
            "public_body_id": committee["public_body_id"],
            "page_url": committee["page_url"],
            "file_url": link["url"],
            "link_text": link["link_text"],
        })
    return records


def error(step, error_type: str, message: str, **context) -> dict:
    return {
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": context,
    }
