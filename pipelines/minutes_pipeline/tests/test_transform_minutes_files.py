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


def test_extract_html_text_keeps_inline_tags_on_one_line():
    html = ("<div class='b'><p>Held on Monday 9<sup>th</sup> <strong>February</strong>\n"
            "2026 in the <span>Chamber</span></p><p>Present: Cllr A.</p>"
            "<p>Line one<br>Line two</p></div>")
    lines = extract_html_text(html, ".b").split("\n")
    assert lines == ["Held on Monday 9th February 2026 in the Chamber",
                     "Present: Cllr A.", "Line one", "Line two"]


def test_extract_html_text_keeps_content_after_self_closing_br():
    # Sligo: an unclosed <br> earlier in the page makes html.parser nest
    # everything after a later <br/> inside it; replacing the <br> must not
    # discard those children.
    html = ("<p>Opening Hours<br> </p>"
            "<div class='b'><h3>Minutes</h3><br/>"
            "<h3>PRESENT</h3><ul><li>Cllr A</li></ul><p>Decision made.</p></div>")
    lines = extract_html_text(html, ".b").split("\n")
    assert lines == ["Minutes", "PRESENT", "Cllr A", "Decision made."]


def test_extract_html_text_excludes_script_style_and_comments():
    html = ("<div class='b'><script>var leak1=1;</script><style>.leak2{}</style>"
            "<!-- leak3 --><p>Real text</p></div>")
    assert extract_html_text(html, ".b") == "Real text"


def test_extract_html_text_script_only_body_is_empty():
    with pytest.raises(ValueError, match="empty"):
        extract_html_text("<div class='b'><script>x=1</script><!-- c --></div>", ".b")


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


# --- Word (.docx) minutes -----------------------------------------------------

import io as _io
import zipfile as _zipfile

from steps.transform_minutes_files.process import extract_document_text, extract_docx_text

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx_bytes(body_xml):
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?>'
                   f'<w:document xmlns:w="{_W_NS}"><w:body>{body_xml}</w:body></w:document>')
    return buf.getvalue()


def _para(*runs):
    return "<w:p>" + "".join(runs) + "</w:p>"


def _run(text):
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


def test_extract_document_text_reads_docx_paragraphs_tabs_and_breaks():
    data = _docx_bytes(
        _para(_run("Minutes of the Council Meeting")) +
        _para(_run("Item 1"), "<w:r><w:tab/></w:r>", _run("Adopted")) +
        _para(_run("Line one"), "<w:r><w:br/></w:r>", _run("line two")) +
        "<w:tbl><w:tr><w:tc>" + _para(_run("Cell text")) + "</w:tc></w:tr></w:tbl>"
    )
    text, extractor = extract_document_text(data)
    assert extractor == "docx"
    assert text == ("Minutes of the Council Meeting\n"
                    "Item 1 Adopted\n"
                    "Line one\nline two\n"
                    "Cell text")


def test_extract_document_text_empty_docx_returns_empty_text():
    text, extractor = extract_document_text(_docx_bytes(_para()))
    assert text == "" and extractor == "docx"


def test_extract_document_text_rejects_docx_with_doctype():
    xml = ('<?xml version="1.0"?><!DOCTYPE w [<!ENTITY a "x">]>'
           f'<w:document xmlns:w="{_W_NS}"><w:body>&a;</w:body></w:document>')
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    with pytest.raises(ValueError, match="DOCTYPE"):
        extract_document_text(buf.getvalue())


def test_extract_document_text_pdf_still_uses_pdfplumber():
    with mock.patch("steps.transform_minutes_files.process._extract_pdfplumber",
                    return_value="pdf words"):
        assert extract_document_text(b"%PDF-1.4 x") == ("pdf words", "pdfplumber")


def test_extract_document_text_rejects_unknown_bytes():
    with pytest.raises(ValueError, match="neither a PDF nor a DOCX"):
        extract_document_text(b"<html>error</html>")


def test_download_accepts_docx_and_caches_it_as_docx(tmp_path):
    url = "https://meetings.southdublin.ie/Home/ViewReply/87222"
    data = _docx_bytes(_para(_run("May 2025 Council Minutes")))
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        class R:
            content = data
        m.return_value = R()
        assert _download(url, tmp_path) == data
    assert _cache_path(tmp_path, url, ".docx").read_bytes() == data
    assert not _cache_path(tmp_path, url).exists()


def test_download_reuses_docx_cache_without_fetching(tmp_path):
    url = "https://meetings.southdublin.ie/Home/ViewReply/87222"
    data = _docx_bytes(_para(_run("cached")))
    _cache_path(tmp_path, url, ".docx").write_bytes(data)
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        assert _download(url, tmp_path) == data
    m.assert_not_called()


def test_process_one_docx_item_extracts_text_with_docx_extractor(tmp_path):
    url = "https://meetings.southdublin.ie/Home/ViewReply/86452"
    item = {"public_body_id": 1732, "municipal_district": None, "file_url": url}
    data = _docx_bytes(_para(_run("May 2025 Council Minutes")))
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        class R:
            content = data
        m.return_value = R()
        _, record, exc = _process_one(item, tmp_path)
    assert exc is None
    assert record["text"] == "May 2025 Council Minutes"
    assert record["extractor"] == "docx"


def test_download_still_rejects_html_as_not_a_document(tmp_path):
    url = "https://meetings.southdublin.ie/Home/ViewReply/1"
    with mock.patch("steps.transform_minutes_files.process.fetch") as m:
        class R:
            content = b"<html>error</html>"
        m.return_value = R()
        with pytest.raises(ValueError, match="neither a PDF nor a DOCX"):
            _download(url, tmp_path)


def test_extract_docx_rejects_utf16_doctype_that_bypasses_byte_guard():
    # UTF-16 bytes contain no b"<!DOCTYPE" sequence, so only a parser-level
    # check catches the entity declaration.
    xml = ('<?xml version="1.0" encoding="UTF-16"?>'
           '<!DOCTYPE w:document [<!ENTITY e "pwned">]>'
           f'<w:document xmlns:w="{_W_NS}"><w:body><w:p><w:r><w:t>&e;</w:t></w:r></w:p>'
           '</w:body></w:document>').encode("utf-16")
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    with pytest.raises(ValueError, match="DOCTYPE"):
        extract_docx_text(buf.getvalue())


def test_extract_docx_rejects_oversized_document_xml(monkeypatch):
    import steps.transform_minutes_files.process as proc
    monkeypatch.setattr(proc, "_MAX_DOCX_XML_BYTES", 1024)
    big = _docx_bytes(_para(_run("x" * 5000)))
    with pytest.raises(ValueError, match="too large"):
        extract_docx_text(big)


def test_extract_docx_text_reads_text_box_paragraphs_once():
    box = "<w:r><w:txbxContent>" + _para(_run("Boxed note")) + "</w:txbxContent></w:r>"
    data = _docx_bytes("<w:p>" + _run("Intro") + box + "</w:p>")
    text, extractor = extract_document_text(data)
    assert extractor == "docx"
    assert text == "Intro\nBoxed note"


def test_extract_docx_text_ignores_alternate_content_fallback():
    mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    alt = (f'<mc:AlternateContent xmlns:mc="{mc}">'
           f'<mc:Choice Requires="wps">{_para(_run("Shared text"))}</mc:Choice>'
           f'<mc:Fallback>{_para(_run("Shared text"))}</mc:Fallback>'
           f'</mc:AlternateContent>')
    text, _ = extract_document_text(_docx_bytes(_para(_run("Intro")) + alt))
    assert text == "Intro\nShared text"


def test_extract_docx_text_survives_deeply_nested_text_boxes():
    depth = 1000
    body = (_run("deep")
            + "<w:r><w:txbxContent><w:p>" * depth
            + _run("bottom")
            + "</w:p></w:txbxContent></w:r>" * depth)
    text, _ = extract_document_text(_docx_bytes("<w:p>" + body + "</w:p>"))
    assert text.splitlines()[0] == "deep"
    assert text.splitlines()[-1] == "bottom"
