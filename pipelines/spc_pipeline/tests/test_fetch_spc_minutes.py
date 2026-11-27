import json
from pathlib import Path

import pytest
import requests

from steps.fetch_spc_minutes import fetching
from steps.fetch_spc_minutes.fetching import (
    CachedOcr,
    FixtureOcr,
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


def _words(*texts, conf=None):
    return [{"text": t, "x0": 10.0 * i, "x1": 10.0 * i + 8, "top": 1.0, "bottom": 9.0,
             **({"conf": conf} if conf is not None else {})}
            for i, t in enumerate(texts)]


class FakeOcr:
    """Provider returning canned words per page; counts page calls."""

    def __init__(self, pages, engine="tesseract 5.5.2 lang=eng psm=4 dpi=300"):
        self.pages = pages
        self.engine = engine
        self.calls = []

    def engine_for(self, sha256):
        return self.engine

    def page_words(self, data, sha256, page_number):
        self.calls.append(page_number)
        return self.pages.get(page_number, [])


def _text_pages(*page_words):
    return [{"page": i, "width": 595.0, "height": 842.0, "words": words}
            for i, words in enumerate(page_words, start=1)]


def _patch_text(monkeypatch, *page_words):
    monkeypatch.setattr(fetching, "extract_pages", lambda data: _text_pages(*page_words))


def _fetch(tmp_path, ocr, overrides=None):
    return run({"results": [SOURCE]}, tmp_path, downloader=lambda url: b"%PDF-1.4 fake",
               ocr=ocr, overrides=overrides)


def test_text_layer_only_file_never_calls_ocr(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), _words("b"))
    ocr = FakeOcr({})
    records, errors = _fetch(tmp_path, ocr)
    assert errors == []
    assert ocr.calls == []
    assert records[0]["text_source"] == "text_layer"
    assert records[0]["ocr_engine"] is None
    assert [p["source"] for p in records[0]["pages"]] == ["text_layer", "text_layer"]


def test_scanned_file_is_read_by_ocr_page_by_page(tmp_path, monkeypatch):
    _patch_text(monkeypatch, [], [])
    ocr = FakeOcr({1: _words("Item", "1", conf=95.0), 2: _words("Done", conf=90.0)})
    records, errors = _fetch(tmp_path, ocr)
    assert errors == []
    record = records[0]
    assert record["text_source"] == "ocr"
    assert record["ocr_engine"] == ocr.engine
    assert [p["source"] for p in record["pages"]] == ["ocr", "ocr"]
    assert record["pages"][0]["words"][0]["conf"] == 95.0
    assert record["pages"][0]["ocr_mean_confidence"] == 95.0
    assert [w["text"] for w in record["pages"][0]["words"]] == ["Item", "1"]


def test_mixed_file_uses_text_layer_then_ocr_for_the_scanned_page(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), _words("b"), _words("c"), [])
    ocr = FakeOcr({4: _words("signed", conf=88.0)})
    records, errors = _fetch(tmp_path, ocr)
    assert errors == []
    assert ocr.calls == [4]
    assert records[0]["text_source"] == "mixed"
    assert records[0]["ocr_engine"] == ocr.engine
    assert [p["source"] for p in records[0]["pages"]] == [
        "text_layer", "text_layer", "text_layer", "ocr"]


def test_no_words_from_either_source_is_no_text_recovered(tmp_path, monkeypatch):
    _patch_text(monkeypatch, [], [])
    records, errors = _fetch(tmp_path, FakeOcr({}))
    assert records == []
    assert [e["error_type"] for e in errors] == ["NoTextRecovered"]
    assert SOURCE["file_url"] in errors[0]["error_message"]


def test_low_confidence_page_is_an_error_and_no_record(tmp_path, monkeypatch):
    _patch_text(monkeypatch, [], [])
    ocr = FakeOcr({1: _words("fine", conf=95.0),
                   2: _words("x", "y", conf=fetching.OCR_MIN_PAGE_CONF - 5)})
    records, errors = _fetch(tmp_path, ocr)
    assert records == []
    assert [e["error_type"] for e in errors] == ["OcrLowConfidence"]
    assert errors[0]["context"]["page"] == 2
    assert errors[0]["context"]["mean_confidence"] < fetching.OCR_MIN_PAGE_CONF


def test_low_confidence_words_in_a_passing_page_are_kept_unchanged(tmp_path, monkeypatch):
    _patch_text(monkeypatch, [])
    page = _words("good", "good", "dubious", conf=0)
    for word in page[:2]:
        word["conf"] = 99.0
    page[2]["conf"] = 70.0                     # mean 89.3, above the gate
    records, errors = _fetch(tmp_path, FakeOcr({1: [dict(w) for w in page]}))
    assert errors == []
    assert records[0]["pages"][0]["words"] == page


SHA = fetching.sha256_hex(b"%PDF-1.4 fake")


def _skip(page=2, sha=SHA):
    return {"file_sha256": sha, "page": page, "action": "skip", "reason": "signature page"}


def test_empty_ocr_page_without_override_is_an_error(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), [])
    records, errors = _fetch(tmp_path, FakeOcr({}))
    assert records == []
    assert [e["error_type"] for e in errors] == ["EmptyOcrPage"]
    assert errors[0]["context"]["page"] == 2


def test_empty_ocr_page_with_override_is_skipped_and_counted(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), [])
    records, errors = _fetch(tmp_path, FakeOcr({}), overrides=[_skip()])
    assert errors == []
    record = records[0]
    assert record["ocr_skipped_pages"] == 1
    assert record["pages"][1]["source"] == "skipped"
    assert record["pages"][1]["skip_reason"] == "signature page"
    assert record["pages"][1]["words"] == []
    assert record["text_source"] == "text_layer"        # no OCR words were used
    assert record["ocr_engine"] is None


def test_republished_file_loses_its_override_and_the_stale_one_is_reported(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), [])
    stale = _skip(sha=fetching.sha256_hex(b"%PDF-1.4 the old bytes"))
    records, errors = _fetch(tmp_path, FakeOcr({}), overrides=[stale])
    assert records == []
    assert sorted(e["error_type"] for e in errors) == ["EmptyOcrPage", "StaleOcrOverride"]


def test_override_skips_a_junk_page_that_would_fail_the_gate_and_drops_its_words(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), [])
    junk = _words("x", "y", "z", conf=13.0)
    records, errors = _fetch(tmp_path, FakeOcr({2: junk}), overrides=[_skip()])
    assert errors == []
    page = records[0]["pages"][1]
    assert page["source"] == "skipped" and page["words"] == []
    assert page["skipped_word_count"] == 3
    assert records[0]["ocr_skipped_pages"] == 1


def test_override_never_skips_a_page_that_passes_the_gate(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), [])
    records, errors = _fetch(tmp_path, FakeOcr({2: _words("real", "text", conf=95.0)}),
                             overrides=[_skip()])
    assert errors == []
    assert records[0]["pages"][1]["source"] == "ocr"
    assert records[0]["ocr_skipped_pages"] == 0


def test_junk_page_without_an_override_still_fails_low_confidence(tmp_path, monkeypatch):
    _patch_text(monkeypatch, _words("a"), [])
    records, errors = _fetch(tmp_path, FakeOcr({2: _words("x", conf=13.0)}))
    assert records == [] and [e["error_type"] for e in errors] == ["OcrLowConfidence"]


def test_load_overrides_validates_entries(tmp_path):
    path = tmp_path / "ocr_overrides.json"
    path.write_text(json.dumps([_skip()]))
    assert fetching.load_overrides(path) == [_skip()]
    assert fetching.load_overrides(tmp_path / "missing.json") == []
    for bad in ({**_skip(), "reason": ""}, {**_skip(), "action": "keep"},
                {**_skip(), "file_sha256": "abc"}, {**_skip(), "page": 0}):
        path.write_text(json.dumps([bad]))
        with pytest.raises(ValueError):
            fetching.load_overrides(path)


def test_ocr_cache_prevents_a_second_ocr_run(tmp_path):
    base = FakeOcr({1: _words("a", conf=90.0)})
    cache = CachedOcr(base, tmp_path / "x.pdf.ocr.json")
    first = cache.page_words(b"pdf", "s" * 64, 1)
    second = cache.page_words(b"pdf", "s" * 64, 1)
    assert first == second
    assert base.calls == [1]


def test_ocr_cache_misses_when_the_engine_changes(tmp_path):
    path = tmp_path / "x.pdf.ocr.json"
    old = FakeOcr({1: _words("old", conf=90.0)}, engine="tesseract 5.4.0 lang=eng psm=4 dpi=300")
    new = FakeOcr({1: _words("new", conf=90.0)}, engine="tesseract 5.5.2 lang=eng psm=4 dpi=300")
    CachedOcr(old, path).page_words(b"pdf", "s" * 64, 1)
    words = CachedOcr(new, path).page_words(b"pdf", "s" * 64, 1)
    assert new.calls == [1]
    assert words[0]["text"] == "new"


def test_ocr_cache_misses_when_the_file_sha_changes(tmp_path):
    path = tmp_path / "x.pdf.ocr.json"
    base = FakeOcr({1: _words("a", conf=90.0)})
    CachedOcr(base, path).page_words(b"pdf", "a" * 64, 1)
    CachedOcr(base, path).page_words(b"pdf", "b" * 64, 1)
    assert base.calls == [1, 1]


def test_unchanged_rerun_of_a_scanned_file_does_no_ocr(tmp_path, monkeypatch):
    _patch_text(monkeypatch, [])
    live = FakeOcr({1: _words("a", conf=90.0)})
    for _ in range(2):
        records, errors = run({"results": [SOURCE]}, tmp_path,
                              downloader=lambda url: b"%PDF-1.4 fake",
                              ocr=CachedOcr(live, fetching.ocr_cache_path(
                                  cache_path(tmp_path, SOURCE["file_url"]))))
        assert errors == []
    assert live.calls == [1]


def test_fixture_ocr_replays_committed_words_and_refuses_unknown_files(tmp_path):
    (tmp_path / "2025-12-11.json").write_text(json.dumps({
        "sha256": "f" * 64, "engine": "tesseract 5.5.2 lang=eng psm=4 dpi=300",
        "pages": {"1": _words("hello", conf=93.0)},
    }))
    ocr = FixtureOcr(tmp_path)
    assert ocr.engine_for("f" * 64).startswith("tesseract 5.5.2")
    assert ocr.page_words(b"", "f" * 64, 1)[0]["text"] == "hello"
    with pytest.raises(KeyError):
        ocr.page_words(b"", "0" * 64, 1)
    with pytest.raises(KeyError):
        ocr.page_words(b"", "f" * 64, 2)


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
    assert len(meetings) == 17
    for entry in meetings:
        pdf = FIXTURES / "pdf" / entry["pdf"]
        assert pdf.exists(), entry["pdf"]
        assert fetching.sha256_hex(pdf.read_bytes()) == entry["sha256"], entry["pdf"]


def test_text_layer_fixture_pdfs_have_words():
    """The fixture PDFs, not a git-ignored cache, are what CI parses."""
    for entry in _manifest():
        if not entry["committee_id"].startswith("meath/"):
            continue
        pages = extract_pages((FIXTURES / "pdf" / entry["pdf"]).read_bytes())
        assert pages and all(page["words"] for page in pages)


def test_every_scanned_fixture_has_committed_ocr_for_exactly_its_wordless_pages():
    """No fixture is parsed without OCR output that matches its PDF and engine."""
    ocr = FixtureOcr(FIXTURES / "ocr")
    scanned = 0
    for entry in _manifest():
        data = (FIXTURES / "pdf" / entry["pdf"]).read_bytes()
        wordless = [p["page"] for p in extract_pages(data) if not p["words"]]
        if not wordless:
            continue
        scanned += 1
        committed = ocr.entries[entry["sha256"]]
        assert sorted(int(n) for n in committed["pages"]) == wordless, entry["pdf"]
        assert committed["engine"] == "tesseract 5.5.2 lang=eng psm=4 dpi=300"
    assert scanned == 11


def test_committed_ocr_clears_the_confidence_gate_except_the_blank_pages():
    """OCR_MIN_PAGE_CONF is set from these fixtures with a margin (README)."""
    ocr = FixtureOcr(FIXTURES / "ocr")
    low = {}
    for sha, entry in ocr.entries.items():
        for number, words in entry["pages"].items():
            if words:
                mean = sum(w["conf"] for w in words) / len(words)
                if mean < fetching.OCR_MIN_PAGE_CONF:
                    low[(sha[:8], number)] = round(mean, 1)
    # Westmeath 28 Nov 2025 page 4 is a blank sheet whose speckle OCR reads as 3 junk
    # words; a reviewed override in ocr_overrides.json skips it.
    assert set(low) == {("719555fd", "4")}
    clear = [sum(w["conf"] for w in words) / len(words)
             for entry in ocr.entries.values() for words in entry["pages"].values()
             if words and sum(w["conf"] for w in words) / len(words) >= fetching.OCR_MIN_PAGE_CONF]
    assert min(clear) >= fetching.OCR_MIN_PAGE_CONF + 5      # margin over the lowest real page


def test_westmeath_blank_last_pages_and_recovered_text_on_the_real_fixtures(fetch_by_pdf):
    sept = fetch_by_pdf("westmeath-2025-09-19.pdf")
    assert sept["ocr_skipped_pages"] == 1
    nov = fetch_by_pdf("westmeath-2025-11-28.pdf")
    assert [p["source"] for p in nov["pages"]] == ["ocr", "ocr", "ocr", "skipped"]
    assert nov["pages"][3]["skipped_word_count"] == 3
    assert [p["source"] for p in sept["pages"]] == ["ocr", "ocr", "ocr", "skipped"]
    assert sept["text_source"] == "ocr"

    # 6 March 2026: page 4 has no text layer, but OCR recovers real text, so no override.
    march = fetch_by_pdf("westmeath-2026-03-06.pdf")
    assert march["ocr_skipped_pages"] == 0
    assert [p["source"] for p in march["pages"]] == [
        "text_layer", "text_layer", "text_layer", "ocr"]
    assert march["text_source"] == "mixed"
    assert march["ocr_engine"] == "tesseract 5.5.2 lang=eng psm=4 dpi=300"
    assert len(march["pages"][3]["words"]) > 100
