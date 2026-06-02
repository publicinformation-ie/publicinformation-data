import json
import pytest
from steps.get_foi_emails.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "check_foi_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "foi_page_url": "https://dept-a.ie/foi/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 1002, "name": "Dept B", "foi_page_url": "https://dept-b.ie/foi/",
         "is_reachable": False, "http_status": 404, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}

HTML_WITH_FOI_EMAIL = '<html><body><a href="mailto:foi@dept-a.ie">FOI</a></body></html>'
HTML_NO_EMAIL = '<html><body><p>No contact info</p></body></html>'
HTML_MULTIPLE_EMAILS = '<html><body><a href="mailto:info@dept-a.ie">Info</a><a href="mailto:foi@dept-a.ie">FOI</a></body></html>'


def test_finds_foi_email(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_FOI_EMAIL)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["foi_email"] == "foi@dept-a.ie"
    assert a["email_status"] == "found"


def test_unreachable_body_excluded(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_NO_EMAIL)
    process(INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 1002 for r in writer.results)


def test_no_email_produces_not_found_status(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_NO_EMAIL)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["foi_email"] is None
    assert a["email_status"] == "not_found"


def test_picks_foi_keyword_email_over_others(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_MULTIPLE_EMAILS)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["foi_email"] == "foi@dept-a.ie"


def test_connection_error_logs_and_skips(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("x"))
    process(INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 1001 for r in writer.results)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_output_has_required_fields(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=HTML_WITH_FOI_EMAIL)
    process(INPUT, tmp_path, writer)
    r = writer.results[0]
    assert {"public_body_id", "name", "foi_page_url", "foi_email", "email_status"} <= r.keys()


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from scripts.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "foi_page_url": "https://dept-a.ie/foi/",
                     "foi_email": "foi@dept-a.ie", "email_status": "found"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0
    assert len([r for r in writer.results if r["public_body_id"] == 1001]) == 1


import sys as _sys
from scripts.file_utils import read_json as _read_json, write_json as _write_json
import steps.get_foi_emails.process as _proc


def test_public_body_scoped_leaves_others_untouched(requests_mock, tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    seeded = [
        {"public_body_id": 1001, "marker": "keep-1001"},
        {"public_body_id": 1002, "marker": "old-1002"},
        {"public_body_id": 1003, "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "get_foi_emails"}, "results": seeded})

    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "foi_page_url": "https://a.ie/foi/", "is_reachable": True},
        {"public_body_id": 1002, "foi_page_url": "https://b.ie/foi/", "is_reachable": True},
        {"public_body_id": 1003, "foi_page_url": "https://c.ie/foi/", "is_reachable": True},
    ]})
    requests_mock.get("https://b.ie/foi/", text=HTML_WITH_FOI_EMAIL)

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = {r["public_body_id"]: r for r in _read_json(out)["results"]}
    assert results[1001]["marker"] == "keep-1001"
    assert results[1003]["marker"] == "keep-1003"
    assert "marker" not in results[1002] or results[1002]["marker"] != "old-1002"
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]
