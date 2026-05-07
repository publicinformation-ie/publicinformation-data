import json
import pytest
from steps.check_foi_pages.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "find_foi_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "official_website_url": "https://dept-a.ie/",
         "foi_page_url": "https://dept-a.ie/foi/", "source_method": "crawl"},
        {"public_body_id": 1002, "name": "Dept B", "official_website_url": "https://dept-b.ie/",
         "foi_page_url": "https://dept-b.ie/foi/", "source_method": "serper"},
    ],
}


def test_reachable_page_marked_true(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", status_code=200)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    process(INPUT, tmp_path, writer)
    assert writer.results[0]["is_reachable"] is True
    assert writer.results[0]["http_status"] == 200


def test_non_200_marked_unreachable(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", status_code=404)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    a = next(r for r in writer.results if r["public_body_id"] == 1001) if False else None
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False


def test_all_upstream_fields_carried_forward(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", status_code=200)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    process(INPUT, tmp_path, writer)
    r = writer.results[0]
    assert r["name"] == "Dept A"
    assert r["official_website_url"] == "https://dept-a.ie/"
    assert r["foi_page_url"] == "https://dept-a.ie/foi/"
    assert r["source_method"] == "crawl"


def test_all_bodies_included_regardless_of_status(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", status_code=404)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 2


def test_connection_error_logs_error_and_marks_unreachable(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("refused"))
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False
    assert a["http_status"] is None
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from scripts.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "foi_page_url": "https://dept-a.ie/foi/",
                     "official_website_url": "https://dept-a.ie/",
                     "source_method": "crawl",
                     "is_reachable": True, "http_status": 200, "checked_at": "2026-05-07T00:00:00+00:00"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    requests_mock.get("https://dept-b.ie/foi/", status_code=200)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0
    assert len(writer.results) == 2
