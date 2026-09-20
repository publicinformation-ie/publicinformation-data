"""Apify rerank: score live top-5 search candidates by PDF-yield.

ONLY network-touching approach: needs APIFY_TOKEN and consumes credits.
`fetch_html(url)` is injected so tests pass canned HTML and the experiment
passes a caching live fetcher.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MINUTES_PIPELINE = _HERE.parents[3]
_REPO_ROOT = _MINUTES_PIPELINE.parents[1]
sys.path.insert(0, str(_MINUTES_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_MINUTES_PIPELINE / "steps" / "find_meeting_minutes_pages_search" / "eval"))

from score_page import collect_yield  # noqa: E402


def rerank(candidates, html_by_url):
    """Order candidate URLs by (minutes_like, purity) desc. Pure."""
    scored = []
    for url in candidates:
        html = html_by_url.get(url)
        if not html:
            continue
        y = collect_yield(html, url, None)
        total = y["total"] or 1
        scored.append((y["minutes_like"], y["minutes_like"] / total, url))
    scored.sort(reverse=True)
    return [u for _, _, u in scored]


def predict(search_results, fetch_html):
    """Return (minutes_page_url or None, method). Fetches top-5 live."""
    candidates = [r.get("link") for r in (search_results or [])[:5] if r.get("link")]
    html_by_url = {}
    for url in candidates:
        try:
            html_by_url[url] = fetch_html(url)
        except Exception:
            continue
    ranked = rerank(candidates, html_by_url)
    if ranked:
        return ranked[0], "apify_rerank"
    return None, "miss"
