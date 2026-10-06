import pathlib

import pytest

from steps.extract_actions.rss_primary_actions import (
    Word,
    column_bands,
    marker_kind,
    text_in_band,
    find_header_rows,
    extract_primary_actions,
)

_PDF = (pathlib.Path(__file__).resolve().parents[1]
        / "steps/fetch_pdfs/pdfs"
        / "road-safety-strategy-phase-2-action-plan-2025-2027.pdf")

EXPECTED_IDS = [
    "1A", "1B", "1C", "1D", "2A", "2B", "3A", "3B", "4A", "4B", "4C",
    "5A", "5B", "5C", "6A", "6B", "6C", "7A", "7B", "7C", "7D", "8",
    "9A", "9B", "9C", "10", "11", "12A", "12B",
]


def _header():
    return [
        Word("No.", 40, 60, 100, 112),
        Word("Action", 90, 130, 100, 112),
        Word("Lead", 360, 390, 100, 112),
        Word("Support", 440, 480, 100, 112),
        Word("Partner(s)", 440, 500, 113, 125),
    ]


def test_column_bands_cover_the_page_and_split_between_header_centres():
    bands = column_bands(_header())
    assert set(bands) == {"no.", "action", "lead", "support"}
    assert bands["no."][0] <= 40 < bands["no."][1]
    assert bands["action"][0] < 110 < bands["action"][1]
    assert bands["lead"][0] < 375 < bands["lead"][1]
    # bands are contiguous, ascending
    lo = [bands[k][0] for k in ("no.", "action", "lead", "support")]
    assert lo == sorted(lo)


def test_marker_kind_reads_a_parent_number_in_the_no_band():
    bands = column_bands(_header())
    assert marker_kind(Word("7", 42, 52, 200, 212), bands) == ("parent", "7")
    assert marker_kind(Word("12", 42, 58, 200, 212), bands) == ("parent", "12")


def test_marker_kind_reads_a_child_letter_at_the_left_of_the_action_band():
    bands = column_bands(_header())
    assert marker_kind(Word("A.", 92, 104, 220, 232), bands) == ("child", "A")
    assert marker_kind(Word("D", 92, 100, 220, 232), bands) == ("child", "D")


def test_marker_kind_ignores_ordinary_words():
    bands = column_bands(_header())
    assert marker_kind(Word("Expand", 110, 160, 220, 232), bands) is None
    assert marker_kind(Word("2027", 200, 240, 220, 232), bands) is None


def test_text_in_band_orders_by_line_then_x_and_collapses_hyphenation():
    bands = column_bands(_header())
    words = [
        Word("Reduce", 92, 130, 300, 312),
        Word("the", 132, 150, 300, 312),
        Word("enforce-", 92, 140, 313, 325),
        Word("ment", 92, 120, 326, 338),
        Word("RSA", 362, 388, 300, 312),   # in the lead band, excluded
    ]
    got = text_in_band(words, bands["action"], 295, 345)
    assert got == "Reduce the enforcement"


def test_find_header_rows_matches_the_rss_header_line():
    words = [
        Word("No.", 40, 60, 100, 112), Word("Action", 90, 130, 100, 112),
        Word("Lead", 360, 390, 100, 112), Word("Support", 440, 480, 100, 112),
        Word("Partner(s)", 440, 500, 100, 112),
        Word("7", 42, 52, 200, 212),
    ]
    rows = find_header_rows(words)
    assert len(rows) == 1
    assert [w.text for w in rows[0]][:2] == ["No.", "Action"]


@pytest.mark.skipif(not _PDF.exists(), reason="RSS source PDF not fetched")
def test_extract_primary_actions_yields_the_29_tracked_ids():
    actions, errors = extract_primary_actions(str(_PDF), "rss")
    assert [a["action_number"] for a in actions] == EXPECTED_IDS
    assert not [e for e in errors if e["error_type"] == "RssActionTextMissing"]
    assert not [e for e in errors if e["error_type"] == "RssHeaderNotFound"]


@pytest.mark.skipif(not _PDF.exists(), reason="RSS source PDF not fetched")
def test_child_7a_text_and_columns():
    actions, _ = extract_primary_actions(str(_PDF), "rss")
    a = next(a for a in actions if a["action_number"] == "7A")
    assert a["action"].startswith("Enhance the learning to drive programme")
    assert "international best practice" in a["action"]
    assert a["columns"]["No."] == "7"
    assert a["columns"]["Sub"] == "A"
    assert a["columns"]["Lead"] == "RSA"
    assert a["columns"]["Parent"].startswith("Take measures to improve driver behaviour")
    assert a["raw_date"] == ""
    assert a["year"] is None and a["start"] is None


@pytest.mark.skipif(not _PDF.exists(), reason="RSS source PDF not fetched")
def test_standalone_8_has_no_sub_and_no_parent():
    actions, _ = extract_primary_actions(str(_PDF), "rss")
    a = next(a for a in actions if a["action_number"] == "8")
    assert a["action"].startswith("Use enhanced Garda access")
    assert a["columns"]["No."] == "8"
    assert "Sub" not in a["columns"]
    assert "Parent" not in a["columns"]
    assert a["columns"]["Lead"] == "AGS"


@pytest.mark.skipif(not _PDF.exists(), reason="RSS source PDF not fetched")
def test_child_7b_support_partners_recovered():
    actions, _ = extract_primary_actions(str(_PDF), "rss")
    a = next(a for a in actions if a["action_number"] == "7B")
    assert a["columns"]["Lead"] == "DOT"
    assert a["columns"]["Support Partner(s)"] == "RSA"
