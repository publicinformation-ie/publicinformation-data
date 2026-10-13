import hashlib
import json
from pathlib import Path

import pytest

from steps.fetch_pdfs.process import _doc_metadata, process

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "fixture.pdf"


def _doc(**overrides):
    record = {"doc_slug": "fixture-doc", "title": "Fixture Transport Strategy",
              "url": "https://example.org/fixture.pdf", "publisher": "Test Authority",
              "public_body_id": None, "published_date": None,
              "policy_id": "p", "policy_role": "primary"}
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


def test_doc_metadata_carries_role_and_report_fields():
    meta = _doc_metadata({
        "doc_slug": "a-report", "policy_id": "p", "policy_role": "primary", "title": "A Report", "url": "https://example.ie/b.pdf",
        "role": "report", "reports_on": "a-plan",
        "expected_status_counts": {"Complete": 58},
    })
    assert meta["role"] == "report"
    assert meta["reports_on"] == "a-plan"
    assert meta["expected_status_counts"] == {"Complete": 58}
    assert meta["expected_action_count"] is None


def test_doc_metadata_defaults_role_to_plan_when_absent():
    meta = _doc_metadata({
        "doc_slug": "discovered", "policy_id": "p", "policy_role": "primary", "title": "Discovered", "url": "https://example.ie/c.pdf",
    })
    assert meta["role"] == "plan"
    assert meta["reports_on"] is None


def test_publisher_is_taken_from_the_document(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(FIXTURE_PDF.read_bytes()))
    writer = make_writer("fetch_pdfs")
    curated_doc = {"doc_slug": "curated-doc", "title": "Curated Plan",
                   "url": "https://example.org/fixture.pdf",
                   "publisher": "Real Body", "public_body_id": 1, "published_date": None,
                   "policy_id": "p", "policy_role": "primary"}

    process([curated_doc], tmp_path, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert record["publisher"] == "Real Body"


def test_cache_hit_recomputes_metadata_and_preserves_fetched_at(tmp_path, make_writer, monkeypatch):
    """A cached PDF must not freeze its metadata: the record's curated fields
    (publisher, title, url, ...) are recomputed from `doc` on every run, while
    the download-derived facts (source_sha256, page_count, fetched_at) keep
    the values from the original fetch — so a metadata-only fix propagates on
    a `--force` rerun without re-downloading the PDF."""
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(FIXTURE_PDF.read_bytes()))
    monkeypatch.setattr("steps.fetch_pdfs.process._remote_unchanged", lambda url, dest: True)

    writer1 = make_writer("fetch_pdfs")
    process([_doc(publisher="Old Body")], tmp_path, writer1)
    writer1.finalize()
    (first,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert first["publisher"] == "Old Body"

    writer2 = make_writer("fetch_pdfs")
    process([_doc(publisher="New Body", title="New Title")], tmp_path, writer2)
    writer2.finalize()
    (second,) = json.loads((tmp_path / "output.json").read_text())["results"]

    assert second["publisher"] == "New Body"
    assert second["title"] == "New Title"
    assert second["fetched_at"] == first["fetched_at"]
    assert second["source_sha256"] == first["source_sha256"]
    assert second["page_count"] == first["page_count"]


def test_doc_metadata_carries_policy_fields():
    from steps.fetch_pdfs.process import _doc_metadata
    meta = _doc_metadata({"doc_slug": "a", "title": "A", "url": "https://e.org/a.pdf",
                          "policy_id": "greater-dublin-area-transport-strategy",
                          "policy_role": "primary"})
    assert meta["policy_id"] == "greater-dublin-area-transport-strategy"
    assert meta["policy_role"] == "primary"
