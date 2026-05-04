import json
import pytest
from steps.get_foi_emails.process import process, STEP_NAME, extract_emails, pick_foi_email

INPUT = {
    "metadata": {"step": "check_foi_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {
            "public_body_id": 1001,
            "name": "Dept A",
            "official_website_url": "https://dept-a.ie/",
            "foi_page_url": "https://dept-a.ie/foi/",
            "source_method": "crawl",
            "is_reachable": True,
            "http_status": 200,
            "checked_at": "2026-05-04T00:00:00+00:00",
        },
        {
            "public_body_id": 1002,
            "name": "Dept B",
            "official_website_url": "https://dept-b.ie/",
            "foi_page_url": "https://dept-b.ie/foi/",
            "source_method": "crawl",
            "is_reachable": False,
            "http_status": 404,
            "checked_at": "2026-05-04T00:00:00+00:00",
        },
    ],
}

HTML_ONE_MAILTO = '<html><body><a href="mailto:foi@dept-a.ie">Email FOI</a></body></html>'
HTML_ONE_TEXT_EMAIL = '<html><body><p>Contact: foi@dept-a.ie for requests</p></body></html>'
HTML_TWO_EMAILS_FOI = '<html><body><a href="mailto:info@dept-a.ie">Info</a><a href="mailto:foi@dept-a.ie">FOI</a></body></html>'
HTML_TWO_EMAILS_NO_FOI = '<html><body><a href="mailto:info@dept-a.ie">Info</a><a href="mailto:press@dept-a.ie">Press</a></body></html>'
HTML_NO_EMAIL = '<html><body><p>No email here</p></body></html>'


def test_unreachable_page_excluded(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_ONE_MAILTO)
    results = process(INPUT, tmp_path)
    assert all(r["public_body_id"] != 1002 for r in results)


def test_single_mailto_link_found(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_ONE_MAILTO)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_email"] == "foi@dept-a.ie"
    assert results[0]["email_status"] == "found"


def test_email_in_page_text_found(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_ONE_TEXT_EMAIL)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_email"] == "foi@dept-a.ie"
    assert results[0]["email_status"] == "found"


def test_multiple_emails_foi_keyword_wins(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_TWO_EMAILS_FOI)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_email"] == "foi@dept-a.ie"
    assert results[0]["email_status"] == "found"


def test_multiple_emails_no_foi_keyword(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_TWO_EMAILS_NO_FOI)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_email"] is None
    assert results[0]["email_status"] == "multiple_found"


def test_no_email_found(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_NO_EMAIL)
    results = process(INPUT, tmp_path)
    assert results[0]["foi_email"] is None
    assert results[0]["email_status"] == "not_found"


def test_reachable_body_always_in_output(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_NO_EMAIL)
    assert len(process(INPUT, tmp_path)) == 1


def test_connection_error_logs_and_skips(requests_mock, tmp_path):
    import requests as req
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("x"))
    results = process(INPUT, tmp_path)
    assert len(results) == 0
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_output_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_ONE_MAILTO)
    r = process(INPUT, tmp_path)[0]
    assert {"public_body_id", "name", "foi_page_url", "foi_email", "email_status"} <= r.keys()


def test_extract_emails_finds_mailto():
    emails = extract_emails('<a href="mailto:test@example.ie">Email</a>')
    assert "test@example.ie" in emails


def test_extract_emails_finds_text_email():
    emails = extract_emails("<p>Contact test@example.ie</p>")
    assert "test@example.ie" in emails


def test_pick_foi_email_empty_returns_not_found():
    email, status = pick_foi_email([])
    assert email is None
    assert status == "not_found"
