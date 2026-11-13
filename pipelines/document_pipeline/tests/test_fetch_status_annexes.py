import hashlib
import io
import json
import zipfile

import openpyxl

from steps.fetch_status_annexes.process import process


def _xlsx_bytes():
    wb = openpyxl.Workbook()
    wb.worksheets[0].title = "Q1"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# openpyxl embeds a creation timestamp, so fix one payload per test session.
_FIXED_XLSX = _xlsx_bytes()
_FIXED_SHA = hashlib.sha256(_FIXED_XLSX).hexdigest()


def _fixed_xlsx():
    return _FIXED_XLSX


def _doc(slug="rep", url="https://example.org/a.xlsx", sha256=None):
    return {"doc_slug": slug, "status_annex": {
        "url": url, "format": "xlsx", "sha256": sha256 or _FIXED_SHA}}


def _run(tmp_path, make_writer, docs, force=True):
    writer = make_writer("fetch_status_annexes", force=force)
    process(docs, tmp_path, writer)
    writer.finalize()
    out = json.loads((tmp_path / "output.json").read_text())["results"]
    errs = json.loads((tmp_path / "errors.json").read_text())
    return out, errs


def _serve(monkeypatch, payloads):
    monkeypatch.setattr("steps.fetch_status_annexes.process.download",
                        lambda url, dest: dest.write_bytes(payloads[url]()))


def test_valid_workbook_passes_whatever_the_content_type(tmp_path, make_writer, monkeypatch):
    # download() never sees the content type: a generic one cannot fail it.
    _serve(monkeypatch, {"https://example.org/a.xlsx": _fixed_xlsx})
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert errs == []
    assert out[0]["sheet_names"] == ["Q1"]
    assert (tmp_path / out[0]["annex_path"]).exists()


def test_pdf_payload_is_wrong_format(tmp_path, make_writer, monkeypatch):
    _serve(monkeypatch, {"https://example.org/a.xlsx": lambda: b"%PDF-1.7 ..."})
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert out == []
    assert errs[0]["error_type"] == "AnnexWrongFormat"
    assert "expected xlsx" in errs[0]["error_message"]
    assert "received pdf" in errs[0]["error_message"]


def test_corrupt_zip_is_unreadable(tmp_path, make_writer, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "not a workbook")
    _serve(monkeypatch, {"https://example.org/a.xlsx": buf.getvalue})
    declared = hashlib.sha256(buf.getvalue()).hexdigest()  # checksum is right; the payload is not a workbook
    out, errs = _run(tmp_path, make_writer, [_doc(sha256=declared)])
    assert out == []
    assert errs[0]["error_type"] == "AnnexUnreadable"


def test_unreachable_does_not_affect_other_documents(tmp_path, make_writer, monkeypatch):
    def boom():
        raise RuntimeError("HTTP 503")
    _serve(monkeypatch, {"https://example.org/a.xlsx": boom,
                         "https://example.org/b.xlsx": _fixed_xlsx})
    out, errs = _run(tmp_path, make_writer,
                     [_doc("a", "https://example.org/a.xlsx"),
                      _doc("b", "https://example.org/b.xlsx")])
    assert [r["doc_slug"] for r in out] == ["b"]
    assert [e["error_type"] for e in errs] == ["AnnexUnreachable"]
    assert errs[0]["context"]["doc_slug"] == "a"


def test_failed_document_is_retried_and_good_one_is_not_refetched(tmp_path, make_writer, monkeypatch):
    calls = []
    state = {"ok": False}

    def a():
        calls.append("a")
        return _FIXED_XLSX if state["ok"] else b"%PDF-"

    def b():
        calls.append("b")
        return _FIXED_XLSX

    _serve(monkeypatch, {"https://example.org/a.xlsx": a, "https://example.org/b.xlsx": b})
    docs = [_doc("a", "https://example.org/a.xlsx"), _doc("b", "https://example.org/b.xlsx")]
    out, _ = _run(tmp_path, make_writer, docs)
    assert [r["doc_slug"] for r in out] == ["b"]

    state["ok"] = True
    calls.clear()
    out, errs = _run(tmp_path, make_writer, docs, force=False)
    assert sorted(r["doc_slug"] for r in out) == ["a", "b"]
    assert calls == ["a"]
    assert errs == []


def test_changed_declaration_is_refetched_and_removed_one_dropped(tmp_path, make_writer, monkeypatch):
    _serve(monkeypatch, {"https://example.org/a.xlsx": _fixed_xlsx,
                         "https://example.org/a2.xlsx": _fixed_xlsx})
    _run(tmp_path, make_writer, [_doc("a", "https://example.org/a.xlsx")])
    out, _ = _run(tmp_path, make_writer, [_doc("a", "https://example.org/a2.xlsx")], force=False)
    assert out[0]["status_annex"]["url"] == "https://example.org/a2.xlsx"
    out, _ = _run(tmp_path, make_writer, [{"doc_slug": "a"}], force=False)
    assert out == []


def test_documents_without_an_annex_are_ignored(tmp_path, make_writer, monkeypatch):
    _serve(monkeypatch, {})
    out, errs = _run(tmp_path, make_writer, [{"doc_slug": "plan"}])
    assert out == [] and errs == []


def test_cold_cache_downloads_and_verifies_checksum(tmp_path, make_writer, monkeypatch):
    calls = []
    monkeypatch.setattr("steps.fetch_status_annexes.process.download",
                        lambda url, dest: (calls.append(url), dest.write_bytes(_FIXED_XLSX)))
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert errs == [] and calls == ["https://example.org/a.xlsx"]
    assert out[0]["source_sha256"] == _FIXED_SHA and out[0]["fetched_at"] is not None


def test_warm_cache_with_declared_checksum_makes_no_request(tmp_path, make_writer, monkeypatch):
    (tmp_path / "annexes").mkdir()
    (tmp_path / "annexes" / "rep.xlsx").write_bytes(_FIXED_XLSX)

    def no_network(url, dest):
        raise AssertionError("network request for a verified cached file")
    monkeypatch.setattr("steps.fetch_status_annexes.process.download", no_network)
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert errs == []
    assert out[0]["source_sha256"] == _FIXED_SHA and out[0]["fetched_at"] is None


def test_cached_file_with_wrong_checksum_is_refetched(tmp_path, make_writer, monkeypatch):
    (tmp_path / "annexes").mkdir()
    (tmp_path / "annexes" / "rep.xlsx").write_bytes(b"stale bytes")
    _serve(monkeypatch, {"https://example.org/a.xlsx": _fixed_xlsx})
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert errs == [] and out[0]["source_sha256"] == _FIXED_SHA


def test_checksum_mismatch_is_recorded_and_emits_no_record(tmp_path, make_writer, monkeypatch):
    _serve(monkeypatch, {"https://example.org/a.xlsx": _fixed_xlsx})
    declared = "0" * 64
    out, errs = _run(tmp_path, make_writer, [_doc(sha256=declared)])
    assert out == []
    assert errs[0]["error_type"] == "AnnexChecksumMismatch"
    assert declared in errs[0]["error_message"] and _FIXED_SHA in errs[0]["error_message"]
    assert errs[0]["context"]["doc_slug"] == "rep"
    assert not (tmp_path / "annexes" / "rep.xlsx").exists()


def test_unreachable_uncached_source_is_a_fetch_error_not_a_crash(tmp_path, make_writer, monkeypatch):
    def boom():
        raise RuntimeError("connection refused")
    _serve(monkeypatch, {"https://example.org/a.xlsx": boom})
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert out == [] and errs[0]["error_type"] == "AnnexUnreachable"
