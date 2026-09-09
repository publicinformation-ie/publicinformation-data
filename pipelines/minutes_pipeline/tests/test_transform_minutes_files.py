import json
from pathlib import Path
from unittest import mock

import pytest

from steps.transform_minutes_files.process import (
    STEP_NAME,
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
