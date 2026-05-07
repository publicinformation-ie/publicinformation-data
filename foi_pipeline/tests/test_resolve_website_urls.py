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
        {"public_body_id": 1001, "name": "Health Service Executive",
         "official_website_url": "https://www.gov.ie/en/organisation/hse/",
         "status": {"website_url": {"url": "https://www.gov.ie/en/organisation/hse/", "status": "not_attempted"}}},
        {"public_body_id": 1002, "name": "Dept of Finance",
         "official_website_url": "https://www.gov.ie/en/organisation/finance/",
         "status": {"website_url": {"url": "https://www.gov.ie/en/organisation/finance/", "status": "not_attempted"}}},
    ],
}


def test_stub_page_resolves_to_external_url(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=STUB_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    hse = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://hse.ie/"


def test_non_stub_page_keeps_original_url(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=DEPT_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    hse = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://www.gov.ie/en/organisation/hse/"


def test_all_bodies_produce_one_result_each(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=DEPT_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 2


def test_connection_error_logs_and_keeps_original_body(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/",
                      exc=requests.exceptions.ConnectionError("x"))
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    hse = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://www.gov.ie/en/organisation/hse/"
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_output_key_is_results(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=DEPT_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    from scripts.file_utils import read_json
    data = read_json(tmp_path / "output.json")
    assert "results" in data
    assert "public_bodies" not in data


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from scripts.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Health Service Executive",
                     "official_website_url": "https://hse.ie/",
                     "status": {}}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    hse_calls = [r for r in requests_mock.request_history if "hse" in r.url]
    assert len(hse_calls) == 0
