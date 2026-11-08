"""ocr_pages step: only for listed full-page raster pages with no
meaningful text layer. One test uses real Tesseract; the edge cases mock it."""
import json
import shutil

import pymupdf
import pytest

from lib.file_utils import IncrementalWriter
from steps.extract_pages.process import process as extract_pages_process
from steps.ocr_pages import process as ep

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None,
                                     reason="tesseract binary not installed")

SENTENCE = "Emissions fell by eight percent during the first quarter"


def _text_image_bytes(text=SENTENCE, size=(595, 842), fontsize=22):
    src = pymupdf.open()
    page = src.new_page(width=size[0], height=size[1])
    page.insert_text((30, 200), text, fontsize=fontsize, fontname="helv")
    return page.get_pixmap(dpi=72).tobytes("png")


def _scanned_pdf(path, page_number_text=None, with_text_page=True):
    """Page 1: ordinary text. Page 2: a full-page raster of text, with an
    optional printed page number as its only text layer."""
    doc = pymupdf.open()
    if with_text_page:
        p1 = doc.new_page()
        p1.insert_text((72, 100), "This page has a real text layer of its own.",
                       fontsize=12, fontname="helv")
    p2 = doc.new_page()
    p2.insert_image(p2.rect, stream=_text_image_bytes(), keep_proportion=False)
    if page_number_text:
        p2.insert_text((290, 820), page_number_text, fontsize=10, fontname="helv")
    doc.save(str(path))
    doc.close()


def _run(tmp_path, make_writer, pdf, ocr_pages=(2,), page_count=2):
    """extract_pages then ocr_pages, in sibling step dirs like the real layout.
    Returns (page loader following the ocr_pages records, errors, ocr records)."""
    ep_dir, oc_dir = tmp_path / "extract_pages", tmp_path / "ocr_pages"
    ep_dir.mkdir(exist_ok=True), oc_dir.mkdir(exist_ok=True)
    upstream = [{"doc_slug": "scan-doc", "title": "Scan", "url": "https://example.org/s.pdf",
                 "page_count": page_count, "pdf_path": str(pdf)}]
    w1 = IncrementalWriter(ep_dir / "output.json", "extract_pages", key_field="doc_slug", force=True)
    extract_pages_process(upstream, tmp_path, ep_dir, w1)
    w1.finalize()
    w2 = IncrementalWriter(oc_dir / "output.json", "ocr_pages", key_field="doc_slug", force=True)
    ep.process(json.loads((ep_dir / "output.json").read_text())["results"], ep_dir,
               {"scan-doc": pdf}, {"scan-doc": list(ocr_pages)} if ocr_pages else {},
               oc_dir, w2)
    w2.finalize()
    errors = json.loads((oc_dir / "errors.json").read_text())
    assert not any(e["error_type"] == "OcrFailed" for e in errors), errors
    (record,) = json.loads((oc_dir / "output.json").read_text())["results"]
    errors = json.loads((oc_dir / "errors.json").read_text())

    def page(n):
        entry = next(e for e in record["pages"] if e["number"] == n)
        return json.loads((oc_dir / entry["file"]).read_text())
    page.record = record
    return page, errors


def _fake_words(conf=90.0, text="Emissions"):
    return [{"text": text, "conf": conf, "left": 100, "top": 200, "width": 300,
             "height": 50, "block": 1, "par": 1, "line": 1, "word": 1},
            {"text": "fell", "conf": conf, "left": 420, "top": 200, "width": 120,
             "height": 50, "block": 1, "par": 1, "line": 1, "word": 2},
            {"text": "sharply", "conf": conf, "left": 100, "top": 300, "width": 300,
             "height": 50, "block": 1, "par": 1, "line": 2, "word": 1}]


@needs_tesseract
def test_a_full_page_raster_with_no_text_layer_is_read_by_real_tesseract(tmp_path, make_writer):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    page, errors = _run(tmp_path, make_writer, pdf)

    ocr_page = page(2)
    assert ocr_page["spans"], "expected OCR spans"
    assert all(s["source"] == "ocr" for s in ocr_page["spans"])
    text = " ".join(s["text"] for s in ocr_page["spans"]).lower()
    assert "emissions" in text and "quarter" in text
    assert ocr_page["ocr"]["engine"] == "tesseract"
    assert ocr_page["ocr"]["mean_confidence"] > ep.OCR_MIN_CONFIDENCE
    assert [e for e in errors if e["error_type"].startswith("Ocr")] == []
    for span in ocr_page["spans"]:
        assert set(span) >= {"text", "font", "size", "bbox", "block", "line", "span"}
        x0, y0, x1, y1 = span["bbox"]
        assert 0 <= x0 < x1 <= ocr_page["width"] and 0 <= y0 < y1 <= ocr_page["height"]


@needs_tesseract
def test_text_pages_are_untouched_by_the_fallback(tmp_path, make_writer):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    page, _ = _run(tmp_path, make_writer, pdf)

    text_page = page(1)
    assert "ocr" not in text_page
    assert all("source" not in s for s in text_page["spans"])


def test_a_page_whose_only_text_is_a_page_number_still_counts_as_scanned(
        tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf, page_number_text="20")
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: _fake_words())
    page, _ = _run(tmp_path, make_writer, pdf)

    spans = page(2)["spans"]
    assert any(s["text"] == "20" and "source" not in s for s in spans)   # native kept
    ocr_spans = [s for s in spans if s.get("source") == "ocr"]
    assert [s["text"] for s in ocr_spans] == ["Emissions fell", "sharply"]
    native_blocks = {s["block"] for s in spans if "source" not in s}
    assert not native_blocks & {s["block"] for s in ocr_spans}


def test_a_page_with_a_real_text_layer_is_never_ocrd(tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "mixed.pdf"
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_image(p.rect, stream=_text_image_bytes(), keep_proportion=False)
    p.insert_text((72, 100), "A genuine sentence of searchable text sits over the image.",
                  fontsize=12, fontname="helv")
    doc.save(str(pdf))
    doc.close()
    calls = []
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: calls.append(1) or [])
    _run(tmp_path, make_writer, pdf, ocr_pages=(1,), page_count=1)
    assert calls == []


def test_ocr_is_opt_in_an_unlisted_scanned_page_is_never_ocrd_or_logged(
        tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    calls = []
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: calls.append(1) or [])
    for listed in ((), (1,)):
        page, errors = _run(tmp_path, make_writer, pdf, ocr_pages=listed)
        assert "ocr" not in page(2) and page(2)["spans"] == []
        assert all(e["context"]["page"] != 2 for e in errors)
    assert calls == []


def test_a_listed_page_that_is_not_scanned_logs_ocr_page_not_scanned(
        tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    calls = []
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: calls.append(1) or [])
    page, errors = _run(tmp_path, make_writer, pdf, ocr_pages=(1,))
    assert calls == []
    assert "ocr" not in page(1)
    (error,) = errors
    assert error["error_type"] == "OcrPageNotScanned"
    assert error["context"] == {"doc_slug": "scan-doc", "page": 1}


def test_a_listed_page_beyond_the_document_logs_ocr_page_not_scanned(
        tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: _fake_words())
    _page, errors = _run(tmp_path, make_writer, pdf, ocr_pages=(2, 9))
    (error,) = errors
    assert error["error_type"] == "OcrPageNotScanned" and error["context"]["page"] == 9


def test_a_blank_page_without_an_image_is_not_ocrd(tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 100), "Some body text on the first page.", fontsize=12, fontname="helv")
    doc.new_page()
    doc.save(str(pdf))
    doc.close()
    calls = []
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: calls.append(1) or [])
    page, errors = _run(tmp_path, make_writer, pdf)     # page 2 listed, but blank
    assert calls == []
    assert "ocr" not in page(2)
    assert [e["error_type"] for e in errors] == ["OcrPageNotScanned"]


def test_empty_ocr_leaves_the_gap_and_logs_an_error(tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: [])
    page, errors = _run(tmp_path, make_writer, pdf)

    assert page(2)["spans"] == []
    assert page(2)["ocr"]["word_count"] == 0
    (error,) = errors
    assert error["error_type"] == "OcrEmpty"
    assert error["context"] == {"doc_slug": "scan-doc", "page": 2}


def test_low_confidence_ocr_still_emits_text_but_logs_a_warning(tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: _fake_words(conf=ep.OCR_MIN_CONFIDENCE - 20))
    page, errors = _run(tmp_path, make_writer, pdf)

    assert page(2)["spans"], "low-confidence text is still emitted"
    (error,) = errors
    assert error["error_type"] == "OcrLowConfidence"
    assert error["context"]["page"] == 2
    assert error["context"]["mean_confidence"] == page(2)["ocr"]["mean_confidence"]


def test_ocr_output_is_deterministic(tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: _fake_words())
    page, _ = _run(tmp_path, make_writer, pdf)
    first = page(2)
    page2, _ = _run(tmp_path, make_writer, pdf)
    assert page2(2) == first


def test_a_document_without_ocr_pages_passes_through_without_opening_its_pdf(
        tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    monkeypatch.setattr(ep.pymupdf, "open", lambda *a, **k: pytest.fail("PDF opened"))
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: pytest.fail("OCR ran"))
    up = tmp_path / "extract_pages"
    # build the upstream with the real opener, then forbid it for ocr_pages
    monkeypatch.undo()
    page, errors = _run(tmp_path, make_writer, pdf, ocr_pages=())
    upstream = json.loads((up / "output.json").read_text())["results"][0]
    assert errors == []
    assert len(page.record["pages"]) == len(upstream["pages"])
    for new, old in zip(page.record["pages"], upstream["pages"]):
        assert {k: v for k, v in new.items() if k != "file"} == {k: v for k, v in old.items() if k != "file"}
        # the pointer resolves, from this step's dir, to the very same upstream file
        assert (tmp_path / "ocr_pages" / new["file"]).resolve() == (up / old["file"]).resolve()
    assert not (tmp_path / "ocr_pages" / "pages").exists()


def test_upstream_page_files_are_never_written(tmp_path, make_writer, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _scanned_pdf(pdf)
    monkeypatch.setattr(ep, "ocr_words", lambda image, **kw: _fake_words())
    _run(tmp_path, make_writer, pdf, ocr_pages=())
    up = tmp_path / "extract_pages"
    before = {p: p.read_bytes() for p in (up / "pages").rglob("*.json")}
    page, _ = _run(tmp_path, make_writer, pdf, ocr_pages=(2,))
    # extract_pages (deterministic) rewrites its own pages identically; ocr_pages adds nothing there
    after = {p: p.read_bytes() for p in (up / "pages").rglob("*.json")}
    assert after == before
    assert "ocr" not in json.loads((up / "pages" / "scan-doc" / "002.json").read_text())
    assert (tmp_path / "ocr_pages" / "pages" / "scan-doc" / "002.json").exists()
    assert page(2)["ocr"]["engine"] == "tesseract"
