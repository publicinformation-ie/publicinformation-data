import json
import pytest
from steps.validate_websites.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "resolve_website_urls", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "official_website_url": "https://dept-a.ie/", "status": {}},
        {"public_body_id": 1002, "name": "Dept B", "official_website_url": "https://dept-b.ie/", "status": {}},
    ],
}


def test_reachable_body_marked_true(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", status_code=200)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path, writer)
    assert writer.results[0]["is_reachable"] is True
    assert writer.results[0]["http_status"] == 200


def test_non_200_body_marked_unreachable(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", status_code=404)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    a = next(r for r in writer.results if r["public_body_id"] == 1001) if False else None
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False
    assert a["http_status"] == 404


def test_connection_error_logs_error_and_marks_unreachable(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", exc=req.exceptions.ConnectionError("refused"))
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False
    assert a["http_status"] is None
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME


def test_all_bodies_included_regardless_of_status(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", status_code=500)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 2


def test_output_has_required_fields(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", status_code=200)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path, writer)
    for r in writer.results:
        assert {"public_body_id", "name", "official_website_url", "is_reachable", "http_status", "checked_at"} <= r.keys()


def test_errors_json_reset_on_each_run(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    (tmp_path / "errors.json").write_text('[{"step": "old"}]')
    requests_mock.get("https://dept-a.ie/", exc=req.exceptions.ConnectionError("x"))
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from lib.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "official_website_url": "https://dept-a.ie/", "status": {},
                     "is_reachable": True, "http_status": 200,
                     "checked_at": "2026-05-07T00:00:00+00:00"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0
    assert len(writer.results) == 2


import sys as _sys
from lib.file_utils import read_json as _read_json, write_json as _write_json
import steps.validate_websites.process as _proc


def test_public_body_scoped_leaves_others_untouched(requests_mock, tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    seeded = [
        {"public_body_id": 1001, "marker": "keep-1001"},
        {"public_body_id": 1002, "marker": "old-1002"},
        {"public_body_id": 1003, "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "validate_websites"}, "results": seeded})

    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "official_website_url": "https://a.ie/", "status": {}},
        {"public_body_id": 1002, "official_website_url": "https://b.ie/", "status": {}},
        {"public_body_id": 1003, "official_website_url": "https://c.ie/", "status": {}},
    ]})
    requests_mock.get("https://b.ie/", status_code=200)

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = {r["public_body_id"]: r for r in _read_json(out)["results"]}
    assert results[1001]["marker"] == "keep-1001"
    assert results[1003]["marker"] == "keep-1003"
    assert "marker" not in results[1002] or results[1002]["marker"] != "old-1002"
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]
