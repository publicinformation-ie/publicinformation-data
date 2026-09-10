from unittest import mock

from steps.ocr_minutes_files.process import (
    STEP_NAME,
    ocr_pdf_bytes,
    process,
)
from lib.file_utils import read_json


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


def test_non_empty_passthrough_preserves_text_and_extractor(tmp_path, make_writer):
    item = _item(text="Text layer prose", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for") as m_bytes:
        m_bytes.side_effect = AssertionError("OCR path must not fetch PDFs")
        writer = make_writer(STEP_NAME, key_field="file_url")
        process({"results": [item]}, tmp_path, writer)
        writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == "Text layer prose"
    assert out["results"][0]["extractor"] == "pdfplumber"
    assert read_json(tmp_path / "errors.json") == []


def test_empty_text_is_ocrd(tmp_path, make_writer):
    item = _item(text="", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         return_value="OCR recognised text"):
            writer = make_writer(STEP_NAME, key_field="file_url")
            process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == "OCR recognised text"
    assert out["results"][0]["extractor"] == "tesseract"
    assert read_json(tmp_path / "errors.json") == []


def test_ocr_still_empty_logs_error(tmp_path, make_writer):
    item = _item(text="   ", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         return_value="  \n "):
            writer = make_writer(STEP_NAME, key_field="file_url")
            process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == ""
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "EmptyTextExtraction"
    assert errors[0]["context"]["file_url"] == item["file_url"]


def test_ocr_exception_logs_ocr_failed(tmp_path, make_writer):
    item = _item(text="", extractor="pdfplumber")
    with mock.patch("steps.ocr_minutes_files.process._pdf_bytes_for",
                     return_value=b"%PDF-1.4 fake"):
        with mock.patch("steps.ocr_minutes_files.process.ocr_pdf_bytes",
                         side_effect=RuntimeError("tesseract boom")):
            writer = make_writer(STEP_NAME, key_field="file_url")
            process({"results": [item]}, tmp_path, writer)
            writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert out["results"][0]["text"] == ""
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "OcrFailed"
    assert errors[0]["context"]["file_url"] == item["file_url"]


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
