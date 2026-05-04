import json
import pytest
from steps.find_foi_pages.process import process, STEP_NAME, find_foi_link_on_page

INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "official_website_url": "https://dept-a.ie/", "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 1002, "official_website_url": "https://dept-b.ie/", "is_reachable": False, "http_status": 404, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}

HTML_WITH_FOI_LINK = '<html><body><a href="/freedom-of-information/">Freedom of Information</a></body></html>'
HTML_WITH_FOI_HREF = '<html><body><a href="/foi/">Contact</a></body></html>'
HTML_WITHOUT_FOI = '<html><body><a href="/contact/">Contact us</a></body></html>'


def test_crawl_finds_foi_link_by_text(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_page_url"] == "https://dept-a.ie/freedom-of-information/"
    assert results[0]["source_method"] == "crawl"


def test_crawl_finds_foi_link_by_href(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_HREF)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_page_url"] == "https://dept-a.ie/foi/"
    assert results[0]["source_method"] == "crawl"


def test_unreachable_body_excluded(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    results = process(INPUT, tmp_path)
    assert all(r["public_body_id"] != 1002 for r in results)


def test_serper_fallback_when_crawl_finds_nothing(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    requests_mock.post("https://google.serper.dev/search", json={"organic": [{"link": "https://dept-a.ie/foi/"}]})
    results = process(INPUT, tmp_path)
    assert len(results) == 1
    assert results[0]["source_method"] == "serper"
    assert results[0]["foi_page_url"] == "https://dept-a.ie/foi/"


def test_body_excluded_when_no_foi_link_and_no_serper_key(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    results = process(INPUT, tmp_path)
    assert len(results) == 0


def test_connection_error_logs_and_skips_body(requests_mock, tmp_path):
    import requests as req
    requests_mock.get("https://dept-a.ie/", exc=req.exceptions.ConnectionError("refused"))
    results = process(INPUT, tmp_path)
    assert len(results) == 0
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME


def test_output_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    r = process(INPUT, tmp_path)[0]
    assert {"public_body_id", "official_website_url", "foi_page_url", "source_method"} <= r.keys()


def test_find_foi_link_returns_none_when_no_match():
    html = '<html><body><a href="/about/">About</a></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") is None


def test_find_foi_link_resolves_relative_urls():
    html = '<html><body><a href="/foi/">FOI</a></body></html>'
    result = find_foi_link_on_page(html, "https://example.ie/")
    assert result == "https://example.ie/foi/"
