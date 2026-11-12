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


def _doc(slug="rep", url="https://example.org/a.xlsx"):
    return {"doc_slug": slug, "status_annex": {"url": url, "format": "xlsx"}}


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
    _serve(monkeypatch, {"https://example.org/a.xlsx": _xlsx_bytes})
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
    out, errs = _run(tmp_path, make_writer, [_doc()])
    assert out == []
    assert errs[0]["error_type"] == "AnnexUnreadable"


def test_unreachable_does_not_affect_other_documents(tmp_path, make_writer, monkeypatch):
    def boom():
        raise RuntimeError("HTTP 503")
    _serve(monkeypatch, {"https://example.org/a.xlsx": boom,
                         "https://example.org/b.xlsx": _xlsx_bytes})
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
        return _xlsx_bytes() if state["ok"] else b"%PDF-"

    def b():
        calls.append("b")
        return _xlsx_bytes()

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
    _serve(monkeypatch, {"https://example.org/a.xlsx": _xlsx_bytes,
                         "https://example.org/a2.xlsx": _xlsx_bytes})
    _run(tmp_path, make_writer, [_doc("a", "https://example.org/a.xlsx")])
    out, _ = _run(tmp_path, make_writer, [_doc("a", "https://example.org/a2.xlsx")], force=False)
    assert out[0]["status_annex"]["url"] == "https://example.org/a2.xlsx"
    out, _ = _run(tmp_path, make_writer, [{"doc_slug": "a"}], force=False)
    assert out == []


def test_documents_without_an_annex_are_ignored(tmp_path, make_writer, monkeypatch):
    _serve(monkeypatch, {})
    out, errs = _run(tmp_path, make_writer, [{"doc_slug": "plan"}])
    assert out == [] and errs == []
