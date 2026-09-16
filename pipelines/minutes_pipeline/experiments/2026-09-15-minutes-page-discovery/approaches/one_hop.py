"""One-hop: baseline, else follow the best hub link once from cached fixtures."""
import sys
from pathlib import Path
from urllib.parse import urljoin

_HERE = Path(__file__).resolve().parent
_MINUTES_PIPELINE = _HERE.parents[3]
sys.path.insert(0, str(_MINUTES_PIPELINE))

from bs4 import BeautifulSoup  # noqa: E402

from steps.find_meeting_minutes_pages.process import (  # noqa: E402
    _score_link,
    _tokenize,
    find_minutes_link,
)


def predict(home_html, website_url, pages):
    """Return (minutes_page_url or None, method). `pages` maps hub URL -> HTML."""
    match = find_minutes_link(home_html or "", website_url or "")
    if match:
        url, _score = match
        return url, "crawl"
    soup = BeautifulSoup(home_html or "", "html.parser")
    scored = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:
            continue
        sc = _score_link(_tokenize(href, link.get_text(strip=True)))
        if sc > 0:
            scored.append((sc, urljoin(website_url or "", href)))
    scored.sort(reverse=True)
    for _, hub_url in scored:
        hub_html = pages.get(hub_url)
        if not hub_html:
            continue
        hit = find_minutes_link(hub_html, hub_url)
        if hit:
            url, _score = hit
            return url, "one_hop"
    return None, "miss"
