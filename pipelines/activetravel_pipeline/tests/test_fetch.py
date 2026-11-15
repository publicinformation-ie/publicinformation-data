"""Document fetch: cold cache, warm cache, and an unreachable document."""
import hashlib
from pathlib import Path

from steps.fetch_grant_documents import process


def _document(available_url: str = "https://example.ie/2026.pdf") -> dict:
    return {"document_id": "nta-active-travel-2026", "year": 2026,
            "url": available_url, "kinds": ["project_table"],
            "publication_page": "https://example.ie/news", "title": "2026"}


def test_cold_cache_downloads_once_and_records_the_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "CACHE_DIR", tmp_path)
    calls = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return b"%PDF-1.4 cold"

    entries, errors = process.collect([_document()], fetcher=fetcher)

    assert calls == ["https://example.ie/2026.pdf"]
    assert errors == []
    entry = entries[0]
    assert entry["source"] == "network"
    assert entry["available"] is True
    assert entry["sha256"] == hashlib.sha256(b"%PDF-1.4 cold").hexdigest()
    assert entry["byte_size"] == len(b"%PDF-1.4 cold")
    assert (tmp_path / Path(entry["cache_file"]).name).read_bytes() == b"%PDF-1.4 cold"


def test_warm_cache_makes_no_request_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "CACHE_DIR", tmp_path)
    first, _ = process.collect([_document()], fetcher=lambda url: b"%PDF-1.4 warm")

    def fetcher(url: str) -> bytes:  # pragma: no cover - must never be called
        raise AssertionError(f"the warm cache should have answered {url}")

    second, errors = process.collect([_document()], fetcher=fetcher)

    assert errors == []
    assert second[0]["source"] == "cache"
    assert second[0]["sha256"] == first[0]["sha256"]


def test_an_unreachable_document_is_reported_and_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "CACHE_DIR", tmp_path)

    def fetcher(url: str) -> bytes:
        raise OSError("connection refused")

    entries, errors = process.collect([_document()], fetcher=fetcher)

    assert entries[0]["available"] is False
    assert entries[0]["sha256"] is None
    assert [e["error_type"] for e in errors] == ["DocumentFetchError"]
    assert errors[0]["context"]["document_id"] == "nta-active-travel-2026"
    assert "connection refused" in errors[0]["context"]["reason"]
    assert list(tmp_path.iterdir()) == []


def test_an_empty_response_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "CACHE_DIR", tmp_path)

    entries, errors = process.collect([_document()], fetcher=lambda url: b"")

    assert entries[0]["available"] is False
    assert [e["error_type"] for e in errors] == ["DocumentFetchError"]
    assert list(tmp_path.iterdir()) == []


def test_only_documents_with_an_extractable_kind_are_extracted(tmp_path, monkeypatch):
    "The 2022 annex is fetched and cached, but never read as project rows."
    from steps.extract_grant_tables import process as extract

    documents = [
        {"document_id": "nta-active-travel-2022", "year": 2022,
         "kinds": ["project_table"], "available": True, "cache_file": "x.pdf"},
        {"document_id": "nta-active-travel-2022-annex-1", "year": 2022,
         "kinds": ["programme_summary"], "available": True, "cache_file": "y.pdf"},
    ]
    seen = []

    def fake_extract(entry):
        seen.append(entry["document_id"])
        return [], [], []

    monkeypatch.setattr(extract, "extract_document", fake_extract)
    output, errors = extract.run({"documents": documents})

    assert seen == ["nta-active-travel-2022"]
    assert output["rows"] == []
    assert errors == []


def test_an_unavailable_document_is_not_extracted():
    from steps.extract_grant_tables import run as extract_run

    documents = [{"document_id": "nta-active-travel-2026", "year": 2026,
                  "kinds": ["project_table"], "available": False, "error": "DocumentFetchError"}]
    output, errors = extract_run({"documents": documents})
    assert output["pages"] == []
    assert errors == []
