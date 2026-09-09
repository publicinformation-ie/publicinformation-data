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
