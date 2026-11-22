"""Tests for the detection snapshot builder (`eval/make_input.py`).

The snapshot is what the comparison regression test and the accuracy report
score, so its fingerprints must cover everything detection reads and must be
stable across rebuilds.
"""
import json

import pytest

from steps.detect_structure.eval import make_input
from steps.detect_structure.eval.snapshot import spans_sha256


def _span(text, y0=100.0):
    return {"text": text, "font": "Helvetica", "size": 12.0,
            "bbox": [72.0, y0, 72.0 + 6.0 * len(text), y0 + 12.0],
            "block": 0, "line": 0, "span": 0}


def _write_doc(pages_dir, slug, pages):
    pages_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for number, spans in pages:
        name = f"{slug}/{number:03d}.json"
        path = pages_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"number": number, "width": 595.0, "height": 842.0,
                                    "spans": spans}), encoding="utf-8")
        entries.append({"number": number, "file": name})
    return {"doc_slug": slug, "page_count": len(pages), "outline": [], "pages": entries}


@pytest.fixture
def corpus(tmp_path):
    pages_dir = tmp_path / "pages"
    records = [
        _write_doc(pages_dir, "doc-one", [
            (1, [_span("Cover")]),
            (2, [_span("Introduction"), _span("Body text", y0=140.0)]),
        ]),
        _write_doc(pages_dir, "doc-two", [
            (1, [_span("Contents")]),
            (2, [_span("Chapter One")]),
            (3, [_span("Chapter Two")]),
        ]),
    ]
    records[1]["outline"] = [{"level": 1, "title": "Chapter One", "page": 2, "y": 0.0}]
    shas = {"doc-one": "a" * 64, "doc-two": "b" * 64}
    return records, pages_dir, shas


def test_snapshot_records_fingerprints_for_every_document(corpus):
    records, pages_dir, shas = corpus
    snapshot = make_input.build_snapshot(records, pages_dir, shas)

    assert snapshot["metadata"]["doc_count"] == 2
    by_slug = {d["doc_slug"]: d for d in snapshot["documents"]}
    assert by_slug["doc-one"]["source_sha256"] == "a" * 64
    assert by_slug["doc-two"]["source_sha256"] == "b" * 64
    for doc in snapshot["documents"]:
        assert len(doc["spans_sha256"]) == 64, doc["doc_slug"]

    # Deterministic: a second build over the same sidecars is byte-identical.
    again = make_input.build_snapshot(records, pages_dir, shas)
    assert again == snapshot


def test_fingerprint_covers_spans_and_outline(corpus):
    records, pages_dir, shas = corpus
    snapshot = make_input.build_snapshot(records, pages_dir, shas)
    doc = {d["doc_slug"]: d for d in snapshot["documents"]}["doc-two"]

    # The outline is part of the fingerprint: detection reads it first.
    assert spans_sha256(doc["pages"], doc["outline"]) == doc["spans_sha256"]
    assert spans_sha256(doc["pages"], []) != doc["spans_sha256"]

    # So is a change to any span.
    changed = json.loads(json.dumps(doc["pages"]))
    changed[1]["spans"][0]["text"] = "Chapter 1"
    assert spans_sha256(changed, doc["outline"]) != doc["spans_sha256"]


def test_snapshot_refuses_a_document_without_a_pdf_hash(corpus):
    records, pages_dir, _ = corpus
    with pytest.raises(ValueError, match="doc-two"):
        make_input.build_snapshot(records, pages_dir, {"doc-one": "a" * 64})
