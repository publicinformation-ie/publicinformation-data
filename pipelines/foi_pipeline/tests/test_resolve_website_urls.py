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
    from lib.file_utils import read_json
    data = read_json(tmp_path / "output.json")
    assert "results" in data
    assert "public_bodies" not in data


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from lib.file_utils import write_json, IncrementalWriter
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



def test_http_redirect_uses_final_url(monkeypatch, tmp_path, make_writer):
    """When response.url differs from the original (HTTP redirect), the final URL is used."""
    from unittest.mock import MagicMock
    import steps.resolve_website_urls.process as proc

    writer = make_writer(STEP_NAME)

    def fake_fetch(method, url, **kwargs):
        resp = MagicMock()
        resp.url = "https://hse.ie/"   # final URL after redirect
        resp.text = DEPT_HTML          # no stub marker on landing page
        return resp

    monkeypatch.setattr(proc, "fetch", fake_fetch)
    process(INPUT, tmp_path, writer)
    hse = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://hse.ie/"


def test_http_error_status_is_logged_and_body_kept(requests_mock, tmp_path, make_writer):
    """A 404 or 500 response should be treated as a failure, logged, and original URL kept."""
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", status_code=404)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    hse = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert hse["official_website_url"] == "https://www.gov.ie/en/organisation/hse/"
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert any(e["public_body_id"] == 1001 for e in [e["context"] for e in errors])


def test_failed_ids_written_for_retry(requests_mock, tmp_path, make_writer):
    """Bodies that fail (network error or HTTP error) should appear in failed_ids.json."""
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", status_code=500)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/",
                      exc=requests.exceptions.ConnectionError("x"))
    process(INPUT, tmp_path, writer)
    failed = json.loads((tmp_path / "failed_ids.json").read_text())
    assert 1001 in failed
    assert 1002 in failed


def test_successful_bodies_not_in_failed_ids(requests_mock, tmp_path, make_writer):
    """Successfully fetched bodies must not appear in failed_ids.json."""
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/organisation/hse/", text=DEPT_HTML)
    requests_mock.get("https://www.gov.ie/en/organisation/finance/", text=DEPT_HTML)
    process(INPUT, tmp_path, writer)
    failed = json.loads((tmp_path / "failed_ids.json").read_text())
    assert failed == []


import sys as _sys
from lib.file_utils import read_json as _read_json, write_json as _write_json
import steps.resolve_website_urls.process as _proc


def test_public_body_scoped_leaves_others_untouched(requests_mock, tmp_path, monkeypatch):
    # Seed this step's existing output with three bodies.
    out = tmp_path / "output.json"
    seeded = [
        {"public_body_id": 1001, "marker": "keep-1001"},
        {"public_body_id": 1002, "marker": "old-1002"},
        {"public_body_id": 1003, "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "resolve_website_urls"}, "results": seeded})

    # Input contains all three; only 1002 will pass through the filter.
    inp = tmp_path / "input.json"
    _write_json(inp, {"public_bodies": [
        {"public_body_id": 1001, "name": "A",
         "official_website_url": "https://example.com/1001/",
         "status": {"website_url": {"url": "https://example.com/1001/", "status": "not_attempted"}}},
        {"public_body_id": 1002, "name": "B",
         "official_website_url": "https://example.com/1002/",
         "status": {"website_url": {"url": "https://example.com/1002/", "status": "not_attempted"}}},
        {"public_body_id": 1003, "name": "C",
         "official_website_url": "https://example.com/1003/",
         "status": {"website_url": {"url": "https://example.com/1003/", "status": "not_attempted"}}},
    ]})

    # Mock only 1002's URL (filter means 1001/1003 are never fetched)
    requests_mock.get("https://example.com/1002/", text=DEPT_HTML)

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = {r["public_body_id"]: r for r in _read_json(out)["results"]}
    assert results[1001]["marker"] == "keep-1001"   # untouched
    assert results[1003]["marker"] == "keep-1003"   # untouched
    assert "marker" not in results[1002] or results[1002]["marker"] != "old-1002"  # reprocessed
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]
