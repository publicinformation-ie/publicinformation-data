import json
import pytest
from steps.find_foi_pages.process import process, STEP_NAME, find_foi_link_on_page

INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "official_website_url": "https://dept-a.ie/", "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 1002, "name": "Dept B", "official_website_url": "https://dept-b.ie/", "is_reachable": False, "http_status": 404, "checked_at": "2026-05-04T00:00:00+00:00"},
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
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)  # Valid-length API key
    requests_mock.post("https://google.serper.dev/search", json={"organic": [{"link": "https://dept-a.ie/foi/"}]})
    results = process(INPUT, tmp_path)
    assert len(results) == 1
    assert results[0]["source_method"] == "serper"
    assert results[0]["foi_page_url"] == "https://dept-a.ie/foi/"
    # Verify Serper query includes department name
    assert "Dept A" in requests_mock.last_request.json()["q"]


def test_body_excluded_when_no_foi_link_and_no_serper_key(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    results = process(INPUT, tmp_path)
    assert len(results) == 0
    # Verify that an error was logged for the missing API key
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert "SERPER_API_KEY not set" in errors[0]["error_message"]


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
    assert {"public_body_id", "name", "official_website_url", "foi_page_url", "source_method"} <= r.keys()


def test_find_foi_link_returns_none_when_no_match():
    html = '<html><body><a href="/about/">About</a></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") is None


def test_find_foi_link_resolves_relative_urls():
    html = '<html><body><a href="/foi/">FOI</a></body></html>'
    result = find_foi_link_on_page(html, "https://example.ie/")
    assert result == "https://example.ie/foi/"


def test_mailto_link_not_returned_by_crawl(requests_mock, tmp_path):
    html = '<html><body><a href="mailto:foi@dept-a.ie">Email FOI</a></body></html>'
    requests_mock.get("https://dept-a.ie/", text=html)
    results = process(INPUT, tmp_path)
    assert len(results) == 0


def test_mailto_not_matched_by_find_foi_link_on_page():
    html = '<html><body><a href="mailto:foi@body.ie">FOI Contact</a></body></html>'
    assert find_foi_link_on_page(html, "https://body.ie/") is None


# Additional INPUT fixture for gov.ie bodies
GOV_IE_INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {
            "public_body_id": 2001,
            "name": "Courts Service",
            "official_website_url": "https://www.gov.ie/en/courts-service/",
            "is_reachable": True,
            "http_status": 200,
            "checked_at": "2026-05-04T00:00:00+00:00",
        },
    ],
}


def test_serper_gov_ie_filters_to_path_prefix(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://www.gov.ie/en/courts-service/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)  # Valid-length API key
    # Serper returns a cross-body result first, then the correct one
    requests_mock.post(
        "https://google.serper.dev/search",
        json={
            "organic": [
                {"link": "https://www.gov.ie/en/social-welfare-appeals/foi/"},  # wrong body
                {"link": "https://www.gov.ie/en/courts-service/foi/"},           # correct
            ]
        },
    )
    results = process(GOV_IE_INPUT, tmp_path)
    assert len(results) == 1
    assert results[0]["foi_page_url"] == "https://www.gov.ie/en/courts-service/foi/"


def test_serper_non_gov_ie_not_filtered(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)  # Valid-length API key
    requests_mock.post(
        "https://google.serper.dev/search",
        json={"organic": [{"link": "https://dept-a.ie/foi/"}]},
    )
    results = process(INPUT, tmp_path)
    assert len(results) == 1
    assert results[0]["foi_page_url"] == "https://dept-a.ie/foi/"


def test_serper_gov_ie_no_matching_prefix_returns_nothing(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://www.gov.ie/en/courts-service/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)  # Valid-length API key
    requests_mock.post(
        "https://google.serper.dev/search",
        json={"organic": [{"link": "https://www.gov.ie/en/social-welfare-appeals/foi/"}]},
    )
    results = process(GOV_IE_INPUT, tmp_path)
    assert len(results) == 0


# Input with two bodies that will both resolve to the same (blocked) URL
BLOCKLIST_INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 3001, "name": "Agency A", "official_website_url": "https://agency-a.ie/", "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 3002, "name": "Agency B", "official_website_url": "https://agency-b.ie/", "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}

BLOCKED_URL_HTML = '<html><body><a href="https://www.gov.ie/en/topics/freedom-of-information">FOI</a></body></html>'
BLOCKED_URL_TRAILING_SLASH_HTML = '<html><body><a href="https://www.gov.ie/en/topics/freedom-of-information/">FOI</a></body></html>'
DUPLICATE_FOI_HTML = '<html><body><a href="https://shared-foi.ie/foi/">FOI</a></body></html>'


def test_blocklisted_url_excluded_from_crawl_results(requests_mock, tmp_path):
    requests_mock.get("https://agency-a.ie/", text=BLOCKED_URL_HTML)
    requests_mock.get("https://agency-b.ie/", text=HTML_WITH_FOI_LINK)
    results = process(BLOCKLIST_INPUT, tmp_path)
    assert all(r["public_body_id"] != 3001 for r in results)
    assert any(r["public_body_id"] == 3002 for r in results)


def test_blocklisted_url_with_trailing_slash_excluded(requests_mock, tmp_path):
    requests_mock.get("https://agency-a.ie/", text=BLOCKED_URL_TRAILING_SLASH_HTML)
    requests_mock.get("https://agency-b.ie/", text=HTML_WITH_FOI_LINK)
    results = process(BLOCKLIST_INPUT, tmp_path)
    assert all(r["public_body_id"] != 3001 for r in results)


def test_duplicate_foi_urls_removed_from_output(requests_mock, tmp_path):
    # Both bodies resolve to the same foi page URL
    requests_mock.get("https://agency-a.ie/", text=DUPLICATE_FOI_HTML)
    requests_mock.get("https://agency-b.ie/", text=DUPLICATE_FOI_HTML)
    results = process(BLOCKLIST_INPUT, tmp_path)
    assert len(results) == 0


def test_duplicate_foi_urls_logged_to_errors(requests_mock, tmp_path):
    requests_mock.get("https://agency-a.ie/", text=DUPLICATE_FOI_HTML)
    requests_mock.get("https://agency-b.ie/", text=DUPLICATE_FOI_HTML)
    process(BLOCKLIST_INPUT, tmp_path)
    errors = json.loads((tmp_path / "errors.json").read_text())
    duplicate_errors = [e for e in errors if e.get("error_type") == "DuplicateFoiPageUrl"]
    assert len(duplicate_errors) == 2
    assert {e["context"]["public_body_id"] for e in duplicate_errors} == {3001, 3002}


def test_non_duplicate_urls_not_affected_by_uniqueness_pass(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    results = process(INPUT, tmp_path)
    assert len(results) == 1
    assert results[0]["foi_page_url"] == "https://dept-a.ie/freedom-of-information/"
