# foi_pipeline/tests/test_merge_page_splits.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from steps.transform_disclosure_files.process import _merge_page_splits


def test_no_split_single_page():
    """Single page — rows returned unchanged, zero stats."""
    pages = [[["H1", "H2"], ["A", "B"], ["C", "D"]]]
    rows, stats = _merge_page_splits(pages)
    assert rows == [["H1", "H2"], ["A", "B"], ["C", "D"]]
    assert stats == {"page_split_merges": 0, "header_rows_stripped": 0}


def test_no_split_multi_page_clean():
    """Multi-page doc where every first row of each page has a non-null anchor — no merges."""
    page1 = [["H1", "H2", "H3"], ["A", "B", "C"]]
    page2 = [["D", "E", "F"]]          # first cell non-null → not a continuation
    page3 = [["G", "H", "I"]]
    rows, stats = _merge_page_splits([page1, page2, page3])
    assert rows == [
        ["H1", "H2", "H3"],
        ["A", "B", "C"],
        ["D", "E", "F"],
        ["G", "H", "I"],
    ]
    assert stats == {"page_split_merges": 0, "header_rows_stripped": 0}


def test_split_no_repeated_header():
    """Case 2: continuation row at top of page 2, null-heavy — merged with previous row."""
    page1 = [["H1", "H2", "H3"], ["A", "B", "C"], ["D", None, None]]
    page2 = [[None, "E", None], ["F", "G", "H"]]
    # [None, "E", None]: 2/3 = 0.667 nulls > 0.5 → continuation
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        ["H1", "H2", "H3"],
        ["A", "B", "C"],
        ["D", "E", None],
        ["F", "G", "H"],
    ]
    assert stats["page_split_merges"] == 1
    assert stats["header_rows_stripped"] == 0


def test_split_with_repeated_header():
    """Case 1: page-1 header block repeated at top of page 2, then continuation — header stripped, row merged."""
    header = ["H1", "H2", "H3"]
    page1 = [header, ["A", "B", "C"], ["D", None, None]]
    page2 = [header, [None, "E", None], ["F", "G", "H"]]
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        ["H1", "H2", "H3"],
        ["A", "B", "C"],
        ["D", "E", None],
        ["F", "G", "H"],
    ]
    assert stats["header_rows_stripped"] == 1
    assert stats["page_split_merges"] == 1


def test_split_with_multi_row_repeated_header():
    """Header is 3 rows, all repeated at top of page 2 — all stripped, continuation merged."""
    h1 = ["Col A", "Col B"]
    h2 = ["(unit)", "(unit)"]
    h3 = ["---", "---"]
    page1 = [h1, h2, h3, ["A", "B"], ["C", None]]
    page2 = [h1, h2, h3, [None, "D"], ["E", "F"]]
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        ["Col A", "Col B"],
        ["(unit)", "(unit)"],
        ["---", "---"],
        ["A", "B"],
        ["C", "D"],
        ["E", "F"],
    ]
    assert stats["header_rows_stripped"] == 3
    assert stats["page_split_merges"] == 1


def test_split_across_multiple_boundaries():
    """3-page doc with splits at both boundaries — both merged correctly."""
    header = ["H1", "H2"]
    page1 = [header, ["A", None]]
    page2 = [header, [None, "B"], ["C", None]]
    page3 = [header, [None, "D"], ["E", "F"]]
    rows, stats = _merge_page_splits([page1, page2, page3])
    assert rows == [
        ["H1", "H2"],
        ["A", "B"],
        ["C", "D"],
        ["E", "F"],
    ]
    assert stats["header_rows_stripped"] == 2
    assert stats["page_split_merges"] == 2


def test_continuation_not_null_heavy():
    """First row of page 2 has only 2/5 = 40% nulls — not a continuation, left as-is."""
    page1 = [["H1", "H2", "H3", "H4", "H5"], ["A", "B", "C", None, None]]
    page2 = [["D", "E", "F", None, None], ["G", "H", "I", "J", "K"]]
    # 2/5 = 0.4 — NOT > 0.5 → no merge
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        ["H1", "H2", "H3", "H4", "H5"],
        ["A", "B", "C", None, None],
        ["D", "E", "F", None, None],
        ["G", "H", "I", "J", "K"],
    ]
    assert stats["page_split_merges"] == 0
    assert stats["header_rows_stripped"] == 0


def test_empty_page():
    """An empty page (no rows) is handled gracefully without crashing."""
    page1 = [["H1", "H2"], ["A", "B"]]
    page2 = []
    page3 = [["C", "D"]]
    rows, stats = _merge_page_splits([page1, page2, page3])
    assert rows == [["H1", "H2"], ["A", "B"], ["C", "D"]]
    assert stats["page_split_merges"] == 0
    assert stats["header_rows_stripped"] == 0


def test_whitespace_normalisation():
    """Header rows with differing internal whitespace are treated as equal by normalisation."""
    # page1 header has double space; page2 repeats with single space — should still be stripped
    page1 = [["Column  One", "Column Two"], ["A", "B"]]
    page2 = [["Column One", "Column  Two"], [None, "C"], ["D", "E"]]
    # Header stripped (normalised match), then [None, "C"] has 0.5 nulls but ["A", "B"] has 0 nulls
    # → previous row not null-heavy enough → no merge despite continuation row meeting threshold
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        ["Column  One", "Column Two"],
        ["A", "B"],
        [None, "C"],
        ["D", "E"],
    ]
    assert stats["header_rows_stripped"] == 1
    assert stats["page_split_merges"] == 0


def test_metadata_counts():
    """Stats dict accurately counts merges and stripped header rows across multiple boundaries."""
    header = ["H1", "H2"]
    page1 = [header, ["A", None]]
    page2 = [header, [None, "B"], ["C", None]]
    page3 = [header, [None, "D"], ["E", "F"]]
    rows, stats = _merge_page_splits([page1, page2, page3])
    assert stats["page_split_merges"] == 2
    assert stats["header_rows_stripped"] == 2
    # Verify rows too, to ensure counts reflect actual merges
    assert rows == [["H1", "H2"], ["A", "B"], ["C", "D"], ["E", "F"]]


def test_fingerprint_skips_leading_title_rows_on_page1():
    """Meath case: page 1 has 2 title rows before the repeating header block;
    page 2 starts directly with the header (no titles). A naive
    first-K-rows-of-page-1 fingerprint never matches anything because
    page2's row 0 is page1's row 2. The fingerprint must be located by
    aligning page 2's start against page 1, not assumed to start at row 0."""
    title1 = [None, None, "Summary of Non-Personal Requests Submitted", None]
    title2 = [None, None, None, "Freedom of Information Requests (non-personal)"]
    header = ["Reference", "Date", "Category", "Summary"]
    page1 = [title1, title2, header, ["FOI/1", "01/01/2020", "Individual", "desc"]]
    page2 = [header, ["FOI/2", "02/01/2020", "Individual", "desc2"]]
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        title1,
        title2,
        header,
        ["FOI/1", "01/01/2020", "Individual", "desc"],
        ["FOI/2", "02/01/2020", "Individual", "desc2"],
    ]
    assert stats["header_rows_stripped"] == 1
    assert stats["page_split_merges"] == 0


def test_fingerprint_skips_leading_title_rows_multi_row_header():
    """Same as above but the repeating block is multiple rows (closer to
    Meath's real 6-row staggered header) — all of them must be located and
    stripped, not just the first row of the block."""
    title = [None, None, "Some Title Row", None]
    h1 = ["Reference", None, None, None]
    h2 = [None, "Date of", None, None]
    h3 = [None, "Receipt", "Category", "Summary"]
    page1 = [title, h1, h2, h3, ["FOI/1", "01/01/2020", "Individual", "desc"]]
    page2 = [h1, h2, h3, ["FOI/2", "02/01/2020", "Individual", "desc2"]]
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [
        title,
        h1,
        h2,
        h3,
        ["FOI/1", "01/01/2020", "Individual", "desc"],
        ["FOI/2", "02/01/2020", "Individual", "desc2"],
    ]
    assert stats["header_rows_stripped"] == 3


def test_fingerprint_no_overlap_falls_back_to_page1_prefix():
    """If page 2's first row never appears anywhere in page 1's prefix,
    preserve today's behavior: fingerprint defaults to the raw first-K
    rows of page 1 (so existing non-Meath-shaped docs are unaffected)."""
    page1 = [["H1", "H2"], ["A", "B"]]
    page2 = [["X", "Y"], ["C", "D"]]
    rows, stats = _merge_page_splits([page1, page2])
    assert rows == [["H1", "H2"], ["A", "B"], ["X", "Y"], ["C", "D"]]
    assert stats["header_rows_stripped"] == 0
