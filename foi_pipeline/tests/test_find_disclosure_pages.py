import json
import pytest
from steps.find_disclosure_pages.process import process, STEP_NAME, find_disclosure_link

INPUT = {
    "metadata": {"step": "get_foi_emails", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "foi_page_url": "https://dept-a.ie/foi/", "foi_email": "foi@dept-a.ie", "email_status": "found"},
        {"public_body_id": 1002, "name": "Dept B", "foi_page_url": "https://dept-b.ie/foi/", "foi_email": None, "email_status": "not_found"},
    ],
}

HTML_WITH_DISCLOSURE_LINK = '<html><body><a href="/foi/disclosure-log/">Disclosure Log</a></body></html>'
HTML_WITH_REQUEST_LINK = '<html><body><a href="/foi/requests/">FOI Requests</a></body></html>'
HTML_WITHOUT_DISCLOSURE = '<html><body><p>FOI information</p></body></html>'


def test_disclosure_link_found_by_text(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    results = process(INPUT, tmp_path)
    a = next(r for r in results if r["public_body_id"] == 1001)
    assert a["disclosure_page_url"] == "https://dept-a.ie/foi/disclosure-log/"


def test_disclosure_link_found_by_request_keyword(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_REQUEST_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITH_REQUEST_LINK)
    results = process(INPUT, tmp_path)
    a = next(r for r in results if r["public_body_id"] == 1001)
    assert a["disclosure_page_url"] == "https://dept-a.ie/foi/requests/"


def test_defaults_to_foi_page_when_no_disclosure_link(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITHOUT_DISCLOSURE)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE)
    results = process(INPUT, tmp_path)
    a = next(r for r in results if r["public_body_id"] == 1001)
    assert a["disclosure_page_url"] == "https://dept-a.ie/foi/"


def test_all_input_bodies_included(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE)
    assert len(process(INPUT, tmp_path)) == 2


def test_connection_error_logs_and_skips(requests_mock, tmp_path):
    import requests as req
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("x"))
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    results = process(INPUT, tmp_path)
    assert len(results) == 1
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_output_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    r = process(INPUT, tmp_path)[0]
    assert {"public_body_id", "foi_page_url", "disclosure_page_url"} <= r.keys()


def test_find_disclosure_link_returns_none_when_no_match():
    html = "<html><body><a href='/about/'>About</a></body></html>"
    assert find_disclosure_link(html, "https://example.ie/") is None


def test_find_disclosure_link_resolves_relative_url():
    html = '<html><body><a href="/disclosure-log/">Disclosure Log</a></body></html>'
    result = find_disclosure_link(html, "https://example.ie/foi/")
    assert result == "https://example.ie/disclosure-log/"
