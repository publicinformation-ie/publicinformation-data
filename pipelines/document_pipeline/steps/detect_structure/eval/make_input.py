#!/usr/bin/env python3
"""Regenerate `input.json` — the frozen, LFS-backed corpus snapshot for the
detect_structure comparison regression test.

The snapshot is a spans-only reduction of `extract_pages/output.json`: each
document's page sidecars are stripped to `{number, width, height, spans}`
(dropping `drawings`, `images` and `tables`, which detection never reads) so
the committed file stays tractable. Regenerate it after the corpus or the
extraction changes:

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

EXTRACT_PAGES_OUTPUT = _DOC_PIPELINE / "steps" / "extract_pages" / "output.json"
OUTPUT = _HERE / "input.json"


def main():
    records = json.loads(EXTRACT_PAGES_OUTPUT.read_text(encoding="utf-8"))["results"]
    documents = []
    for record in records:
        pages = []
        for entry in sorted(record["pages"], key=lambda e: e["number"]):
            path = EXTRACT_PAGES_OUTPUT.parent / entry["file"]
            raw = json.loads(path.read_text(encoding="utf-8"))
            pages.append({
                "number": raw["number"],
                "width": raw.get("width"),
                "height": raw.get("height"),
                "spans": raw.get("spans", []),
            })
        documents.append({
            "doc_slug": record["doc_slug"],
            "page_count": record.get("page_count"),
            "outline": record.get("outline") or [],
            "pages": pages,
        })
    snapshot = {
        "metadata": {"step": "extract_pages", "doc_count": len(documents)},
        "documents": documents,
    }
    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB, "
          f"{len(documents)} documents)")


if __name__ == "__main__":
    main()
