import json
import pytest
from steps.find_disclosure_files.process import process, STEP_NAME, find_file_links

INPUT = {
    "metadata": {"step": "find_disclosure_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "foi_page_url": "https://dept-a.ie/foi/", "disclosure_page_url": "https://dept-a.ie/foi/disclosure/"},
        {"public_body_id": 1002, "name": "Dept B", "foi_page_url": "https://dept-b.ie/foi/", "disclosure_page_url": "https://dept-b.ie/foi/disclosure/"},
    ],
}

HTML_WITH_PDF = '<html><body><a href="/disclosures/q1-2024.pdf">Q1 2024</a></body></html>'
HTML_WITH_XLSX = '<html><body><a href="/disclosures/log.xlsx">Log</a></body></html>'
HTML_WITH_XLS = '<html><body><a href="/disclosures/log.xls">Log</a></body></html>'
HTML_WITH_MULTIPLE = """
<html><body>
  <a href="/disclosures/q1.pdf">Q1</a>
  <a href="/disclosures/q2.pdf">Q2</a>
  <a href="/disclosures/q3.xlsx">Q3</a>
</body></html>
"""
HTML_WITH_YEAR_PAGE = '<html><body><a href="/disclosures/2024/">2024</a></body></html>'
HTML_YEAR_PAGE_CONTENT = '<html><body><a href="/disclosures/2024/q1.pdf">Q1 2024</a></body></html>'
HTML_NO_FILES = '<html><body><p>No files here</p></body></html>'


def test_finds_pdf_link(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_WITH_PDF)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert writer.results[0]["file_url"] == "https://dept-a.ie/disclosures/q1-2024.pdf"
    assert writer.results[0]["file_type"] == "pdf"


def test_finds_xlsx_link(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_WITH_XLSX)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    assert writer.results[0]["file_type"] == "xlsx"


def test_finds_xls_link(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_WITH_XLS)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    assert writer.results[0]["file_type"] == "xls"


def test_multiple_files_produce_multiple_records(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_WITH_MULTIPLE)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    results = [r for r in writer.results if r["public_body_id"] == 1001]
    assert len(results) == 3


def test_follows_year_page_one_level_deep(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_WITH_YEAR_PAGE)
    requests_mock.get("https://dept-a.ie/disclosures/2024/", text=HTML_YEAR_PAGE_CONTENT)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    results = [r for r in writer.results if r["public_body_id"] == 1001]
    assert len(results) == 1
    assert results[0]["file_url"] == "https://dept-a.ie/disclosures/2024/q1.pdf"


def test_no_files_produces_no_records(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_NO_FILES)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    assert writer.results == []


def test_output_has_required_fields(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=HTML_WITH_PDF)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    r = writer.results[0]
    assert {"public_body_id", "disclosure_page_url", "file_url", "file_type"} <= r.keys()


def test_connection_error_logs_and_skips(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/disclosure/", exc=req.exceptions.ConnectionError("x"))
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_WITH_PDF)
    process(INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 1001 for r in writer.results)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_duplicate_file_urls_deduplicated(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    html = '<html><body><a href="/q1.pdf">Q1</a><a href="/q1.pdf">Q1 again</a></body></html>'
    requests_mock.get("https://dept-a.ie/foi/disclosure/", text=html)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT, tmp_path, writer)
    results = [r for r in writer.results if r["public_body_id"] == 1001]
    assert len(results) == 1


INPUT_DIRECT_FILE = {
    "metadata": {"step": "find_disclosure_pages", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 2001, "name": "Direct PDF Body",
         "foi_page_url": "https://body-a.ie/foi/",
         "disclosure_page_url": "https://body-a.ie/files/foi-disclosure-log-2025.pdf"},
        {"public_body_id": 2002, "name": "Direct XLSX Body",
         "foi_page_url": "https://body-b.ie/foi/",
         "disclosure_page_url": "https://body-b.ie/files/foi-log.xlsx"},
        {"public_body_id": 2003, "name": "HTML Page Body",
         "foi_page_url": "https://body-c.ie/foi/",
         "disclosure_page_url": "https://body-c.ie/foi/disclosure/"},
    ],
}


def test_direct_pdf_url_emitted_without_http_request(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://body-c.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT_DIRECT_FILE, tmp_path, writer)
    results = [r for r in writer.results if r["public_body_id"] == 2001]
    assert len(results) == 1
    assert results[0]["file_url"] == "https://body-a.ie/files/foi-disclosure-log-2025.pdf"
    assert results[0]["file_type"] == "pdf"
    assert results[0]["disclosure_page_url"] == "https://body-a.ie/files/foi-disclosure-log-2025.pdf"
    fetched = [r.url for r in requests_mock.request_history]
    assert not any("body-a.ie" in u for u in fetched), "direct file URL must not be fetched as HTML"


def test_direct_xlsx_url_emitted_without_http_request(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://body-c.ie/foi/disclosure/", text=HTML_NO_FILES)
    process(INPUT_DIRECT_FILE, tmp_path, writer)
    results = [r for r in writer.results if r["public_body_id"] == 2002]
    assert len(results) == 1
    assert results[0]["file_type"] == "xlsx"
    fetched = [r.url for r in requests_mock.request_history]
    assert not any("body-b.ie" in u for u in fetched), "direct file URL must not be fetched as HTML"


def test_html_disclosure_page_still_crawled(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://body-c.ie/foi/disclosure/", text=HTML_WITH_PDF)
    process(INPUT_DIRECT_FILE, tmp_path, writer)
    results = [r for r in writer.results if r["public_body_id"] == 2003]
    assert len(results) == 1
    assert results[0]["file_url"] == "https://body-c.ie/disclosures/q1-2024.pdf"


def test_resume_skips_already_processed_body(requests_mock, tmp_path, make_writer):
    # Writer pre-loaded with body 1001 already done
    from lib.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "disclosure_page_url": "https://dept-a.ie/foi/disclosure/",
                     "file_url": "https://dept-a.ie/disclosures/q1-2024.pdf", "file_type": "pdf"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    requests_mock.get("https://dept-b.ie/foi/disclosure/", text=HTML_WITH_PDF)
    # dept-a.ie should NOT be fetched (already processed)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history
                    if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0
    assert len([r for r in writer.results if r["public_body_id"] == 1001]) == 1


import sys as _sys
from lib.file_utils import read_json as _read_json, write_json as _write_json
import steps.find_disclosure_files.process as _proc


def test_public_body_scoped_leaves_others_untouched(requests_mock, tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    # Seed file-keyed records (file_url key)
    seeded = [
        {"public_body_id": 1001, "file_url": "https://a.ie/f1.pdf", "marker": "keep-1001"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f1.pdf", "marker": "old-1002-f1"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f2.pdf", "marker": "old-1002-f2"},
        {"public_body_id": 1003, "file_url": "https://c.ie/f1.pdf", "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "find_disclosure_files"}, "results": seeded})

    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "disclosure_page_url": "https://a.ie/disc/"},
        {"public_body_id": 1002, "disclosure_page_url": "https://b.ie/disc/"},
        {"public_body_id": 1003, "disclosure_page_url": "https://c.ie/disc/"},
    ]})
    requests_mock.get("https://b.ie/disc/", text=HTML_WITH_MULTIPLE)

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    body_map = {}
    for r in results:
        body_map.setdefault(r["public_body_id"], []).append(r)

    # 1001 and 1003 records untouched
    assert body_map[1001][0]["marker"] == "keep-1001"
    assert body_map[1003][0]["marker"] == "keep-1003"
    # Old 1002 file records removed, new ones present
    assert not any(r.get("marker", "").startswith("old-1002") for r in body_map.get(1002, []))
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]
