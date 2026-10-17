"""Comparison regression tests for the detect_structure TOC-name strategy.

`test_compare_document_reports_both_strategies` exercises the comparison logic
on a hand-written fixture (fast, like the rest of this suite). The corpus test
loads the frozen, LFS-backed snapshot (`steps/detect_structure/eval/input.json`,
see `make_input.py`) and asserts the per-document diagnostics against
`expected.json` so a change to either strategy surfaces as a diff rather than
silently drifting.
"""
import json

import pytest

from steps.detect_structure.eval import compare


def _span(text, size=12.0, font="Helvetica", y0=100.0, x0=72.0, block=0, line=0, index=0):
    return {"text": text, "font": font, "size": size,
            "bbox": [x0, y0, x0 + 6.0 * len(text), y0 + size],
            "block": block, "line": line, "span": index}


def _page(spans, number=1):
    return {"number": number, "width": 595.0, "height": 842.0, "spans": spans}


def test_compare_document_reports_both_strategies():
    toc = _page([
        _span("Contents", size=16.0, y0=40.0, block=0),
        _span("Introduction", size=12.0, y0=80.0, block=1),
        _span("2", size=12.0, y0=80.0, x0=540.0, block=2),
        _span("Conclusions", size=12.0, y0=95.0, block=3),
        _span("3", size=12.0, y0=95.0, x0=540.0, block=4),
    ], number=1)
    intro = _page([_span("Introduction", size=16.0, y0=80.0, block=0),
                   _span("Body text about methods in detail.", size=12.0, y0=120.0, block=1)],
                  number=2)
    concl = _page([_span("Conclusions", size=16.0, y0=80.0, block=0),
                   _span("Final body text.", size=12.0, y0=120.0, block=1)],
                  number=3)
    # Enough filler pages that the headings are not mistaken for running headers
    # (a line must appear on >= 25% of pages).
    filler = [_page([_span(f"Body paragraph number {i}.", size=12.0, y0=100.0, block=0)],
                    number=4 + i) for i in range(6)]

    doc = {
        "doc_slug": "fixture-doc",
        "page_count": 9,
        "outline": [],
        "pages": [toc, intro, concl] + filler,
    }
    result = compare.compare_document(doc)

    assert result["legacy_method"] == "font"
    assert result["toc_fired"] is True
    assert result["toc_method"] == "toc"
    assert result["toc_nodes"] == 2
    assert result["match_rate"] == 1.0
    assert result["entry_count"] == 2
    assert result["matched_count"] == 2


def test_comparison_matches_frozen_expected():
    if not compare.INPUT_PATH.exists():
        pytest.skip("corpus snapshot missing — run steps/detect_structure/eval/make_input.py")
    try:
        snapshot = json.loads(compare.INPUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        pytest.skip("corpus snapshot is an LFS pointer — run `git lfs pull` first")

    expected = json.loads(compare.EXPECTED_PATH.read_text(encoding="utf-8"))
    results = compare.run(snapshot["documents"])

    by_slug = {r["doc_slug"]: r for r in results}
    expected_by_slug = {r["doc_slug"]: r for r in expected}
    assert set(by_slug) == set(expected_by_slug), "document set drifted from expected.json"
    for slug, exp in expected_by_slug.items():
        assert by_slug[slug] == exp, f"comparison regressed for {slug}"
