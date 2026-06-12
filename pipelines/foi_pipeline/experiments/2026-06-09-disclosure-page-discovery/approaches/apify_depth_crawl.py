"""Approach C2: Apify cheerio-scraper depth-2 crawl.

Starts from the FOI page URL, crawls up to maxCrawlDepth=2, scores every
discovered URL with Approach A scoring. Returns the best-scoring URL above
ACCEPT_THRESHOLD, or None.

Requires APIFY_TOKEN env var. Costs Apify credits per call.
"""
import importlib.util as _ilu
import os
import sys
import time
from pathlib import Path

import requests

_here = Path(__file__).parent
sys.path.insert(0, str(_here.parents[2]))


def _load_scoring_fix():
    spec = _ilu.spec_from_file_location("scoring_fix", _here / "scoring_fix.py")
    assert spec is not None and spec.loader is not None
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_sf = _load_scoring_fix()
_tokenize = _sf._tokenize
_score_link = _sf._score_link
ACCEPT_THRESHOLD = _sf.ACCEPT_THRESHOLD

_APIFY_BASE = "https://api.apify.com/v2"
_ACTOR_ID = "apify~cheerio-scraper"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
_POLL_INTERVAL = 3.0


def run_apify_depth_crawl(
    foi_url: str,
    api_token: str | None = None,
    max_pages: int = 50,
) -> tuple[str, int] | None:
    """Return (best_url, score) or None.

    Fires an Apify cheerio-scraper run from foi_url with maxCrawlDepth=2,
    then scores each discovered page URL.
    """
    if api_token is None:
        api_token = os.environ.get("APIFY_TOKEN")
    if not api_token:
        raise RuntimeError(
            "APIFY_TOKEN environment variable is not set. "
            "Set it before running Approach C2."
        )

    run_resp = requests.post(
        f"{_APIFY_BASE}/acts/{_ACTOR_ID}/runs",
        params={"token": api_token},
        json={
            "startUrls": [{"url": foi_url}],
            "maxCrawlDepth": 2,
            "maxPagesPerCrawl": max_pages,
            "pageFunction": (
                "async function pageFunction(context) { "
                "return { url: context.request.url }; "
                "}"
            ),
        },
        timeout=30,
    )
    run_resp.raise_for_status()
    run_data = run_resp.json()["data"]
    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]

    while True:
        status_resp = requests.get(
            f"{_APIFY_BASE}/actor-runs/{run_id}",
            params={"token": api_token},
            timeout=30,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in _TERMINAL_STATUSES:
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
        time.sleep(_POLL_INTERVAL)

    items_resp = requests.get(
        f"{_APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": api_token, "clean": "true"},
        timeout=60,
    )
    items_resp.raise_for_status()
    items = items_resp.json()

    best_url = None
    best_score = 0
    for item in items:
        url = item.get("url", "")
        if not url:
            continue
        tokens = _tokenize(url)
        sc = _score_link(tokens)
        if sc > best_score and sc >= ACCEPT_THRESHOLD:
            best_score = sc
            best_url = url

    return (best_url, best_score) if best_url else None
