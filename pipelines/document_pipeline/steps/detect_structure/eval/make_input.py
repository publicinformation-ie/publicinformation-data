#!/usr/bin/env python3
"""Regenerate `input.json` — the frozen, LFS-backed corpus snapshot used by the
detect_structure comparison test and by the accuracy report (`score.py`).

The snapshot is a spans-only reduction of `extract_pages/output.json`: each
document's page sidecars are stripped to `{number, width, height, spans}`
(dropping `drawings`, `images` and `tables`, which detection never reads) so
the committed file stays tractable. Each document also records:

* `spans_sha256` — a hash of the spans and outline that detection reads (see
  `snapshot.py`), so `score.py --live` can warn when local output has drifted;
* `source_sha256` — the source PDF's hash from `fetch_pdfs/output.json`, so the
  report can refuse to score a gold file whose PDF no longer matches.

Regenerate it after the corpus or the extraction changes:

    cd pipelines/document_pipeline
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/make_input.py
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_DOC_PIPELINE = _HERE.parents[2]
sys.path.insert(0, str(_DOC_PIPELINE))
sys.path.insert(0, str(_DOC_PIPELINE.parent / "src"))
sys.path.insert(0, str(_HERE))

try:  # imported as a module from the test suite
    from .snapshot import spans_sha256  # noqa: E402
except ImportError:  # run as a script, as the docstring says
    from snapshot import spans_sha256  # noqa: E402

EXTRACT_PAGES_OUTPUT = _DOC_PIPELINE / "steps" / "extract_pages" / "output.json"
FETCH_PDFS_OUTPUT = _DOC_PIPELINE / "steps" / "fetch_pdfs" / "output.json"
OUTPUT = _HERE / "input.json"


def read_source_sha256(path: Path = FETCH_PDFS_OUTPUT) -> dict:
    """`doc_slug` → `source_sha256`, from fetch_pdfs output."""
    if not path.exists():
        raise SystemExit(f"{path} is missing — run the fetch_pdfs step first")
    records = json.loads(path.read_text(encoding="utf-8"))["results"]
    return {record["doc_slug"]: record.get("source_sha256") for record in records}


def build_documents(records: list, pages_base_dir: Path, source_sha_by_slug: dict) -> list:
    """Reduce upstream records (plus their page sidecars) to snapshot documents."""
    documents = []
    for record in records:
        pages = []
        for entry in sorted(record["pages"], key=lambda e: e["number"]):
            path = Path(pages_base_dir) / entry["file"]
            raw = json.loads(path.read_text(encoding="utf-8"))
            pages.append({
                "number": raw["number"],
                "width": raw.get("width"),
                "height": raw.get("height"),
                "spans": raw.get("spans", []),
            })
        slug = record["doc_slug"]
        outline = record.get("outline") or []
        documents.append({
            "doc_slug": slug,
            "page_count": record.get("page_count"),
            "outline": outline,
            "spans_sha256": spans_sha256(pages, outline),
            "source_sha256": source_sha_by_slug.get(slug),
            "pages": pages,
        })
    return documents


def build_snapshot(records: list, pages_base_dir: Path, source_sha_by_slug: dict) -> dict:
    documents = build_documents(records, pages_base_dir, source_sha_by_slug)
    missing = sorted(d["doc_slug"] for d in documents if not d["source_sha256"])
    if missing:
        # Fail closed: a snapshot row without a PDF hash cannot support the
        # gold/PDF mismatch check, so it must not be written silently.
        raise ValueError(
            "fetch_pdfs output has no source_sha256 for: " + ", ".join(missing))
    return {
        "metadata": {"step": "extract_pages", "doc_count": len(documents)},
        "documents": documents,
    }


def main():
    payload = json.loads(EXTRACT_PAGES_OUTPUT.read_text(encoding="utf-8"))
    snapshot = build_snapshot(
        payload["results"],
        EXTRACT_PAGES_OUTPUT.parent,
        read_source_sha256(),
    )
    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB, "
          f"{len(snapshot['documents'])} documents)")


if __name__ == "__main__":
    main()
