import hashlib
import json
from pathlib import Path

import pytest

from steps.fetch_pdfs.process import _load_discovered, _merge_documents, process

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


def test_merge_documents_yml_wins_on_doc_slug_collision():
    documents = [{"doc_slug": "a", "title": "Curated", "url": "https://e.org/a.pdf",
                  "publisher": "Real Body", "public_body_id": 1, "published_date": None}]
    discovered = [{"doc_slug": "a", "title": "Discovered", "url": "https://e.org/discovered.pdf",
                   "department": "Dept X", "publisher": None, "public_body_id": None,
                   "published_date": None, "source_method": "apify"}]

    assert _merge_documents(documents, discovered) == documents


def test_merge_documents_appends_a_find_plan_pdfs_only_record_unchanged():
    documents = [{"doc_slug": "a", "title": "Curated", "url": "https://e.org/a.pdf",
                  "publisher": None, "public_body_id": None, "published_date": None}]
    discovered = [{"doc_slug": "b", "title": "Discovered Plan",
                   "url": "https://e.org/discovered.pdf", "department": "Dept X",
                   "publisher": None, "public_body_id": None, "published_date": None,
                   "source_method": "apify"}]

    assert _merge_documents(documents, discovered) == documents + discovered


def test_a_merged_discovered_record_reaches_process_unchanged(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(FIXTURE_PDF.read_bytes()))
    writer = make_writer("fetch_pdfs")
    discovered_doc = {"doc_slug": "discovered-doc", "title": "Discovered Plan",
                       "url": "https://example.org/fixture.pdf", "department": "Dept X",
                       "publisher": None, "public_body_id": None, "published_date": None,
                       "source_method": "apify"}

    process(_merge_documents([], [discovered_doc]), tmp_path, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert record["doc_slug"] == "discovered-doc"
    assert record["public_body_id"] is None


def test_publisher_falls_back_to_department_when_publisher_is_null(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(FIXTURE_PDF.read_bytes()))
    writer = make_writer("fetch_pdfs")
    discovered_doc = {"doc_slug": "discovered-doc", "title": "Discovered Plan",
                       "url": "https://example.org/fixture.pdf", "department": "Dept X",
                       "publisher": None, "public_body_id": None, "published_date": None,
                       "source_method": "apify"}

    process(_merge_documents([], [discovered_doc]), tmp_path, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert record["publisher"] == "Dept X"


def test_explicit_publisher_wins_over_department(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.fetch_pdfs.process.download",
                        lambda url, dest: dest.write_bytes(FIXTURE_PDF.read_bytes()))
    writer = make_writer("fetch_pdfs")
    curated_doc = {"doc_slug": "curated-doc", "title": "Curated Plan",
                   "url": "https://example.org/fixture.pdf", "department": "Dept X",
                   "publisher": "Real Body", "public_body_id": 1, "published_date": None}

    process(_merge_documents([curated_doc], []), tmp_path, writer)
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


def test_load_discovered_returns_empty_list_when_input_file_is_missing(tmp_path):
    assert _load_discovered(tmp_path / "does-not-exist.json") == []


def test_load_discovered_returns_empty_list_on_malformed_json(tmp_path):
    input_path = tmp_path / "output.json"
    input_path.write_text("not valid json")

    assert _load_discovered(input_path) == []


def test_missing_find_plan_pdfs_output_degrades_to_documents_yml_only(tmp_path):
    documents = [{"doc_slug": "a", "title": "Curated", "url": "https://e.org/a.pdf",
                  "publisher": None, "public_body_id": None, "published_date": None}]
    discovered = _load_discovered(tmp_path / "does-not-exist.json")

    assert discovered == []
    assert _merge_documents(documents, discovered) == documents
