"""Tests for the annotation helper (`eval/annotate.py`).

Only the pure text-layer parsing is tested here: no PDF is opened. The
end-to-end run against a real document is a manual step (it writes images to
the gitignored scratch directory).
"""
from steps.detect_structure.eval import annotate


def _layout(number, width, lines, height=842.0):
    return {"number": number, "width": width, "height": height,
            "lines": [{"text": text, "x0": x0, "x1": x0 + 5.0 * len(text), "y0": y0}
                      for text, x0, y0 in lines]}


def _toc_pages():
    page_three = _layout(3, 595.0, [
        ("Transport Infrastructure Ireland", 35.4, 21.6),
        ("Table of Contents", 36.0, 65.9),
        ("Executive Summary", 36.0, 99.1), ("v", 552.5, 99.1),
        ("5 Introduction", 36.0, 122.0), ("1", 552.2, 122.0),
        ("5.1 Purpose of National Roads 2040", 47.3, 144.9), ("1", 552.2, 144.9),
        ("2 Policy Context", 36.0, 167.8), ("4", 552.2, 167.8),
        ("3 Long Term Strategic Issues", 36.0, 190.7),
        ("for National Roads", 46.0, 205.7), ("11", 545.0, 205.7),
    ])
    page_four = _layout(4, 595.0, [
        ("Transport Infrastructure Ireland", 35.4, 21.6),
        ("4 NR2040 Vision and Key Objectives", 36.0, 40.0), ("23", 545.0, 40.0),
        ("5 National Roads Investment Priorities", 36.0, 62.0), ("25", 545.0, 62.0),
        ("6 Implementation", 36.0, 84.0), ("37", 545.0, 84.0),
    ])
    return [page_three, page_four]


def test_top_level_entries_are_transcribed_and_wrapped_titles_joined():
    entries = annotate.parse_entries(_toc_pages())

    assert entries == [
        {"title": "Executive Summary", "printed_page": "v"},
        {"title": "5 Introduction", "printed_page": "1"},
        {"title": "2 Policy Context", "printed_page": "4"},
        {"title": "3 Long Term Strategic Issues for National Roads", "printed_page": "11"},
        {"title": "4 NR2040 Vision and Key Objectives", "printed_page": "23"},
        {"title": "5 National Roads Investment Priorities", "printed_page": "25"},
        {"title": "6 Implementation", "printed_page": "37"},
    ]


def test_running_header_and_page_heading_are_not_entries():
    titles = [entry["title"] for entry in annotate.parse_entries(_toc_pages())]

    assert "Transport Infrastructure Ireland" not in titles
    assert "Table of Contents" not in titles


def test_contents_pages_are_found_and_bounded():
    pages = _toc_pages()
    pages.append(_layout(5, 595.0, [("List of Figures", 36.0, 40.0)]))

    assert annotate.find_toc_pages(pages) == [3, 4]


def test_find_start_page_prefers_the_heading_and_keeps_monotonic():
    body = [
        _layout(5, 595.0, [("Executive Summary", 36.0, 40.0),
                           ("Introduction", 36.0, 80.0)]),
        _layout(11, 595.0, [("1 Introduction", 36.0, 40.0),
                            ("Body text.", 36.0, 80.0)]),
        _layout(21, 595.0, [("3 Long Term Strategic Issues", 36.0, 40.0),
                            ("for National Roads", 46.0, 60.0)]),
        _layout(30, 595.0, [("2.4 National Sustainable Mobility Policy is described here.", 36.0, 40.0)]),
    ]

    assert annotate.find_start_page(body, "Introduction", after_page=4, min_page=1) == 5
    assert annotate.find_start_page(body, "Introduction", after_page=4, min_page=6) == 11
    assert annotate.find_start_page(body, "Long Term Strategic Issues for National Roads",
                                    after_page=4, min_page=6) == 21
    # A prose mention is not a heading line.
    assert annotate.find_start_page(body, "National Sustainable Mobility Policy",
                                    after_page=4) is None
