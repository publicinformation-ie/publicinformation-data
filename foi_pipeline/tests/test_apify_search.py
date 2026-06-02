import pytest
import requests_mock as requests_mock_module
from scripts.apify_search import batch_search

APIFY_BASE = "https://api.apify.com/v2"
TOKEN = "test-token-abc"

RUN_RESPONSE = {
    "data": {
        "id": "run123",
        "defaultDatasetId": "ds456",
        "status": "RUNNING",
    }
}
SUCCEEDED_RESPONSE = {
    "data": {"id": "run123", "status": "SUCCEEDED"}
}
DATASET_ITEMS = [
    {
        "searchQuery": {"term": "site:example.com foi"},
        "organicResults": [{"url": "https://example.com/foi/", "title": "FOI"}],
    },
    {
        "searchQuery": {"term": "site:other.ie freedom of information"},
        "organicResults": [],
    },
]


def test_batch_search_returns_results_keyed_by_query(requests_mock):
    requests_mock.post(
        f"{APIFY_BASE}/acts/apify~google-search-scraper/runs",
        json=RUN_RESPONSE,
    )
    requests_mock.get(
        f"{APIFY_BASE}/actor-runs/run123",
        json=SUCCEEDED_RESPONSE,
    )
    requests_mock.get(
        f"{APIFY_BASE}/datasets/ds456/items",
        json=DATASET_ITEMS,
    )
    result = batch_search(
        ["site:example.com foi", "site:other.ie freedom of information"],
        api_token=TOKEN,
    )
    assert result["site:example.com foi"] == [{"url": "https://example.com/foi/", "title": "FOI", "link": "https://example.com/foi/"}]
    assert result["site:other.ie freedom of information"] == []


def test_batch_search_polls_until_succeeded(requests_mock):
    requests_mock.post(
        f"{APIFY_BASE}/acts/apify~google-search-scraper/runs",
        json=RUN_RESPONSE,
    )
    requests_mock.get(
        f"{APIFY_BASE}/actor-runs/run123",
        [
            {"json": {"data": {"id": "run123", "status": "RUNNING"}}},
            {"json": SUCCEEDED_RESPONSE},
        ],
    )
    requests_mock.get(f"{APIFY_BASE}/datasets/ds456/items", json=[])
    batch_search(["site:example.com foi"], api_token=TOKEN)
    poll_calls = [r for r in requests_mock.request_history if "/actor-runs/" in r.url]
    assert len(poll_calls) == 2


def test_batch_search_raises_on_failed_run(requests_mock):
    requests_mock.post(
        f"{APIFY_BASE}/acts/apify~google-search-scraper/runs",
        json=RUN_RESPONSE,
    )
    requests_mock.get(
        f"{APIFY_BASE}/actor-runs/run123",
        json={"data": {"id": "run123", "status": "FAILED"}},
    )
    with pytest.raises(RuntimeError, match="FAILED"):
        batch_search(["site:example.com foi"], api_token=TOKEN)


def test_batch_search_raises_without_token(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        batch_search(["site:example.com foi"])


def test_batch_search_reads_token_from_env(requests_mock, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    requests_mock.post(
        f"{APIFY_BASE}/acts/apify~google-search-scraper/runs",
        json=RUN_RESPONSE,
    )
    requests_mock.get(f"{APIFY_BASE}/actor-runs/run123", json=SUCCEEDED_RESPONSE)
    requests_mock.get(f"{APIFY_BASE}/datasets/ds456/items", json=[])
    batch_search(["site:example.com foi"])
    assert TOKEN in requests_mock.request_history[0].url


def test_batch_search_sends_all_queries_in_one_run(requests_mock):
    requests_mock.post(
        f"{APIFY_BASE}/acts/apify~google-search-scraper/runs",
        json=RUN_RESPONSE,
    )
    requests_mock.get(f"{APIFY_BASE}/actor-runs/run123", json=SUCCEEDED_RESPONSE)
    requests_mock.get(f"{APIFY_BASE}/datasets/ds456/items", json=[])
    batch_search(
        ["site:a.ie foi", "site:b.ie foi", "site:c.ie foi"],
        api_token=TOKEN,
    )
    run_calls = [r for r in requests_mock.request_history if "/acts/" in r.url]
    assert len(run_calls) == 1
    body = run_calls[0].json()
    assert "site:a.ie foi" in body["queries"]
    assert "site:b.ie foi" in body["queries"]
    assert "site:c.ie foi" in body["queries"]


def test_batch_search_missing_query_returns_empty_list(requests_mock):
    requests_mock.post(
        f"{APIFY_BASE}/acts/apify~google-search-scraper/runs",
        json=RUN_RESPONSE,
    )
    requests_mock.get(f"{APIFY_BASE}/actor-runs/run123", json=SUCCEEDED_RESPONSE)
    requests_mock.get(f"{APIFY_BASE}/datasets/ds456/items", json=[])
    result = batch_search(["site:example.com foi"], api_token=TOKEN)
    assert result["site:example.com foi"] == []


def test_batch_search_returns_empty_dict_for_empty_queries(requests_mock):
    result = batch_search([], api_token=TOKEN)
    assert result == {}
    assert len(requests_mock.request_history) == 0
