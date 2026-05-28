import json
import pytest
from steps.find_disclosure_pages.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "find_foi_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "foi_page_url": "https://dept-a.ie/foi/", "source_method": "crawl"},
        {"public_body_id": 1002, "name": "Dept B", "foi_page_url": "https://dept-b.ie/foi/", "source_method": "crawl"},
    ],
}

HTML_WITH_DISCLOSURE_LINK = '<html><body><a href="/foi/disclosure/">Disclosure Log</a></body></html>'
HTML_WITHOUT_DISCLOSURE_LINK = '<html><body><p>FOI info only</p></body></html>'


def test_finds_disclosure_link(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["disclosure_page_url"] == "https://dept-a.ie/foi/disclosure/"


def test_falls_back_to_foi_url_when_no_disclosure_link(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["disclosure_page_url"] == "https://dept-a.ie/foi/"


def test_output_has_required_fields(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    r = writer.results[0]
    assert {"public_body_id", "name", "foi_page_url", "disclosure_page_url"} <= r.keys()


def test_all_bodies_produce_one_result_each(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 2


def test_connection_error_logs_and_skips(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("x"))
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 1001 for r in writer.results)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from scripts.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "foi_page_url": "https://dept-a.ie/foi/",
                     "disclosure_page_url": "https://dept-a.ie/foi/disclosure/"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0


DISCLOSURE_URL = (
    "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/"
    "collections/freedom-of-information-disclosure-logs/"
)

INPUT_GOV_IE = {
    "metadata": {"step": "find_foi_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {
            "public_body_id": 2001,
            "name": "Department of Agriculture, Food and the Marine",
            "foi_page_url": "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
            "source_method": "crawl",
        }
    ],
}


def test_gov_ie_uses_domain_handler_not_crawl(requests_mock, tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: [{"link": DISCLOSURE_URL}],
    )
    writer = make_writer(STEP_NAME)
    process(INPUT_GOV_IE, tmp_path, writer)
    result = next(r for r in writer.results if r["public_body_id"] == 2001)
    assert result["disclosure_page_url"] == DISCLOSURE_URL
    gov_ie_crawl_calls = [r for r in requests_mock.request_history if "gov.ie" in r.url]
    assert gov_ie_crawl_calls == [], "gov.ie FOI page must not be crawled when domain handler returns a result"


def test_skips_irish_language_disclosure_links(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    html = '<html><body><a href="/ga/disclosure-log/">Nochtadh</a></body></html>'
    requests_mock.get("https://dept-a.ie/foi/", text=html)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["disclosure_page_url"] == "https://dept-a.ie/foi/"


def test_gov_ie_falls_back_to_crawl_when_domain_handler_returns_none(requests_mock, tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: [],
    )
    requests_mock.get(
        "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
        text='<html><body><a href="/collections/foi-disclosure-log/">Disclosure Log</a></body></html>',
    )
    writer = make_writer(STEP_NAME)
    process(INPUT_GOV_IE, tmp_path, writer)
    result = next(r for r in writer.results if r["public_body_id"] == 2001)
    assert "collections/foi-disclosure-log" in result["disclosure_page_url"]


def test_records_confidence_and_source_method(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    html = '<html><body><a href="/foi/foi-disclosure-log/">FOI Disclosure Log</a></body></html>'
    requests_mock.get("https://dept-a.ie/foi/", text=html)
    requests_mock.get("https://dept-b.ie/foi/", text=HTML_WITHOUT_DISCLOSURE_LINK)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    b = next(r for r in writer.results if r["public_body_id"] == 1002)
    assert a["confidence"] == "high"
    assert a["source_method"] == "crawl"
    assert b["confidence"] == "none"
    assert b["source_method"] == "foi_page_fallback"
    assert b["disclosure_page_url"] == "https://dept-b.ie/foi/"
