import os

import pytest
import requests_mock as requests_mock_module

from scripts.http_utils import HEADERS, RATE_LIMIT_DELAY, fetch, search_serper


def test_fetch_success(requests_mock):
    requests_mock.get("https://example.com/page", text="hello world")
    resp = fetch("GET", "https://example.com/page")
    assert resp.status_code == 200
    assert resp.text == "hello world"


def test_fetch_sends_user_agent(requests_mock):
    requests_mock.get("https://example.com/page", text="ok")
    fetch("GET", "https://example.com/page")
    assert requests_mock.last_request.headers["User-Agent"] == HEADERS["User-Agent"]


def test_fetch_merges_extra_headers(requests_mock):
    requests_mock.get("https://example.com/page", text="ok")
    fetch("GET", "https://example.com/page", headers={"X-Custom": "yes"})
    assert requests_mock.last_request.headers["X-Custom"] == "yes"
    assert requests_mock.last_request.headers["User-Agent"] == HEADERS["User-Agent"]


def test_rate_limit_delay_value():
    assert RATE_LIMIT_DELAY == 0.2


def test_search_serper_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    results = search_serper("example.com")
    assert results == []


def test_search_serper_uses_env_key(requests_mock, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key-123")
    requests_mock.post(
        "https://google.serper.dev/search",
        json={"organic": [{"link": "https://example.com/foi", "title": "FOI"}]},
    )
    results = search_serper("example.com")
    assert len(results) == 1
    assert results[0]["link"] == "https://example.com/foi"
    assert requests_mock.last_request.headers["X-API-KEY"] == "test-key-123"


def test_search_serper_explicit_key_overrides_env(requests_mock, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "env-key")
    requests_mock.post(
        "https://google.serper.dev/search",
        json={"organic": []},
    )
    search_serper("example.com", api_key="explicit-key")
    assert requests_mock.last_request.headers["X-API-KEY"] == "explicit-key"


def test_search_serper_returns_empty_on_bad_status(requests_mock, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "key")
    requests_mock.post("https://google.serper.dev/search", status_code=429)
    assert search_serper("example.com") == []
