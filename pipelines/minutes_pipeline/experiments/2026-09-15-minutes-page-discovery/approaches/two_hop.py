"""Two-hop: BFS to depth 2 over the cached page map; first PDF-yield-positive wins."""
import sys
from pathlib import Path
from urllib.parse import urljoin

_HERE = Path(__file__).resolve().parent
_MINUTES_PIPELINE = _HERE.parents[3]
_REPO_ROOT = _MINUTES_PIPELINE.parents[1]
sys.path.insert(0, str(_MINUTES_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_MINUTES_PIPELINE / "steps" / "find_meeting_minutes_pages_search" / "eval"))

from bs4 import BeautifulSoup  # noqa: E402

from steps.find_meeting_minutes_pages.process import (  # noqa: E402
    _score_link,
    _tokenize,
    find_minutes_link,
)
from score_page import collect_yield  # noqa: E402


def _outlinks(html, base_url):
    soup = BeautifulSoup(html or "", "html.parser")
    links = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:
            continue
        full = urljoin(base_url or "", href)
        sc = _score_link(_tokenize(href, link.get_text(strip=True)))
        links.append((sc, full))
    links.sort(reverse=True)
    return [u for _, u in links]


def predict(home_html, website_url, pages):
    """Return (minutes_page_url or None, method)."""
    match = find_minutes_link(home_html or "", website_url or "")
    if match:
        url, _score = match
        return url, "crawl"
    level1 = [u for u in _outlinks(home_html, website_url) if u in pages]
    for hub_url in level1:
        hub_html = pages[hub_url]
        hit = find_minutes_link(hub_html, hub_url)
        if hit:
            url, _score = hit
            return url, "one_hop"
        for dest_url in _outlinks(hub_html, hub_url):
            dest_html = pages.get(dest_url)
            if not dest_html:
                continue
            y = collect_yield(dest_html, dest_url, None)
            if y["positive"]:
                return dest_url, "two_hop"
    return None, "miss"
