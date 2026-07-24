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


def _is_binary_response(response):
    content_type = response.headers.get("Content-Type", "").lower()
    return any(ct in content_type for ct in _BINARY_CONTENT_TYPES)


def _try_candidate(candidate_url):
    """Fetch a candidate page and return (email, found) or (None, False) on
    any failure/non-HTML/no-email outcome. Never raises."""
    try:
        response = fetch("GET", candidate_url, allow_redirects=True)
    except Exception:
        return None, False
    if _is_binary_response(response):
        return None, False
    emails = extract_emails(response.text)
    email, email_status = pick_foi_email(emails)
    return email, email_status == "found"


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    items = input_data["results"]

    for item in items:
        body_id = item["public_body_id"]
        if writer.is_processed(body_id):
            continue

        if item.get("email_status") != "not_found":
            writer.append([item])
            if verbose:
                print(".", end="", flush=True)
            continue

        url = item["foi_page_url"]
        name = item.get("name", "")
        if verbose:
            print(f"  {name} ({url}) ...", end=" ", flush=True)
        try:
            response = fetch("GET", url, allow_redirects=True)
            if _is_binary_response(response):
                writer.append([item])
                if verbose:
                    print("[binary foi page]", flush=True)
                continue

            candidates = find_candidate_links(response.text, url)
            upgraded = None
            for candidate_url, link_score in candidates:
                email, found = _try_candidate(candidate_url)
                if found:
                    upgraded = {
                        **item,
                        "foi_email": email,
                        "email_status": "found",
                        "confidence": _confidence(link_score, email),
                        "source_page_url": candidate_url,
                    }
                    break

            writer.append([upgraded if upgraded is not None else item])
            if verbose:
                print(f"[{'upgraded' if upgraded else 'no match'}]", flush=True)
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
                print("[error]", flush=True)
