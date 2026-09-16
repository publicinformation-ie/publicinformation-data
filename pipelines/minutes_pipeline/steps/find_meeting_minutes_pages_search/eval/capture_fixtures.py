#!/usr/bin/env python3
"""Cache HTML for the offline minutes-page eval loop.

  - fixtures/home/<key>.html          authority homepage (matcher input)
  - fixtures/pages/<key>.html         predicted minutes page (eval PDF-yield input)
  - fixtures/destinations/<key>.html  year-listing hub target (eval one-hop input)
  - fixtures/hubs/hub_<n>.html          top-3 scoring hub links off each homepage
                                      (one_hop/two_hop experiment inputs)
  - fixtures/hub_index.json           maps hub URL -> hub fixture filename

Run rarely (only to refresh the corpus). Re-running skips already-cached
files, so the iteration loop stays offline and deterministic.

Usage (from minutes_pipeline/):
    uv run python steps/find_meeting_minutes_pages_search/eval/capture_fixtures.py
"""
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

_HERE = Path(__file__).resolve().parent
_MINUTES_PIPELINE = _HERE.parents[2]
_REPO_ROOT = _MINUTES_PIPELINE.parents[1]
sys.path.insert(0, str(_MINUTES_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from lib.http_utils import fetch, is_safe_url  # noqa: E402
from steps.find_meeting_minutes_pages.process import (  # noqa: E402
    _score_link,
    _tokenize,
)

FIXTURES = _HERE / "fixtures"
HOME = FIXTURES / "home"
PAGES = FIXTURES / "pages"
DESTINATIONS = FIXTURES / "destinations"
HUBS = FIXTURES / "hubs"


def fixture_key(public_body_id, municipal_district):
    """Body-level key is str(id); district key appends a URL-slug."""
    if municipal_district:
        slug = re.sub(r"[^a-z0-9]+", "-", str(municipal_district).lower()).strip("-")
        return f"{public_body_id}__{slug}"
    return str(public_body_id)


def _grab(url, dest):
    """Cache one URL. True if newly fetched, None if already cached,
    False on skip/error. Non-HTML responses are stubbed so the scorer can
    read the URL without parsing binary (e.g. a minutes PDF)."""
    if dest.exists():
        return None
    if not url or not is_safe_url(url):
        print(f"    SKIP unsafe {url}")
        return False
    try:
        resp = fetch("GET", url, allow_redirects=True)
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            dest.write_text(f"<!-- non-HTML content ({ctype}) at {url} -->", encoding="utf-8")
        else:
            dest.write_text(resp.text, encoding="utf-8")
        return True
    except Exception as e:
        print(f"    FAIL {url}: {type(e).__name__}: {e}")
        return False


def _top_hub_links(home_html, home_url, limit=3):
    """Top-scoring (score > 0) non-self links off the homepage for hub caching."""
    from urllib.parse import urldefrag
    soup = BeautifulSoup(home_html, "html.parser")
    scored = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/ga/" in href:
            continue
        sc = _score_link(_tokenize(href, link.get_text(strip=True)))
        if sc <= 0:
            continue
        full = urljoin(home_url, href)
        if not is_safe_url(full):
            continue
        if urldefrag(full)[0] == urldefrag(home_url)[0]:
            continue
        scored.append((sc, full))
    scored.sort(reverse=True)
    seen, out = set(), []
    for _, url in scored:
        if url not in seen:
            seen.add(url)
            out.append(url)
        if len(out) == limit:
            break
    return out


def main():
    for d in (HOME, PAGES, DESTINATIONS, HUBS):
        d.mkdir(parents=True, exist_ok=True)
    authorities = {str(a["public_body_id"]): a for a in json.loads(
        (_MINUTES_PIPELINE / "steps" / "find_local_authorities" / "output.json").read_text()
    )["results"]}
    live_path = _HERE.parent / "output.json"
    live = {}
    if live_path.exists():
        for r in json.loads(live_path.read_text())["results"]:
            live[(str(r["public_body_id"]), r.get("municipal_district") or "")] = \
                r.get("minutes_page_url", "")
    hub_index_path = FIXTURES / "hub_index.json"
    hub_index = json.loads(hub_index_path.read_text()) if hub_index_path.exists() else {}
    hub_counter = len(hub_index)
    with open(_HERE / "labels.csv", newline="") as f:
        labels = [r for r in csv.DictReader(f) if r.get("has_log")]
    for row in labels:
        bid, district = row["public_body_id"], row["municipal_district"] or None
        key = fixture_key(bid, district)
        home_url = (authorities.get(bid) or {}).get("official_website_url", "")
        page_url = live.get((bid, district or ""), "")
        _grab(home_url, HOME / f"{key}.html")
        _grab(page_url, PAGES / f"{key}.html")
        home_path = HOME / f"{key}.html"
        home_html = home_path.read_text(encoding="utf-8") if home_path.exists() else ""
        for hub_url in _top_hub_links(home_html, home_url):
            if hub_url not in hub_index:
                fname = f"hub_{hub_counter}.html"
                if _grab(hub_url, HUBS / fname):
                    time.sleep(0.5)
                hub_index[hub_url] = fname
                hub_counter += 1
        print(f"  [{key}] done")
    hub_index_path.write_text(json.dumps(hub_index, indent=2))
    print(f"\nFixture capture complete ({len(hub_index)} hub URLs indexed)")


if __name__ == "__main__":
    main()
