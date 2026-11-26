import json
from pathlib import Path

import pytest
import requests

from steps.fetch_spc_minutes import fetching
from steps.fetch_spc_minutes.fetching import (
    NoTextLayer,
    cache_path,
    extract_pages,
    fetch_one,
    run,
)

SOURCE = {
    "committee_id": "meath/transportation-urban-regeneration",
    "committee_name": "Transportation & Urban Regeneration Strategic Policy Committee",
    "public_body_id": 1511,
    "page_url": "https://www.meath.ie/page",
    "file_url": "https://www.meath.ie/files/February%202025%20Minutes.pdf",
    "link_text": "February 2025 - Minutes - SPC",
}


def test_cold_cache_downloads_and_records_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(fetching, "extract_pages", lambda data: [{"page": 1, "words": [{"text": "x"}]}])
    calls = []

    def downloader(url):
        calls.append(url)
        return b"%PDF-1.4 fake"

    record = fetch_one(SOURCE, tmp_path, downloader=downloader)
    assert calls == [SOURCE["file_url"]]
    assert record["sha256"] == fetching.sha256_hex(b"%PDF-1.4 fake")
    assert record["size_bytes"] == len(b"%PDF-1.4 fake")
    assert record["retrieved_at"]
    assert record["page_count"] == 1
    assert cache_path(tmp_path, SOURCE["file_url"]).exists()


def test_warm_cache_makes_no_http_request(tmp_path, monkeypatch):
    monkeypatch.setattr(fetching, "extract_pages", lambda data: [{"page": 1, "words": [{"text": "x"}]}])
    pdf = cache_path(tmp_path, SOURCE["file_url"])
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 cached")
    fetching._write_sidecar(pdf, {
        "sha256": fetching.sha256_hex(b"%PDF-1.4 cached"), "size_bytes": 15,
        "retrieved_at": "2026-01-01T00:00:00+00:00",
    })

    def downloader(url):
        raise AssertionError("the cache should have answered this request")

    record = fetch_one(SOURCE, tmp_path, downloader=downloader)
    assert record["sha256"] == fetching.sha256_hex(b"%PDF-1.4 cached")
    assert record["retrieved_at"] == "2026-01-01T00:00:00+00:00"


def test_warm_cache_without_sidecar_redownloads(tmp_path, monkeypatch):
    monkeypatch.setattr(fetching, "extract_pages", lambda data: [{"page": 1, "words": [{"text": "x"}]}])
    pdf = cache_path(tmp_path, SOURCE["file_url"])
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 unverified")
    calls = []

    def downloader(url):
        calls.append(url)
        return b"%PDF-1.4 refreshed"

    record = fetch_one(SOURCE, tmp_path, downloader=downloader)
    assert calls == [SOURCE["file_url"]]
    assert record["sha256"] == fetching.sha256_hex(b"%PDF-1.4 refreshed")
    assert pdf.read_bytes() == b"%PDF-1.4 refreshed"


def test_warm_cache_with_a_mismatched_sidecar_redownloads(tmp_path, monkeypatch):
    monkeypatch.setattr(fetching, "extract_pages", lambda data: [{"page": 1, "words": [{"text": "x"}]}])
    pdf = cache_path(tmp_path, SOURCE["file_url"])
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 corrupt")
    fetching._write_sidecar(pdf, {"sha256": "a" * 64, "size_bytes": 15})

    def downloader(url):
        return b"%PDF-1.4 fresh"

    record = fetch_one(SOURCE, tmp_path, downloader=downloader)
    assert record["sha256"] == fetching.sha256_hex(b"%PDF-1.4 fresh")
    assert pdf.read_bytes() == b"%PDF-1.4 fresh"


def test_a_non_pdf_response_is_rejected_before_it_is_cached(tmp_path):
    def downloader(url):
        return b"<html><body>404</body></html>"

    with pytest.raises(fetching.InvalidPdf):
        fetch_one(SOURCE, tmp_path, downloader=downloader)
    assert not cache_path(tmp_path, SOURCE["file_url"]).exists()


def test_a_non_pdf_response_is_reported_as_invalid_not_download_failed(tmp_path):
    records, errors = run({"results": [SOURCE]}, tmp_path,
                          downloader=lambda url: b"<html>not a pdf</html>")
    assert records == []
    assert [e["error_type"] for e in errors] == ["InvalidPdf"]


def test_a_corrupt_cached_pdf_is_redownloaded_once(tmp_path, monkeypatch):
    pdf = cache_path(tmp_path, SOURCE["file_url"])
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 corrupt")
    fetching._write_sidecar(pdf, {
        "sha256": fetching.sha256_hex(b"%PDF-1.4 corrupt"), "size_bytes": 15,
    })
    calls = []

    def flaky(data):
        calls.append(data)
        if data == b"%PDF-1.4 corrupt":
            raise ValueError("broken xref")
        return [{"page": 1, "words": [{"text": "x"}]}]

    monkeypatch.setattr(fetching, "extract_pages", flaky)

    record = fetch_one(SOURCE, tmp_path,
                       downloader=lambda url: b"%PDF-1.4 repaired")
    assert calls == [b"%PDF-1.4 corrupt", b"%PDF-1.4 repaired"]
    assert record["sha256"] == fetching.sha256_hex(b"%PDF-1.4 repaired")


def test_pdf_without_text_layer_is_an_error_and_no_record(tmp_path, monkeypatch):
    def no_text(data):
        raise NoTextLayer("no extractable text on any page")

    monkeypatch.setattr(fetching, "extract_pages", no_text)
    records, errors = run({"results": [SOURCE]}, tmp_path,
                          downloader=lambda url: b"%PDF-1.4 fake")
    assert records == []
    assert [e["error_type"] for e in errors] == ["NoTextLayer"]
    assert SOURCE["file_url"] in errors[0]["error_message"]


def test_download_failure_is_an_error_and_no_record(tmp_path):
    def failing(url):
        raise requests.exceptions.SSLError("certificate verify failed")

    records, errors = run({"results": [SOURCE]}, tmp_path, downloader=failing)
    assert records == []
    assert [e["error_type"] for e in errors] == ["DownloadFailed"]
    assert "certificate verify failed" in errors[0]["error_message"]


def test_download_keeps_verification_on(monkeypatch):
    captured = {}

    class Response:
        content = b"%PDF-1.4 fake"

        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(fetching.requests, "get", fake_get)
    assert fetching.download("https://www.meath.ie/x.pdf") == b"%PDF-1.4 fake"
    assert captured["verify"] is not False
    assert captured["verify"]


FIXTURES = Path(__file__).resolve().parent / "fixtures"
MANIFEST = FIXTURES / "meetings.json"


def _manifest() -> list[dict]:
    return json.loads(MANIFEST.read_text())["meetings"]


def test_committed_fixture_pdfs_are_sha_pinned():
    meetings = _manifest()
    assert len(meetings) == 6
    for entry in meetings:
        pdf = FIXTURES / "pdf" / entry["pdf"]
        assert pdf.exists(), entry["pdf"]
        assert fetching.sha256_hex(pdf.read_bytes()) == entry["sha256"], entry["pdf"]


def test_committed_pdfs_have_words():
    """The fixture PDFs, not a git-ignored cache, are what CI parses."""
    for entry in _manifest():
        pages = extract_pages((FIXTURES / "pdf" / entry["pdf"]).read_bytes())
        assert pages and any(page["words"] for page in pages)
