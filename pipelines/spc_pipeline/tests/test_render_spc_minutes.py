import json
from pathlib import Path

import pytest

from steps.render_spc_minutes.rendering import (
    RenderMismatch,
    check_words,
    render_meeting,
    run,
)

PIPELINE = Path(__file__).resolve().parents[1]
RESOLVE_OUTPUT = PIPELINE / "steps/resolve_attendees/output.json"


def _records():
    return json.loads(RESOLVE_OUTPUT.read_text())["results"]


@pytest.fixture(scope="module")
def rendered():
    if not RESOLVE_OUTPUT.exists():
        pytest.skip("resolved meetings are a git-ignored cache")
    results, errors = run({"results": _records()})
    assert errors == []
    return {r["meeting_id"]: r for r in results}


def test_furniture_is_removed_and_counted(rendered):
    for record in rendered.values():
        stats = record["furniture_removed"]
        assert stats["page_numbers"] == record["page_count"]
        assert stats["total"] == (record["page_count"] * 4)
        texts = {entry["text"]: entry["count"] for entry in stats["by_text"]}
        header = "Miontuairiscí/Meeting Minutes"
        assert texts[header] == record["page_count"]
        footer = next(t for t in texts if "Transportation Section" in t)
        assert texts[footer] == record["page_count"]
        assert "Miontuariscí/Meeting Minutes" not in record["markdown"]
        assert "Page 1 of" not in record["markdown"]


def test_item_headings_and_anchors(rendered):
    feb = rendered["meath/transportation-urban-regeneration/2026-02-19"]
    assert "## 5.0 Work Programme 2026 {#item-5-0}" in feb["markdown"]
    assert [item["item_key"] for item in feb["items"]][0] == "item-1-0"
    assert feb["items"][0]["is_minutes_approval"] is True


def test_item_numbers_include_zero_zero(rendered):
    may25 = rendered["meath/transportation-urban-regeneration/2025-05-27"]
    assert "0.0" in [item["number"] for item in may25["items"]]


def test_bullets_become_list_items(rendered):
    feb = rendered["meath/transportation-urban-regeneration/2026-02-19"]
    assert "- What is a DZ in relation to the Climate Action Plan (CAP)" in feb["markdown"]
    assert "•" not in feb["markdown"]


def test_aob_section_becomes_a_heading(rendered):
    nov = rendered["meath/transportation-urban-regeneration/2025-11-20"]
    assert "## AOB {#aob" in nov["markdown"]


def test_markup_characters_are_escaped(rendered):
    for record in rendered.values():
        # No unescaped HTML tag can appear.
        assert not __import__("re").search(r"(?<!\\)<[A-Za-z/]", record["markdown"])
        # Every "<" from the source is escaped.
        assert "\\<" in record["markdown"] or "<" not in record["markdown"]


def test_every_meeting_passes_the_word_check(rendered):
    assert len(rendered) == 6
    assert all(record["word_check"] == "passed" for record in rendered.values())


def test_word_check_rejects_a_dropped_word():
    with pytest.raises(RenderMismatch, match="source has 2 words, rendered has 1"):
        check_words(["keep", "this"], ["keep"])


def test_word_check_rejects_an_inserted_word():
    with pytest.raises(RenderMismatch, match="word count differs at position 1"):
        check_words(["keep"], ["keep", "extra"])


def test_word_check_rejects_a_swapped_word_and_names_the_position():
    with pytest.raises(RenderMismatch, match="word 1: source 'second'"):
        check_words(["first", "second"], ["first", "swapped"])


def test_attendance_block_keeps_printed_names(rendered):
    feb = rendered["meath/transportation-urban-regeneration/2026-02-19"]
    assert "### Councillors" in feb["markdown"]
    assert "- Cllr Mike Bray (MB) Chair" in feb["markdown"]
    assert "- Mr. Dave Anderson (DA) PPN Rep" in feb["markdown"]


def test_markdown_matches_the_committed_snapshot(rendered):
    import hashlib

    snapshot = json.loads((Path(__file__).parent / "fixtures/render_sha256.json").read_text())
    assert set(rendered) == set(snapshot)
    for meeting_id, record in rendered.items():
        digest = hashlib.sha256(record["markdown"].encode("utf-8")).hexdigest()
        assert digest == snapshot[meeting_id], meeting_id


def test_withheld_attendance_is_visible_but_minutes_still_render(rendered):
    record = dict(_records()[0])
    record["attendance_published"] = False
    record["printed_attendance"] = _records()[0]["printed_attendance"]
    result = render_meeting(record)
    assert "Attendance is withheld" in result["markdown"]
    assert result["word_check"] == "passed"
