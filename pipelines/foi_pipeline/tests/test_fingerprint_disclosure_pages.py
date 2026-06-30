import hashlib
import json
import pytest
import requests as req
from steps.fingerprint_disclosure_pages.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "find_disclosure_pages", "completed_at": "2026-06-29T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "disclosure_page_url": "https://dept-a.ie/disc/"},
        {"public_body_id": 1002, "name": "Dept B", "disclosure_page_url": "https://dept-b.ie/disc/"},
    ],
}

HTML_WITH_ONE_FILE = '<html><body><a href="/disclosures/foi-log-2024.pdf">FOI Log 2024</a></body></html>'
HTML_WITH_TWO_FILES = (
    '<html><body>'
    '<a href="/disclosures/foi-log-2024.pdf">FOI Log 2024</a>'
    '<a href="/disclosures/foi-log-2023.pdf">FOI Log 2023</a>'
    '</body></html>'
)
HTML_NO_FILES = '<html><body><p>No files here</p></body></html>'


def _hash(urls):
    raw = "\n".join(sorted(set(urls)))
    return "sha256-" + hashlib.sha256(raw.encode()).hexdigest()


def test_hash_stability_body_not_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    expected_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: expected_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 not in dirty_ids


def test_new_link_marks_body_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_TWO_FILES)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 in dirty_ids


def test_removed_link_marks_body_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash([
        "https://dept-a.ie/disclosures/foi-log-2024.pdf",
        "https://dept-a.ie/disclosures/foi-log-2023.pdf",
    ])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 in dirty_ids


def test_new_body_no_previous_hash_is_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes={})
    assert 1001 in dirty_ids


def test_fetch_error_body_not_dirty_error_logged(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", exc=req.exceptions.ConnectionError("timeout"))
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 not in dirty_ids
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME
    assert errors[0]["context"]["public_body_id"] == 1001


def test_fetch_error_preserves_previous_hash_in_output(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", exc=req.exceptions.ConnectionError("timeout"))
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    assert result_1001["page_hash"] == old_hash


def test_output_record_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes={})
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    assert {"public_body_id", "name", "disclosure_page_url", "page_hash", "file_count"} <= result_1001.keys()
    assert result_1001["page_hash"].startswith("sha256-")
    assert result_1001["file_count"] == 1


def test_force_clears_hashes_all_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    current_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: current_hash, 1002: _hash([])}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes, force=True)
    assert 1001 in dirty_ids


def test_page_with_no_files_hash_is_stable(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_NO_FILES)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    results, _ = process(INPUT, tmp_path, previous_hashes={})
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    empty_hash = _hash([])
    assert result_1001["page_hash"] == empty_hash
    assert result_1001["file_count"] == 0
