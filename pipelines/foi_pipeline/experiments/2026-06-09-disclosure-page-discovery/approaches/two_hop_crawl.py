"""Approach C1: two-hop crawl fallback.

When find_disclosure_link (Approach A scoring) finds nothing on the FOI page,
identify up to 2 FOI-section links and fetch each, re-running find_disclosure_link
on the result. Returns (url, score, method) or None.
"""
import importlib.util as _ilu
import sys
from pathlib import Path
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[3]))

from lib.http_utils import fetch, is_safe_url


def _load_scoring_fix():
    _here = Path(__file__).parent
    spec = _ilu.spec_from_file_location("scoring_fix", _here / "scoring_fix.py")
    assert spec is not None and spec.loader is not None
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_sf = _load_scoring_fix()
_tokenize = _sf._tokenize
find_disclosure_link = _sf.find_disclosure_link
ACCEPT_THRESHOLD = _sf.ACCEPT_THRESHOLD

_DISCLOSURE_TOKENS = {"disclosure", "disclosures", "log", "logs", "decisions", "decision"}


def _is_foi_section_link(tokens: set) -> bool:
    """True when the link looks like an FOI section nav page (not a disclosure log)."""
    has_foi = "foi" in tokens or ("freedom" in tokens and "information" in tokens)
    has_disclosure = bool(tokens & _DISCLOSURE_TOKENS)
    return has_foi and not has_disclosure


def _section_score(tokens: set) -> int:
    """Rank section candidates. Higher = follow first."""
    if not _is_foi_section_link(tokens):
        return 0
    score = 0
    if "foi" in tokens:
        score += 3
    if "freedom" in tokens:
        score += 1
    if "information" in tokens:
        score += 1
    return score


def _default_fetcher(url: str) -> str:
    return fetch("GET", url, allow_redirects=True).text


def find_disclosure_link_two_hop(html: str, base_url: str, fetcher=None):
    """Return (url, score, method) or None.

    method is 'crawl' if found on the first page, 'crawl_2hop' if found on a
    section page. Returns None if neither hop produces a match.
    """
    # First pass — Approach A scoring on the FOI page
    match = find_disclosure_link(html, base_url)
    if match:
        return match[0], match[1], "crawl"

    # Identify FOI section link candidates
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str]] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:
            continue
        tokens = _tokenize(href, link.get_text(strip=True))
        sc = _section_score(tokens)
        if sc == 0:
            continue
        full_url = urljoin(base_url, href)
        norm = urldefrag(full_url)[0]
        if not is_safe_url(full_url):
            continue
        if norm == urldefrag(base_url)[0]:
            continue
        if norm in seen_urls:
            continue
        seen_urls.add(norm)
        candidates.append((sc, full_url))

    candidates.sort(key=lambda x: -x[0])
    candidates = candidates[:2]

    if not candidates:
        return None

    _fetcher = fetcher if fetcher is not None else _default_fetcher

    for _, section_url in candidates:
        try:
            section_html = _fetcher(section_url)
            match = find_disclosure_link(section_html, section_url)
            if match:
                return match[0], match[1], "crawl_2hop"
        except Exception:
            continue

    return None
