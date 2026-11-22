"""Tests for the chapter-accuracy metrics (`eval/metrics.py`)."""
import pytest

from steps.detect_structure.eval import metrics
from steps.detect_structure.process import Node


def _gold(*pairs):
    return [{"title": title, "printed_page": str(page), "pdf_page": page}
            for title, page in pairs]


def _pred(*pairs):
    return [{"title": title, "slug": title.lower().replace(" ", "-"), "page": page}
            for title, page in pairs]


# --------------------------------------------------------------------------
# Predicted chapters
# --------------------------------------------------------------------------

def test_orphaned_section_counts_as_a_chapter():
    nodes = [
        Node(level=1, number="1", title="Chapter", slug="1-chapter",
             start_page=2, start_y=10.0, parent=None),
        Node(level=2, number="1.1", title="Section", slug="1-1-section",
             start_page=3, start_y=10.0, parent="1-chapter"),
        Node(level=2, number="1.2", title="Orphan", slug="1-2-orphan",
             start_page=4, start_y=10.0, parent="missing-parent"),
    ]

    chapters = metrics.predicted_chapters(nodes)

    assert [c["title"] for c in chapters] == ["Chapter", "Orphan"]
    assert chapters[1]["page"] == 4


def test_nested_section_with_a_real_parent_is_not_a_chapter():
    nodes = [
        Node(level=1, number="1", title="Chapter", slug="1-chapter",
             start_page=2, start_y=10.0, parent=None),
        Node(level=2, number="1.1", title="Section", slug="1-1-section",
             start_page=3, start_y=10.0, parent="1-chapter"),
    ]

    assert [c["title"] for c in metrics.predicted_chapters(nodes)] == ["Chapter"]


# --------------------------------------------------------------------------
# Boundary matching
# --------------------------------------------------------------------------

def test_two_chapters_on_one_page_pair_in_document_order():
    gold = _gold(("Alpha", 5), ("Beta", 5))
    predicted = _pred(("Alpha", 5), ("Beta", 5))

    assert metrics.align(gold, predicted, tolerance=0) == [(0, 0), (1, 1)]


def test_off_by_one_is_tolerant_but_not_exact():
    gold = _gold(("Chapter", 20))
    predicted = _pred(("Chapter", 21))

    assert metrics.align(gold, predicted, tolerance=0) == []
    assert metrics.align(gold, predicted, tolerance=1) == [(0, 0)]


def test_matching_is_deterministic_and_keeps_order():
    gold = _gold(("A", 10), ("B", 20), ("C", 30))
    predicted = _pred(("B", 20), ("A", 10), ("C", 30))

    first = metrics.align(gold, predicted, tolerance=1)
    assert first == metrics.align(gold, predicted, tolerance=1)
    # Order is preserved even though the other list reorders two chapters: at
    # most two of the three can pair, and the pairs keep increasing pages.
    assert first == [(1, 0), (2, 2)]
    pages = [(gold[i]["pdf_page"], predicted[j]["page"]) for i, j in first]
    assert pages == sorted(pages)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def test_over_split_document_scores_recall_one_precision_nine_over_fourteen():
    gold = _gold(*[(f"Chapter {i}", i * 10) for i in range(1, 10)])
    predicted = _pred(*[(f"Chapter {i}", i * 10) for i in range(1, 10)],
                      *[(f"Extra {i}", i * 10 + 5) for i in range(1, 6)])
    result = metrics.score(gold, predicted, page_count=100)

    assert result["exact"]["matched"] == 9
    assert result["exact"]["recall"] == 1.0
    assert result["exact"]["precision"] == pytest.approx(9 / 14)
    assert result["fully_correct"] is False


def test_swallowed_pages_count_as_wrongly_attributed():
    # One detected chapter starts on the first real chapter's page and runs on
    # over ten gold chapters whose starts were not detected.
    gold = _gold(*[(f"Chapter {i}", i * 10) for i in range(1, 12)])
    predicted = _pred(("Chapter 1", 10))
    result = metrics.score(gold, predicted, page_count=120)

    # Pages 1-9 are front matter on both sides and pages 10-19 belong to the
    # one matched chapter. Every page from 20 on belongs to a gold chapter the
    # predicted chapter is not matched to.
    assert result["pages_correct"] == 19
    assert result["page_accuracy"] == pytest.approx(19 / 120)
    assert result["exact"]["matched"] == 1


def test_fully_correct_document():
    gold = _gold(("Introduction", 5), ("Findings", 12), ("Recommendations", 30))
    predicted = _pred(("Introduction", 5), ("Findings", 12), ("Recommendations", 30))
    result = metrics.score(gold, predicted, page_count=40)

    assert result["fully_correct"] is True
    assert result["page_accuracy"] == 1.0
    assert result["title_accuracy"] == 1.0
    assert result["exact"]["f1"] == 1.0


def test_titles_are_compared_after_normalisation():
    gold = _gold(("Long Term Strategic Issues", 10))
    predicted = _pred(("3  Long Term Strategic Issues.", 10))
    result = metrics.score(gold, predicted, page_count=12)

    assert result["matched_pairs"] == 1
    assert result["titles_correct"] == 1
    assert result["fully_correct"] is True


def test_wrong_title_is_not_fully_correct():
    gold = _gold(("Introduction", 10))
    predicted = _pred(("Executive Summary", 10))
    result = metrics.score(gold, predicted, page_count=12)

    assert result["matched_pairs"] == 1
    assert result["titles_correct"] == 0
    assert result["fully_correct"] is False


def test_front_matter_is_a_chapter_on_both_sides():
    # The document starts on page 4; pages 1-3 are front matter, correct only
    # when neither side places a chapter there.
    gold = _gold(("Introduction", 4))
    predicted = _pred(("Introduction", 4))
    assert metrics.score(gold, predicted, page_count=6)["page_accuracy"] == 1.0

    late = _pred(("Introduction", 5))
    result = metrics.score(gold, late, page_count=6)
    # Page 4 now belongs to front matter in the prediction, not to the chapter.
    assert result["page_accuracy"] == pytest.approx(3 / 6)


# --------------------------------------------------------------------------
# Corpus summary
# --------------------------------------------------------------------------

def test_one_large_document_does_not_dominate_the_macro_average():
    big_gold = _gold(*[(f"Chapter {i}", i) for i in range(1, 40)])
    big_pred = _pred(*[(f"Chapter {i}", i) for i in range(1, 40)])
    big = metrics.score(big_gold, big_pred, page_count=1107)
    assert big["page_accuracy"] == 1.0

    small_gold = _gold(("Introduction", 2))
    small_pred = _pred(("Wrong", 3))
    small = metrics.score(small_gold, small_pred, page_count=10)
    assert small["page_accuracy"] < 1.0

    summary = metrics.summarise([big, small])

    assert summary["macro"]["page_accuracy"] == pytest.approx(
        (big["page_accuracy"] + small["page_accuracy"]) / 2)
    assert summary["micro"]["page_accuracy"] == pytest.approx(
        (big["pages_correct"] + small["pages_correct"]) / 1117)
    assert summary["macro"]["page_accuracy"] != summary["micro"]["page_accuracy"]


def test_summary_counts_fully_correct_documents():
    good = metrics.score(_gold(("One", 2)), _pred(("One", 2)), page_count=3)
    bad = metrics.score(_gold(("One", 2)), _pred(("Two", 3)), page_count=3)

    summary = metrics.summarise([good, bad])

    assert summary["documents"] == 2
    assert summary["fully_correct"] == 1


# --------------------------------------------------------------------------
# Gold-versus-gold
# --------------------------------------------------------------------------

def test_gold_comparison_lists_boundary_and_title_disagreements():
    committed = _gold(("Introduction", 10), ("Findings", 20))
    reannotated = _gold(("Introduction", 10), ("Findings", 21))
    reannotated[0]["title"] = "Introduction and Context"

    result = metrics.score(committed, metrics.gold_as_predicted(reannotated), page_count=25)
    items = metrics.disagreements(committed, metrics.gold_as_predicted(reannotated))

    assert result["exact"]["matched"] == 1
    assert result["tolerant"]["matched"] == 2
    assert any("off by one" in item for item in items)
    assert any("title differs" in item for item in items)
