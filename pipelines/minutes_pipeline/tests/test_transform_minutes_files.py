import json
from pathlib import Path
from unittest import mock

import pytest

from steps.transform_minutes_files.process import (
    STEP_NAME,
    _download,
    _cache_path,
    _process_one,
    extract_html_text,
    extract_text,
    process,
)
from lib.file_utils import read_json


def test_extract_text_returns_pdfplumber_text():
    pdf_bytes = b"%PDF-1.4 fake"
    with mock.patch("steps.transform_minutes_files.process._extract_pdfplumber",
                    return_value="PDF text extracted"):
        text, extractor = extract_text(pdf_bytes)
    assert text == "PDF text extracted"
    assert extractor == "pdfplumber"


def test_extract_text_empty_when_pdfplumber_empty():
    pdf_bytes = b"%PDF-1.4 fake"
    with mock.patch("steps.transform_minutes_files.process._extract_pdfplumber",
                    return_value="   "):
        text, extractor = extract_text(pdf_bytes)
    assert text == ""
    assert extractor == "pdfplumber"


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


def test_extract_html_text_returns_selected_text():
    html = ("<html><body><nav>Menu</nav>"
            "<div class='field--name-body'><h1>Minutes</h1><p>Present: Cllr A.</p></div>"
            "</body></html>")
    text = extract_html_text(html, ".field--name-body")
    assert "Minutes" in text and "Present: Cllr A." in text
    assert "Menu" not in text


def test_extract_html_text_fails_closed_when_selector_matches_nothing():
    with pytest.raises(ValueError, match="matched nothing"):
        extract_html_text("<html><body><p>x</p></body></html>", ".field--name-body")


def test_extract_html_text_fails_closed_on_whitespace_only_text():
    with pytest.raises(ValueError, match="empty"):
        extract_html_text("<div class='b'>   </div>", ".b")


def test_process_one_html_item_uses_selector_and_marks_extractor(tmp_path):
    item = {"public_body_id": 1129, "file_url": "https://x.ie/minutes-march",
            "file_kind": "html", "text_selector": ".b", "link_text": "March"}

    class R:
        status_code = 200
        text = "<div class='b'>Minutes body</div>"
        content = text.encode()

    with mock.patch("steps.transform_minutes_files.process.fetch", return_value=R()):
        url, record, exc = _process_one(item, tmp_path)
    assert exc is None
    assert record["text"] == "Minutes body"
    assert record["extractor"] == "html"
    assert record["file_kind"] == "html"


def test_process_one_html_item_error_for_missing_selector(tmp_path):
    item = {"public_body_id": 1129, "file_url": "https://x.ie/minutes-march",
            "file_kind": "html", "text_selector": ".nope"}

    class R:
        status_code = 200
        text = "<div class='b'>Minutes body</div>"
        content = text.encode()

    with mock.patch("steps.transform_minutes_files.process.fetch", return_value=R()):
        url, record, exc = _process_one(item, tmp_path)
    assert record is None and isinstance(exc, ValueError)


def test_process_one_html_cache_does_not_collide_with_pdf_cache(tmp_path):
    item = {"public_body_id": 1129, "file_url": "https://x.ie/minutes-march",
            "file_kind": "html", "text_selector": ".b"}

    class R:
        status_code = 200
        text = "<div class='b'>Body</div>"
        content = text.encode()

    with mock.patch("steps.transform_minutes_files.process.fetch", return_value=R()):
        _process_one(item, tmp_path)
    assert not _cache_path(tmp_path, item["file_url"]).exists()
    assert list(tmp_path.glob("*.html"))


def test_process_one_html_http_error_raises_and_is_not_cached(tmp_path):
    item = {"public_body_id": 1129, "file_url": "https://x.ie/minutes-march",
            "file_kind": "html", "text_selector": ".b"}

    class R:
        status_code = 500
        text = "<div class='b'>Server error page</div>"
        content = text.encode()

    with mock.patch("steps.transform_minutes_files.process.fetch", return_value=R()):
        url, record, exc = _process_one(item, tmp_path)
    assert record is None and isinstance(exc, RuntimeError)
    assert "500" in str(exc) and item["file_url"] in str(exc)
    assert not list(tmp_path.iterdir())


def test_process_one_html_selector_miss_is_not_cached(tmp_path):
    item = {"public_body_id": 1129, "file_url": "https://x.ie/minutes-march",
            "file_kind": "html", "text_selector": ".nope"}

    class R:
        status_code = 200
        text = "<div class='b'>Body</div>"
        content = text.encode()

    with mock.patch("steps.transform_minutes_files.process.fetch", return_value=R()):
        url, record, exc = _process_one(item, tmp_path)
    assert record is None and isinstance(exc, ValueError)
    assert not list(tmp_path.iterdir())
