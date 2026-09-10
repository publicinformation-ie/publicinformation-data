import json
from pathlib import Path
from unittest import mock

import pytest

from steps.transform_minutes_files.process import (
    STEP_NAME,
    _download,
    _cache_path,
    extract_text,
    process,
)
from lib.file_utils import read_json


def test_extract_text_falls_back_to_pdfplumber_when_marker_fails():
    pdf_bytes = b"%PDF-1.4 fake"
    with mock.patch("steps.transform_minutes_files.process._extract_marker", return_value=""):
        with mock.patch("steps.transform_minutes_files.process._extract_pdfplumber",
                        return_value="PDF text extracted"):
            text, extractor = extract_text(pdf_bytes)
    assert text == "PDF text extracted"
    assert extractor == "pdfplumber"


def test_extract_text_uses_marker_when_it_succeeds():
    pdf_bytes = b"%PDF-1.4 fake"
    with mock.patch("steps.transform_minutes_files.process._extract_marker",
                    return_value="Marker text"):
        with mock.patch("steps.transform_minutes_files.process._extract_pdfplumber",
                        return_value="PDF text extracted"):
            text, extractor = extract_text(pdf_bytes)
    assert text == "Marker text"
    assert extractor == "marker_pdf"


def test_download_caches_pdf_to_disk(tmp_path):
    url = "https://x.ie/meeting-2024-07-08.pdf"
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        class R:
            content = b"%PDF-1.4 cached"
        m.return_value = R()
        first = _download(url, tmp_path)
    assert first == b"%PDF-1.4 cached"
    path = _cache_path(tmp_path, url)
    assert path.exists()
    assert path.read_bytes() == b"%PDF-1.4 cached"


def test_download_reuses_cache_without_fetching(tmp_path):
    url = "https://x.ie/meeting-2024-07-08.pdf"
    path = _cache_path(tmp_path, url)
    path.write_bytes(b"%PDF-1.4 cached")
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        data = _download(url, tmp_path)
    m.assert_not_called()
    assert data == b"%PDF-1.4 cached"


def test_process_logs_error_when_text_extraction_is_empty(tmp_path, make_writer):
    # Deep path + query string: a regression that collapses the URL to its
    # domain (www.meath.ie) would be unambiguous.
    full_url = ("https://www.meath.ie/system/files/media/file-uploads/2026-05/"
                "05-2026%20Minutes%20Navan%20MD.pdf?ver=2")
    item = {
        "public_body_id": 1511, "municipal_district": "Navan",
        "file_url": full_url, "meeting_date": "2024-07-08",
    }
    with mock.patch("steps.transform_minutes_files.process._download",
                    return_value=b"%PDF-1.4 empty"):
        with mock.patch("steps.transform_minutes_files.process.extract_text",
                        return_value=("", "pdfplumber")):
            writer = make_writer(STEP_NAME, key_field="file_url")
            process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    errors = read_json(tmp_path / "errors.json")
    empty = [e for e in errors if e["error_type"] == "EmptyTextExtraction"]
    assert len(empty) == 1
    ctx = empty[0]["context"]
    assert ctx["file_url"] == full_url    # full URL preserved, not collapsed to a domain
    assert "url" not in ctx               # the sanitiser-collapsed key is gone
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == ""


def test_download_rejects_non_pdf_response(tmp_path):
    url = "https://x.ie/meeting-2024-07-08.pdf"
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        class R:
            content = b"<html>not a pdf</html>"
        m.return_value = R()
        with pytest.raises(ValueError):
            _download(url, tmp_path)
    assert not _cache_path(tmp_path, url).exists()


def test_download_writes_atomically_without_tmp_leftover(tmp_path):
    url = "https://x.ie/meeting-2024-07-08.pdf"
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        class R:
            content = b"%PDF-1.4 ok"
        m.return_value = R()
        data = _download(url, tmp_path)
    path = _cache_path(tmp_path, url)
    assert data == b"%PDF-1.4 ok"
    assert path.read_bytes() == b"%PDF-1.4 ok"
    assert not path.with_suffix(".tmp").exists()
