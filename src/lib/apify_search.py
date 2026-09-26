import os
import time

import requests

from lib.response_cache import ResponseCache

_APIFY_BASE = "https://api.apify.com/v2"
_ACTOR_ID = "apify~google-search-scraper"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
_POLL_INTERVAL = 2.0

ACTOR_INPUT = {"maxPagesPerQuery": 1, "resultsPerPage": 10}
# apify/google-search-scraper pay-per-event prices, FREE tier, verified 2026-09-26.
PRICE_PER_PAGE_USD = 0.0045
PRICE_PER_START_USD = 0.001
DEFAULT_RESERVE_USD = float(os.environ.get("APIFY_RESERVE_USD", "0.50"))


class ApifyBudgetExceeded(RuntimeError):
    """Raised before an Actor run whose estimated cost exceeds the remaining monthly budget."""


def _token(api_token):
    token = api_token or os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError(
            "APIFY_TOKEN environment variable is not set. "
            "Set it to your Apify API token before running this step."
        )
    return token


def batch_search_raw(queries: list[str], api_token: str | None = None) -> dict[str, dict | None]:
    """Run queries in one Actor run; return the complete dataset item per query (None if absent)."""
    if not queries:
        return {}
    api_token = _token(api_token)
    run_resp = requests.post(
        f"{_APIFY_BASE}/acts/{_ACTOR_ID}/runs",
        params={"token": api_token},
        json={"queries": "\n".join(queries), **ACTOR_INPUT},
        timeout=30,
    )
    run_resp.raise_for_status()
    run_data = run_resp.json()["data"]
    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]

    while True:
        status_resp = requests.get(f"{_APIFY_BASE}/actor-runs/{run_id}",
                                   params={"token": api_token}, timeout=30)
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in _TERMINAL_STATUSES:
            raise RuntimeError(f"Apify Actor run {run_id} ended with status: {status}")
        time.sleep(_POLL_INTERVAL)

    items_resp = requests.get(f"{_APIFY_BASE}/datasets/{dataset_id}/items",
                              params={"token": api_token, "clean": "true"}, timeout=60)
    items_resp.raise_for_status()
    results: dict[str, dict | None] = {q: None for q in queries}
    for item in items_resp.json():
        term = item.get("searchQuery", {}).get("term", "")
        if term in results and results[term] is None:
            results[term] = item
    return results


def batch_search(queries: list[str], api_token: str | None = None) -> dict[str, list]:
    """Run multiple search queries in one Apify Actor run.

    Returns a dict mapping each query string to its list of organic result dicts.
    Each result dict contains a normalised 'link' key (copied from 'url') for
    compatibility with existing URL-validation code.
    """
    raw = batch_search_raw(queries, api_token)
    return {
        q: [{**r, "link": r["url"]} for r in (item or {}).get("organicResults", []) if "url" in r]
        for q, item in raw.items()
    }


def estimate_cost_usd(n_queries: int) -> float:
    if n_queries <= 0:
        return 0.0
    return n_queries * PRICE_PER_PAGE_USD + PRICE_PER_START_USD


def remaining_budget_usd(api_token: str | None = None) -> float:
    """Live remaining usage this billing cycle, from GET /v2/users/me/limits."""
    resp = requests.get(f"{_APIFY_BASE}/users/me/limits",
                        headers={"Authorization": f"Bearer {_token(api_token)}"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()["data"]
    return float(data["limits"]["maxMonthlyUsageUsd"]) - float(data["current"]["monthlyUsageUsd"])


def _cache_key(query: str) -> str:
    return ResponseCache.key("apify", _ACTOR_ID, ACTOR_INPUT, " ".join(query.split()).lower())


def cached_search(queries, cache: ResponseCache, *, refresh: bool = False, reserve_usd=None,
                  raw_fn=None, budget_fn=None) -> tuple[dict, int]:
    """Search with a permanent raw-item cache. Returns (items_by_query, n_paid_queries).

    Only cache misses are sent to Apify. Raises ApifyBudgetExceeded before any call
    if the estimated cost of the misses exceeds live remaining budget minus reserve.
    """
    raw_fn = raw_fn or batch_search_raw
    budget_fn = budget_fn or remaining_budget_usd
    reserve = DEFAULT_RESERVE_USD if reserve_usd is None else reserve_usd

    items, misses = {}, []
    for q in dict.fromkeys(queries):
        hit = None if refresh else cache.get(_cache_key(q))
        if hit is None:
            misses.append(q)
        else:
            items[q] = hit["item"]

    if misses:
        estimate = estimate_cost_usd(len(misses))
        remaining = budget_fn()
        if estimate > remaining - reserve:
            raise ApifyBudgetExceeded(
                f"{len(misses)} queries ≈ ${estimate:.3f} exceeds remaining ${remaining:.3f} "
                f"minus reserve ${reserve:.2f}")
        raw = raw_fn(misses)
        for q in misses:
            item = raw.get(q)
            cache.put(_cache_key(q), {"query": q, "actor": _ACTOR_ID,
                                      "actor_input": ACTOR_INPUT, "item": item})
            items[q] = item
    return items, len(misses)
