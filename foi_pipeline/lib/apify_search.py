import os
import time

import requests

_APIFY_BASE = "https://api.apify.com/v2"
_ACTOR_ID = "apify~google-search-scraper"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
_POLL_INTERVAL = 2.0


def batch_search(queries: list[str], api_token: str | None = None) -> dict[str, list]:
    """Run multiple search queries in one Apify Actor run.

    Returns a dict mapping each query string to its list of organic result dicts.
    Each result dict contains a normalised 'link' key (copied from 'url') for
    compatibility with existing URL-validation code.
    """
    if not queries:
        return {}

    if api_token is None:
        api_token = os.environ.get("APIFY_TOKEN")
    if not api_token:
        raise RuntimeError(
            "APIFY_TOKEN environment variable is not set. "
            "Set it to your Apify API token before running this step."
        )

    run_resp = requests.post(
        f"{_APIFY_BASE}/acts/{_ACTOR_ID}/runs",
        params={"token": api_token},
        json={
            "queries": "\n".join(queries),
            "maxPagesPerQuery": 1,
            "resultsPerPage": 10,
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
            raise RuntimeError(f"Apify Actor run {run_id} ended with status: {status}")
        time.sleep(_POLL_INTERVAL)

    items_resp = requests.get(
        f"{_APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": api_token, "clean": "true"},
        timeout=60,
    )
    items_resp.raise_for_status()
    items = items_resp.json()

    results: dict[str, list] = {q: [] for q in queries}
    for item in items:
        term = item.get("searchQuery", {}).get("term", "")
        if term not in results:
            continue
        organic = item.get("organicResults", [])
        normalised = [{**r, "link": r["url"]} for r in organic if "url" in r]
        results[term].extend(normalised)

    return results
