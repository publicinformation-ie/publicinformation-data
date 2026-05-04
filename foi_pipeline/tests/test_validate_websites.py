import json
import pytest
from steps.validate_websites.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "find_public_bodies", "completed_at": "2026-05-04T00:00:00+00:00"},
    "public_bodies": [
        {"public_body_id": 1001, "name": "Dept A", "official_website_url": "https://dept-a.ie/", "status": {}},
        {"public_body_id": 1002, "name": "Dept B", "official_website_url": "https://dept-b.ie/", "status": {}},
    ],
}


def test_reachable_body_marked_true(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", status_code=200)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    results = process(INPUT, tmp_path)
    assert results[0]["is_reachable"] is True
    assert results[0]["http_status"] == 200


def test_non_200_body_marked_unreachable(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", status_code=404)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    a = next(r for r in process(INPUT, tmp_path) if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False
    assert a["http_status"] == 404


def test_connection_error_logs_error_and_marks_unreachable(requests_mock, tmp_path):
    import requests as req
    requests_mock.get("https://dept-a.ie/", exc=req.exceptions.ConnectionError("refused"))
    requests_mock.get("https://dept-b.ie/", status_code=200)
    results = process(INPUT, tmp_path)
    a = next(r for r in results if r["public_body_id"] == 1001)
    assert a["is_reachable"] is False
    assert a["http_status"] is None
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME


def test_all_bodies_included_regardless_of_status(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", status_code=500)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    assert len(process(INPUT, tmp_path)) == 2


def test_output_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/", status_code=200)
    requests_mock.get("https://dept-b.ie/", status_code=200)
    for r in process(INPUT, tmp_path):
        assert {"public_body_id", "official_website_url", "is_reachable", "http_status", "checked_at"} <= r.keys()


def test_errors_json_reset_on_each_run(requests_mock, tmp_path):
    import requests as req
    (tmp_path / "errors.json").write_text('[{"step": "old"}]')
    requests_mock.get("https://dept-a.ie/", exc=req.exceptions.ConnectionError("x"))
    requests_mock.get("https://dept-b.ie/", status_code=200)
    process(INPUT, tmp_path)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1  # old error replaced, not appended
