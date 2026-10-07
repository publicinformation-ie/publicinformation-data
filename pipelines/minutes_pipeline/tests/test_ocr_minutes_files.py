from unittest import mock

import pytest

from steps.ocr_minutes_files.process import (
    MIN_TEXT_CHARS,
    STEP_NAME,
    _evict_thin_output_records,
    ocr_pdf_bytes,
    process,
)
from lib.file_utils import read_json, write_json


def _item(**overrides):
    base = {
        "public_body_id": 1511,
        "municipal_district": "Navan",
        "minutes_page_url": "https://x.ie/minutes",
        "file_url": "https://x.ie/meeting-2024-07-08.pdf",
        "meeting_date": "2024-07-08",
        "link_text": "Minutes July 2024",
        "text": "",
        "extractor": "pdfplumber",
    }
    base.update(overrides)
    return base


LONG_TEXT = "Minutes of the council meeting. " * 20  # well above MIN_TEXT_CHARS

assert len(LONG_TEXT.strip()) >= MIN_TEXT_CHARS


def test_non_empty_passthrough_preserves_text_and_extractor(tmp_path, make_writer):
    item = _item(text=LONG_TEXT, extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for") as m_bytes:
        m_bytes.side_effect = AssertionError("OCR path must not fetch PDFs")
        writer = make_writer(STEP_NAME, key_field="file_url")
        process({"results": [item]}, tmp_path, writer)
        writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == LONG_TEXT
    assert out["results"][0]["extractor"] == "pdfplumber"
    assert read_json(tmp_path / "errors.json") == []


def test_empty_text_is_ocrd(tmp_path, make_writer):
    item = _item(text="", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         return_value=LONG_TEXT):
            writer = make_writer(STEP_NAME, key_field="file_url")
            process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == LONG_TEXT
    assert out["results"][0]["extractor"] == "tesseract"
    assert read_json(tmp_path / "errors.json") == []


def test_ocr_still_empty_logs_error_and_quarantines(tmp_path, make_writer):
    item = _item(text="   ", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         return_value="  \n "):
            writer = make_writer(STEP_NAME, key_field="file_url")
            quarantined = process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"] == []
    assert quarantined == {item["file_url"]}
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "EmptyTextExtraction"
    assert errors[0]["context"]["file_url"] == item["file_url"]


def test_ocr_exception_logs_ocr_failed_without_record(tmp_path, make_writer):
    item = _item(text="", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         side_effect=RuntimeError("tesseract boom")):
            writer = make_writer(STEP_NAME, key_field="file_url")
            quarantined = process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"] == []
    # Infra failures are transient: retried next run, never quarantined.
    assert quarantined == set()
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "OcrFailed"
    assert errors[0]["context"]["file_url"] == item["file_url"]


def test_near_empty_passthrough_gets_ocr_attempt_and_recovers(tmp_path, make_writer):
    # Signature-date-only text layer (e.g. "28.02.2023") with real minutes
    # on scanned pages: OCR recovers usable text.
    item = _item(text="28.02.2023", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         return_value=LONG_TEXT):
            writer = make_writer(STEP_NAME, key_field="file_url")
            quarantined = process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == LONG_TEXT
    assert out["results"][0]["extractor"] == "tesseract"
    assert quarantined == set()
    assert read_json(tmp_path / "errors.json") == []


def test_near_empty_ocr_result_is_quarantined_as_near_empty_text(tmp_path, make_writer):
    item = _item(text="28.02.2023", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         return_value="29.02.2023"):
            writer = make_writer(STEP_NAME, key_field="file_url")
            quarantined = process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"] == []
    assert quarantined == {item["file_url"]}
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "NearEmptyText"
    assert errors[0]["context"]["file_url"] == item["file_url"]


def test_quarantined_urls_are_skipped_without_fetch(tmp_path, make_writer):
    item = _item(text="", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for") as m_bytes:
        m_bytes.side_effect = AssertionError("quarantined urls must not be fetched")
        writer = make_writer(STEP_NAME, key_field="file_url")
        quarantined = process({"results": [item]}, tmp_path, writer,
                              quarantined={item["file_url"]})
        writer.finalize()
    assert quarantined == {item["file_url"]}
    assert read_json(tmp_path / "output.json")["results"] == []
    assert read_json(tmp_path / "errors.json") == []


def test_evict_thin_output_records(tmp_path, make_writer):
    thin = _item(text="28.02.2023")
    good = _item(text=LONG_TEXT,
                 file_url="https://x.ie/meeting-2024-08-08.pdf")
    write_json(tmp_path / "output.json",
               {"metadata": {"step": STEP_NAME}, "results": [thin, good]})
    writer = make_writer(STEP_NAME, key_field="file_url", force=False)
    assert len(writer.results) == 2
    evicted = _evict_thin_output_records(writer)
    assert [r["file_url"] for r in evicted] == [thin["file_url"]]
    assert thin["file_url"] not in writer.processed_keys
    assert good["file_url"] in writer.processed_keys
    out = read_json(tmp_path / "output.json")
    assert [r["file_url"] for r in out["results"]] == [good["file_url"]]


def test_ocr_joins_per_page_text_in_order():
    page_texts = ["Page one", "", "Page three"]
    pages = [mock.Mock() for _ in page_texts]
    for page, _ in zip(pages, page_texts):
        page.get_pixmap.return_value = mock.Mock(width=10, height=10, samples=b"\x00" * 300)

    fake_doc = mock.MagicMock()
    fake_doc.__enter__.return_value = iter(pages)
    # pymupdf.open(...) is used as a context manager yielding an iterable of pages
    with mock.patch("pymupdf.open", return_value=fake_doc):
        with mock.patch("PIL.Image.frombytes", return_value=mock.Mock()):
            with mock.patch("pytesseract.image_to_string", side_effect=page_texts):
                result = ocr_pdf_bytes(b"%PDF-1.4 fake")
    assert result == "Page one\nPage three"
