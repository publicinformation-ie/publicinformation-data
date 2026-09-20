"""Baseline: current homepage crawl logic unmodified."""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MINUTES_PIPELINE = _HERE.parents[3]
sys.path.insert(0, str(_MINUTES_PIPELINE))

from steps.find_meeting_minutes_pages.process import find_minutes_link  # noqa: E402


def predict(home_html, website_url, pages):
    """Return (minutes_page_url or None, method)."""
    match = find_minutes_link(home_html or "", website_url or "")
    if match:
        url, _score = match
        return url, "crawl"
    return None, "miss"
