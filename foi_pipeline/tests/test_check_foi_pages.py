import json
import pytest
from steps.check_foi_pages.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "find_foi_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {
            "public_body_id": 1001,
            "official_website_url": "https://dept-a.ie/",
            "foi_page_url": "https://dept-a.ie/foi/",
            "source_method": "crawl",
        },
        {
            "public_body_id": 1002,
            "official_website_url": "https://dept-b.ie/",
            "foi_page_url": "https://dept-b.ie/foi/",
            "source_method": "serper",
        },
    ],
}


def test_reachable_page_marked_true(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", status_code=200)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    results = process(INPUT, tmp_path)
    assert results[0]["is_reachable"] is True
    assert results[0]["http_status"] == 200


def test_non_200_marked_unreachable(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", status_code=404)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    a = next(r for r in process(INPUT, tmp_path) if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False


def test_all_upstream_fields_carried_forward(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", status_code=200)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    r = process(INPUT, tmp_path)[0]
    assert r["official_website_url"] == "https://dept-a.ie/"
    assert r["foi_page_url"] == "https://dept-a.ie/foi/"
    assert r["source_method"] == "crawl"


def test_all_bodies_included_regardless_of_status(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/foi/", status_code=404)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    assert len(process(INPUT, tmp_path)) == 2


def test_connection_error_logs_error_and_marks_unreachable(requests_mock, tmp_path):
    import requests as req
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("refused"))
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    results = process(INPUT, tmp_path)
    a = next(r for r in results if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False
    assert a["http_status"] is None
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME
