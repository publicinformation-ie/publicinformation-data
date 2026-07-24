#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url
from steps.find_disclosure_pages.process import _tokenize
from steps.get_foi_emails.process import extract_emails, pick_foi_email

STEP_NAME = "find_foi_email_pages"

# Non-HTML content types a foi_page_url/candidate link can resolve to. Skipped
# before parsing — BeautifulSoup/html.parser can throw confusing low-level
# errors if handed binary bytes.
_BINARY_CONTENT_TYPES = ("application/pdf", "application/octet-stream", "image/")

_DOC_EXTS = (".pdf", ".docx", ".xlsx", ".xls", ".odt", ".doc")

MAX_CANDIDATES = 3

# Same rationale as find_disclosure_pages.NEGATIVE_TOKENS: token match (not
# substring) so 'log' doesn't fire on 'login'/'blog', and known
# false-positive-prone link types are excluded outright.
NEGATIVE_TOKENS = {
    "login", "logo", "blog", "annual", "report", "reports",
    "publication", "scheme", "form", "how", "make", "apply",
    "guide", "guidance",
}

_FOI = {"foi", "freedom"}
_CONTACT = {"contact", "contacts"}
_OFFICER_UNIT_TEAM = {"officer", "unit", "team"}
_STAFF_DIRECTORY = {"staff", "directory"}

FOI_EMAIL_KEYWORDS = ("foi", "freedom")


def _score_link(tokens):
    """Score a candidate link's combined href+anchor tokens. Higher = more
    confidently a contact/FOI-officer page. 0 = reject."""
    if tokens & NEGATIVE_TOKENS:
        return 0
    foi = bool(tokens & _FOI)
    contact = bool(tokens & _CONTACT)
    officer = bool(tokens & _OFFICER_UNIT_TEAM)
    staff = bool(tokens & _STAFF_DIRECTORY)

    if foi and (contact or officer):
        return 100
    if contact and officer:
        return 80
    if contact:
        return 50
    if officer or staff:
        return 40
    return 0


def find_candidate_links(html, base_url):
    """Return up to MAX_CANDIDATES (url, score) pairs for the highest-scoring
    contact/FOI-officer links on the page, highest score first."""
    soup = BeautifulSoup(html, "html.parser")
    scored = []
    seen_urls = set()
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if href.lower().split("?")[0].endswith(_DOC_EXTS):
            continue
        tokens = _tokenize(href, link.get_text(strip=True))
        sc = _score_link(tokens)
        if sc <= 0:
            continue
        full_url = urljoin(base_url, href)
        if not is_safe_url(full_url):
            continue
        if urldefrag(full_url)[0] == urldefrag(base_url)[0]:
            continue  # same-page anchor only
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        scored.append((full_url, sc))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:MAX_CANDIDATES]


def _confidence(link_score, email):
    """high: winning link scored on foi/freedom tokens (100) AND the email
    itself contains foi/freedom. medium: same link tier, generic email.
    none: link only matched generic contact/officer tokens (40-80)."""
    if link_score < 100:
        return "none"
    email_is_foi = any(kw in (email or "").lower() for kw in FOI_EMAIL_KEYWORDS)
    return "high" if email_is_foi else "medium"
