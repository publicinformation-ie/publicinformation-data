#!/usr/bin/env python3
"""Comparison harness for the detect_structure TOC-name strategy.

Runs the legacy cascade and the TOC-name strategy side by side over a frozen
corpus snapshot (`input.json`, see `make_input.py`) and reports, per document,
the detection method, node count, `validate_split` issue count, TOC match
rate, and slug preservation. The regression test (`tests/test_comparison.py`)
asserts these against `expected.json`; refresh that file with
`--refresh-expected` after an intentional change to the strategy.

Run a report from the document_pipeline directory:

    PYTHONPATH=".:../../src" python steps/detect_structure/eval/compare.py
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_DOC_PIPELINE = _HERE.parents[2]
sys.path.insert(0, str(_DOC_PIPELINE))
sys.path.insert(0, str(_DOC_PIPELINE.parent / "src"))

from steps.detect_structure.process import (  # noqa: E402
    _legacy_cascade,
    assign_hierarchy,
    assign_page_ranges,
    body_size,
    dedupe_slugs,
    from_outline,
    from_toc,
    validate_split,
)

INPUT_PATH = _HERE / "input.json"
EXPECTED_PATH = _HERE / "expected.json"


def _assemble(nodes, page_count):
    nodes = dedupe_slugs(sorted(nodes, key=lambda n: (n.start_page, n.start_y)))
    nodes = assign_hierarchy(nodes)
    nodes = assign_page_ranges(nodes, page_count)
    return nodes


def compare_document(doc: dict) -> dict:
    """Compare the legacy and TOC-name strategies for one document snapshot."""
    pages = doc["pages"]
    page_count = int(doc.get("page_count") or len(pages))
    body = body_size(pages)

    # The pre-TOC cascade: outline wins, then numbering/font/flat.
    if doc.get("outline"):
        legacy_nodes, legacy_method = from_outline(doc["outline"]), "outline"
    else:
        legacy_nodes, legacy_method = _legacy_cascade(pages, body)
    legacy_nodes = _assemble(legacy_nodes, page_count)
    legacy_issues = validate_split(legacy_nodes, page_count)
    legacy_slugs = [n.slug for n in legacy_nodes]

    toc_nodes, report = from_toc(pages, body)
    report = report or {}
    if toc_nodes is not None:
        assembled_toc = _assemble(toc_nodes, page_count)
        toc_issues = validate_split(assembled_toc, page_count)
        toc_fired = True
        toc_method = "toc"
        toc_node_count = len(assembled_toc)
        toc_issue_count = len(toc_issues)
        toc_slugs = [n.slug for n in assembled_toc]
    else:
        toc_fired = False
        toc_method = legacy_method
        toc_node_count = None
        toc_issue_count = None
        toc_slugs = []

    return {
        "doc_slug": doc["doc_slug"],
        "legacy_method": legacy_method,
        "legacy_nodes": len(legacy_nodes),
        "legacy_issues": len(legacy_issues),
        "toc_fired": toc_fired,
        "toc_method": toc_method,
        "toc_nodes": toc_node_count,
        "toc_issues": toc_issue_count,
        "entry_count": report.get("entry_count"),
        "matched_count": report.get("matched_count"),
        "match_rate": report.get("match_rate"),
        "slug_preserved": sum(1 for s in toc_slugs if s in set(legacy_slugs)),
        "slug_total": len(legacy_slugs),
    }


def run(documents: list) -> list:
    return [compare_document(doc) for doc in documents]


def main():
    parser = argparse.ArgumentParser(description="Compare legacy vs TOC-name detection")
    parser.add_argument("--refresh-expected", action="store_true",
                        help="rewrite expected.json from the current snapshot")
    args = parser.parse_args()

    snapshot = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    documents = snapshot["documents"]
    results = run(documents)

    if args.refresh_expected:
        EXPECTED_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        print(f"Wrote {EXPECTED_PATH}")
        return

    print(f"{'document':<50} {'legacy':<10} {'toc':<10} "
          f"{'nodes':>12} {'issues':>12} {'rate':>7} {'slugs':>10}")
    for r in results:
        rate = f"{r['match_rate']:.0%}" if r["match_rate"] is not None else "   -"
        nodes = f"{r['legacy_nodes']}->{r['toc_nodes'] if r['toc_fired'] else r['legacy_nodes']}"
        issues = (f"{r['legacy_issues']}->{r['toc_issues']}"
                  if r["toc_fired"] else str(r["legacy_issues"]))
        slugs = (f"{r['slug_preserved']}/{r['slug_total']}"
                 if r["toc_fired"] else "  -")
        print(f"{r['doc_slug']:<50} {r['legacy_method']:<10} {r['toc_method']:<10} "
              f"{nodes:>12} {issues:>12} {rate:>7} {slugs:>10}")


if __name__ == "__main__":
    main()
