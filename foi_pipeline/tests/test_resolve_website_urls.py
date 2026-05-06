# foi_pipeline/tests/test_resolve_website_urls.py
import json
import pytest
import requests
from steps.resolve_website_urls.process import process, STEP_NAME

STUB_HTML = """<html><body>
<p>There is a separate website for
<a href="https://hse.ie/">the Health Service Executive</a>.</p>
</body></html>"""

DEPT_HTML = "<html><body><h1>Department of Finance</h1></body></html>"

INPUT = {
    "metadata": {"step": "find_public_bodies", "completed_at": "2026-05-04T00:00:00+00:00"},
    "public_bodies": [
        {
            "public_body_id": 1001,
            "name": "Health Service Executive",
            "official_website_url": "https://www.gov.ie/en/organisation/hse/",
            "status": {"website_url": {"url": "https://www.gov.ie/en/organisation/hse/", "status": "not_attempted"}},
        },
        {
            "public_body_id": 1002,
            "name": "Dept of Finance",
            "official_website_url": "https://www.gov.ie/en/organisation/finance/",
            "status": {"website_url": {"url": "https://www.gov.ie/en/organisation/finance/", "status": "not_attempted"}},
        },
    ],
}


def test_stub_url_replaced_with_external_url(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=STUB_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    results = process(INPUT, tmp_path)
    hse = next(r for r in results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://hse.ie/"


def test_non_stub_url_unchanged(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=STUB_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    results = process(INPUT, tmp_path)
    finance = next(r for r in results if r["public_body_id"] == 1002)
    assert finance["official_website_url"] == "https://www.gov.ie/en/organisation/finance/"


def test_all_other_fields_preserved(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=STUB_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    results = process(INPUT, tmp_path)
    hse = next(r for r in results if r["public_body_id"] == 1001)
    assert hse["name"] == "Health Service Executive"
    assert hse["status"] == INPUT["public_bodies"][0]["status"]


def test_fetch_error_logs_error_and_passes_body_through(requests_mock, tmp_path):
    requests_mock.get(
        "https://www.gov.ie/en/organisation/hse/",
        exc=requests.exceptions.ConnectionError("refused"),
    )
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    results = process(INPUT, tmp_path)
    hse = next(r for r in results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://www.gov.ie/en/organisation/hse/"
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME
    assert errors[0]["context"]["public_body_id"] == 1001


def test_process_returns_all_bodies_including_errored(requests_mock, tmp_path):
    requests_mock.get(
        "https://www.gov.ie/en/organisation/hse/",
        exc=requests.exceptions.ConnectionError("refused"),
    )
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    results = process(INPUT, tmp_path)
    assert len(results) == 2


def test_output_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=STUB_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    results = process(INPUT, tmp_path)
    for body in results:
        assert {"public_body_id", "name", "official_website_url", "status"} <= body.keys()
