import os

import pytest
import requests_mock as requests_mock_module

from scripts.http_utils import HEADERS, DEFAULT_RATE_LIMIT_DELAY, fetch, search_serper


def test_fetch_success(requests_mock):
    requests_mock.get("https://www.gov.ie/page", text="hello world")
    resp = fetch("GET", "https://www.gov.ie/page")
    assert resp.status_code == 200
    assert resp.text == "hello world"


def test_fetch_sends_user_agent(requests_mock):
    requests_mock.get("https://www.gov.ie/page", text="ok")
    fetch("GET", "https://www.gov.ie/page")
    assert requests_mock.last_request.headers["User-Agent"] == HEADERS["User-Agent"]


def test_fetch_merges_extra_headers(requests_mock):
    requests_mock.get("https://www.gov.ie/page", text="ok")
    fetch("GET", "https://www.gov.ie/page", headers={"X-Custom": "yes"})
    assert requests_mock.last_request.headers["X-Custom"] == "yes"
    assert requests_mock.last_request.headers["User-Agent"] == HEADERS["User-Agent"]


def test_rate_limit_delay_value():
    assert DEFAULT_RATE_LIMIT_DELAY == 0.2


def test_search_serper_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    results = search_serper("site:example.com")
    assert results == []


def test_search_serper_uses_env_key(requests_mock, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key-123")
    requests_mock.post(
        "https://google.serper.dev/search",
        json={"organic": [{"link": "https://example.com/foi", "title": "FOI"}]},
    )
    results = search_serper("site:example.com")
    assert len(results) == 1
    assert results[0]["link"] == "https://example.com/foi"
    assert requests_mock.last_request.headers["X-API-KEY"] == "test-key-123"


def test_search_serper_explicit_key_overrides_env(requests_mock, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "env-key")
    requests_mock.post(
        "https://google.serper.dev/search",
        json={"organic": []},
    )
    search_serper("site:example.com", api_key="explicit-key")
    assert requests_mock.last_request.headers["X-API-KEY"] == "explicit-key"


def test_search_serper_returns_empty_on_bad_status(requests_mock, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "key")
    requests_mock.post("https://google.serper.dev/search", status_code=429)
    assert search_serper("site:example.com") == []


def test_fetch_sleeps_between_requests(requests_mock, monkeypatch):
    import time
    import scripts.http_utils as hu
    from scripts.http_utils import DEFAULT_RATE_LIMIT_DELAY
    # Save original value
    original_delay = hu.DEFAULT_RATE_LIMIT_DELAY
    monkeypatch.setattr(hu, "DEFAULT_RATE_LIMIT_DELAY", 0.05)
    # Also need to reset the domain tracking
    hu._domain_last_request.clear()
    hu._domain_request_count.clear()
    
    calls = []
    real_sleep = time.sleep
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))
    requests_mock.get("https://www.gov.ie/", status_code=200)
    hu.fetch("GET", "https://www.gov.ie/")
    assert calls == [0.05]
    
    # Restore original value
    monkeypatch.setattr(hu, "DEFAULT_RATE_LIMIT_DELAY", original_delay)
