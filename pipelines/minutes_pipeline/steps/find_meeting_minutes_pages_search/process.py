#!/usr/bin/env python3
from urllib.parse import urlparse

from steps.find_meeting_minutes_pages.process import (
    ACCEPT_THRESHOLD,
    _score_link,
    _tokenize,
)

from lib.http_utils import is_safe_url, validate_url_or_raise

STEP_NAME = "find_meeting_minutes_pages_search"


def _build_query(website_url: str, name: str) -> str:
    domain = urlparse(website_url).netloc
    return f"site:{domain} {name} council meeting minutes"


def _pick_minutes_url(results: list) -> str | None:
    """Best Apify result URL per the crawl step's tiered scorer.

    Tokenises each candidate's URL + search-result title with the same
    vocabulary/weights as find_meeting_minutes_pages.find_minutes_link
    (single source of truth via import). Accepts only scores >=
    ACCEPT_THRESHOLD; skips /ga/ and unsafe URLs like the crawl does.
    No gov.ie path-prefix rule: every council has its own domain, and the
    site: query already constrains results to it.
    """
    best = None
    best_score = 0
    for r in results:
        link = r.get("link", "")
        if not link:
            continue
        if "/ga/" in urlparse(link).path:
            continue
        try:
            validate_url_or_raise(link, context="apify_result")
        except ValueError:
            continue
        if not is_safe_url(link):
            continue
        score = _score_link(_tokenize(link, r.get("title", "")))
        if score > best_score:
            best, best_score = link, score
    if best is not None and best_score >= ACCEPT_THRESHOLD:
        return best
    return None
