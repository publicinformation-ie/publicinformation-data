import hashlib
import json
from pathlib import Path

import pytest

from steps.fetch_pdfs.process import process

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "fixture.pdf"


def _doc(**overrides):
    record = {"doc_slug": "fixture-doc", "title": "Fixture Transport Strategy",
              "url": "https://example.org/fixture.pdf", "publisher": "Test Authority",
              "public_body_id": None, "published_date": None}
    record.update(overrides)
    return record


def test_process_writes_a_record_and_caches_the_pdf(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(FIXTURE_PDF.read_bytes()))
    writer = make_writer("fetch_pdfs")

    process([_doc()], tmp_path, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert record["doc_slug"] == "fixture-doc"
    assert record["page_count"] == 4
    assert record["encrypted"] is False
    assert record["source_sha256"] == hashlib.sha256(FIXTURE_PDF.read_bytes()).hexdigest()
    assert (tmp_path / record["pdf_path"]).exists()


def test_process_logs_an_error_and_skips_on_fetch_failure(tmp_path, make_writer, monkeypatch):
    def boom(url, dest):
        raise RuntimeError("HTTP 503")
    monkeypatch.setattr("steps.fetch_pdfs.process.download", boom)
    writer = make_writer("fetch_pdfs")

    process([_doc()], tmp_path, writer)
    writer.finalize()

    assert json.loads((tmp_path / "output.json").read_text())["results"] == []
    (error,) = json.loads((tmp_path / "errors.json").read_text())
    assert error["error_type"] == "FetchFailed"
    assert error["context"]["doc_slug"] == "fixture-doc"


def test_process_logs_an_error_and_skips_a_non_pdf_payload(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(b"<html>not a pdf</html>"))
    writer = make_writer("fetch_pdfs")

    process([_doc()], tmp_path, writer)
    writer.finalize()

    assert json.loads((tmp_path / "output.json").read_text())["results"] == []
    (error,) = json.loads((tmp_path / "errors.json").read_text())
    assert error["error_type"] == "NotAPdf"


def test_one_failing_document_does_not_prevent_the_others(tmp_path, make_writer, monkeypatch):
    def selective(url, dest):
        if "bad" in url:
            raise RuntimeError("HTTP 503")
        dest.write_bytes(FIXTURE_PDF.read_bytes())
    monkeypatch.setattr("steps.fetch_pdfs.process.download", selective)
    writer = make_writer("fetch_pdfs")

    process([_doc(doc_slug="bad-doc", url="https://example.org/bad.pdf"), _doc()],
            tmp_path, writer)
    writer.finalize()

    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert [r["doc_slug"] for r in results] == ["fixture-doc"]
    assert len(json.loads((tmp_path / "errors.json").read_text())) == 1
