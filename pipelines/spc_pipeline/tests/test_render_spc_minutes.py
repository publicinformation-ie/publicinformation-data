from pathlib import Path

import pytest

from steps.render_spc_minutes.rendering import (
    RenderMismatch,
    UnrecognisedFurniture,
    check_words,
    render_meeting,
)

PIPELINE = Path(__file__).resolve().parents[1]
PUBLISHED_MINUTES = PIPELINE.parents[1] / "public/latest/spc-meetings/minutes"


@pytest.fixture(scope="module")
def rendered(rendered_meetings):
    return {r["meeting_id"]: r for r in rendered_meetings}


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
    # Role text printed as a separate fragment is not lost from the minutes.
    assert "- Martin Murray (MM), DOS" in feb["markdown"]


def test_markdown_matches_the_published_snapshot(rendered):
    """The renderer's output is the committed, human-reviewable artifact.

    A render change therefore shows as an ordinary diff in `public/latest/`
    instead of an opaque changed hash.
    """
    for meeting_id, record in rendered.items():
        published = PUBLISHED_MINUTES / f"{meeting_id}.md"
        assert published.exists(), published
        assert record["markdown"].encode("utf-8") == published.read_bytes(), meeting_id


def test_new_council_markdown_matches_the_published_snapshot(rendered_new_meetings):
    for record in rendered_new_meetings:
        published = PUBLISHED_MINUTES / f"{record['meeting_id']}.md"
        assert published.exists(), published
        assert record["markdown"].encode("utf-8") == published.read_bytes(), record["meeting_id"]


def test_withheld_attendance_is_visible_but_minutes_still_render(resolved_meetings):
    record = dict(resolved_meetings[0])
    record["attendance_published"] = False
    record["printed_attendance"] = resolved_meetings[0]["printed_attendance"]
    result = render_meeting(record)
    assert "Attendance is withheld" in result["markdown"]
    assert result["word_check"] == "passed"


# ---------------------------------------------------------------------------
# Synthetic records: these do not need the git-ignored pipeline caches.
# ---------------------------------------------------------------------------

def _w(text, x0, top):
    width = max(5, 5.0 * len(text))
    return {"text": text, "x0": x0, "x1": x0 + width, "top": top,
            "bottom": top + 10}


def _line(text, top):
    words = []
    x = 50.0
    for token in text.split():
        words.append(_w(token, x, top))
        x += 5.0 * len(token) + 2
    return words


def _synthetic_record(*, body_lines, role="DOS", raw="A B, DOS", pages=3,
                      footer="Transportation Section, Meath County Council"):
    """Three pages with running header, page number and footer furniture."""
    page_words = []
    for index in range(pages):
        words = _line("Miontuairiscí/Meeting Minutes", 0)
        if index == 0:
            words += _line("Item", 20)
        words += _line(body_lines, 50)
        words += _line(f"Page {index + 1} of {pages}", 92)
        words += _line(footer, 100)
        page_words.append({"words": words})
    return {
        "meeting_id": "meath/test/2026-01-01",
        "committee_id": "meath/test",
        "committee_name": "Test Committee",
        "public_body_id": 1511,
        "meeting_date": "2026-01-01",
        "date_text": "1st January 2026",
        "venue": "Room",
        "start_time": "2.30 pm",
        "end_time": "3.30 pm",
        "source_url": "https://example.test/minutes.pdf",
        "source_sha256": "abc",
        "page_count": pages,
        "printed_attendance": [{
            "category": "officials",
            "printed_name": "A B",
            "title": None,
            "initials": None,
            "role": role,
            "markers": [],
            "raw": raw,
        }],
        "pages": page_words,
    }


def test_furniture_rule_keeps_a_body_line_that_repeats_on_three_pages():
    record = _synthetic_record(body_lines="Noted.")
    result = render_meeting(record)
    removed = {entry["text"] for entry in result["furniture_removed"]["by_text"]}
    assert "Noted." not in removed
    assert result["markdown"].count("Noted.") == 3


def test_a_two_page_footer_is_still_removed():
    record = _synthetic_record(body_lines="Body text.", pages=2)
    result = render_meeting(record)
    removed = {entry["text"] for entry in result["furniture_removed"]["by_text"]}
    assert "Transportation Section, Meath County Council" in removed
    assert "Miontuairiscí/Meeting Minutes" in removed
    assert "Transportation Section" not in result["markdown"]


def test_a_one_page_document_keeps_its_lower_lines():
    record = _synthetic_record(body_lines="Body text.", pages=1)
    result = render_meeting(record)
    removed = {entry["text"] for entry in result["furniture_removed"]["by_text"]}
    assert removed == set()
    assert "Transportation Section, Meath County Council" in result["markdown"]


def test_an_unrecognised_repeating_edge_line_fails_closed():
    record = _synthetic_record(body_lines="Body text.", pages=3,
                               footer="A sentence that is not page furniture")
    with pytest.raises(UnrecognisedFurniture, match="not page furniture"):
        render_meeting(record)


def test_attendance_role_text_must_be_in_the_printed_text():
    # The role survived parsing but not in the text kept for the verbatim
    # minutes: publishing it would silently drop "DOS".
    record = _synthetic_record(body_lines="Noted.", role="DOS", raw="A B")
    with pytest.raises(RenderMismatch, match="attendance"):
        render_meeting(record)


def test_attendance_role_text_is_rendered_verbatim():
    record = _synthetic_record(body_lines="Noted.", role="DOS", raw="A B, DOS")
    result = render_meeting(record)
    assert "- A B, DOS" in result["markdown"]
    assert result["word_check"] == "passed"


def test_attendance_role_text_may_be_glued_to_a_bracket():
    record = _synthetic_record(body_lines="Noted.", role="Climate Officer",
                               raw="A B (AB)Climate Officer")
    result = render_meeting(record)
    assert "A B (AB)Climate Officer" in result["markdown"]


# ---------------------------------------------------------------------------
# Scanned layouts (Kildare, Westmeath): OCR words, no declared furniture
# ---------------------------------------------------------------------------

def _new(rendered_new_meetings, committee, iso):
    return next(r for r in rendered_new_meetings
                if r["committee_id"].startswith(committee) and r["meeting_date"] == iso)


def test_every_scanned_meeting_passes_the_word_check(rendered_new_meetings):
    assert len(rendered_new_meetings) == 11
    assert all(r["word_check"] == "passed" for r in rendered_new_meetings)


def test_scanned_layouts_remove_no_furniture(rendered_new_meetings):
    for record in rendered_new_meetings:
        assert record["furniture_removed"] == {"total": 0, "page_numbers": 0, "by_text": []}


def test_front_matter_gives_the_text_source_and_ocr_engine(rendered_new_meetings, rendered):
    kildare = _new(rendered_new_meetings, "kildare/", "2025-12-11")
    assert 'text_source: "ocr"\n' in kildare["markdown"]
    assert 'ocr_engine: "tesseract 5.5.2 lang=eng psm=4 dpi=300"\n' in kildare["markdown"]
    mixed = _new(rendered_new_meetings, "westmeath/", "2026-03-06")
    assert 'text_source: "mixed"\n' in mixed["markdown"]
    for record in rendered.values():                       # Meath: text layer, no engine
        assert 'text_source: "text_layer"\n' in record["markdown"]
        assert "ocr_engine" not in record["markdown"]


def test_kildare_item_word_forms_become_headings_with_item_anchors(rendered_new_meetings):
    markdown = _new(rendered_new_meetings, "kildare/", "2025-12-11")["markdown"]
    assert "## Item 2 — Minutes-of the meeting held on 2 October 2025 {#item-2}" in markdown
    assert "## Item 9- Any Other Business {#item-9}" in markdown


def test_westmeath_colon_headings_keep_their_printed_case_and_number_a_repeat(rendered_new_meetings):
    sept = _new(rendered_new_meetings, "westmeath/", "2025-09-19")
    assert "## item 1: Minutes {#item-1}" in sept["markdown"]
    assert "## Item 2: Matters Arising {#item-2}" in sept["markdown"]
    keys = [item["item_key"] for item in sept["items"]]
    assert keys.count("item-3") == 1 and "item-3-2" in keys            # "Item 3" printed twice
    assert sept["items"][0]["is_minutes_approval"] is True


def test_a_misread_heading_stays_in_the_text_not_dropped(rendered_new_meetings):
    mar = _new(rendered_new_meetings, "westmeath/", "2026-03-06")
    assert "Item \\&: Aon Gno Eile" in mar["markdown"]               # OCR read "8" as "&"
    assert "## Item \\&" not in mar["markdown"]


def test_attendance_uses_the_printed_labels_and_new_categories(rendered_new_meetings):
    markdown = _new(rendered_new_meetings, "kildare/", "2025-12-11")["markdown"]
    for heading in ("### Attendees", "### Also present", "### Guests", "### Apologies",
                    "### Not present"):
        assert heading in markdown
    assert "- Councillor Bill Clear" in markdown
    westmeath = _new(rendered_new_meetings, "westmeath/", "2025-11-28") if any(
        r["meeting_date"] == "2025-11-28" for r in rendered_new_meetings) else \
        _new(rendered_new_meetings, "westmeath/", "2025-09-19")
    assert "### External presenters" in westmeath["markdown"]


def test_start_time_with_a_trailing_full_stop_has_no_doubled_full_stop(rendered_new_meetings):
    markdown = _new(rendered_new_meetings, "kildare/", "2025-12-11")["markdown"]
    assert "Naas. 3.30p.m.\n" in markdown and "p.m..\n" not in markdown


def _ocr_word(text, x0, top, line, conf=95.0):
    return {"text": text, "x0": x0, "x1": x0 + 5.0 * len(text), "top": top,
            "bottom": top + 9, "conf": conf, "line": line}


def _ocr_record(page2_lines):
    page1 = [_ocr_word("Item", 80, 100, 0), _ocr_word("1:", 110, 100, 0),
             _ocr_word("Minutes", 130, 100, 0)]
    page2 = []
    for number, text in enumerate(page2_lines):
        x = 80.0
        for token in text.split():
            page2.append(_ocr_word(token, x, 60 + number * 20, number))
            x += 5.0 * len(token) + 3
    return {
        "meeting_id": "westmeath/test/2026-01-01", "committee_id": "westmeath/test",
        "committee_name": "Test", "public_body_id": 1870, "meeting_date": "2026-01-01",
        "date_text": "1 January 2026", "venue": "Room", "start_time": "10am", "end_time": None,
        "source_url": "https://example.test/m.pdf", "source_sha256": "abc",
        "layout": "westmeath-list", "text_source": "ocr", "ocr_engine": "tesseract 5.5.2 x",
        "body_start": {"page": 1, "top": 100.0}, "printed_attendance": [],
        "pages": [{"page": 1, "words": page1, "source": "ocr"},
                  {"page": 2, "words": page2, "source": "ocr"}],
    }


def test_a_stray_token_that_is_not_declared_furniture_is_kept_in_the_body():
    record = _ocr_record([",", "The committee noted the report."])
    result = render_meeting(record)
    assert result["word_check"] == "passed"
    assert ", The committee noted the report." in result["markdown"]


def test_a_lost_ocr_word_fails_the_word_check_as_render_mismatch(monkeypatch):
    from steps.render_spc_minutes import rendering

    real = rendering.render_body
    monkeypatch.setattr(rendering, "render_body",
                        lambda blocks: real(blocks).replace("noted ", "", 1))
    with pytest.raises(RenderMismatch, match="word"):
        render_meeting(_ocr_record(["The committee noted the report."]))


def test_a_skipped_page_contributes_no_words_to_the_check():
    record = _ocr_record(["Body words."])
    record["pages"].append({"page": 3, "words": [], "source": "skipped",
                            "skip_reason": "blank sheet"})
    assert render_meeting(record)["word_check"] == "passed"


def test_a_header_with_no_body_start_is_unrecognised():
    record = _ocr_record(["Body."])
    del record["body_start"]
    from steps.render_spc_minutes.rendering import UnrecognisedBodyLayout

    with pytest.raises(UnrecognisedBodyLayout):
        render_meeting(record)


def test_attendance_check_follows_the_render_grouping_when_apologies_print_before_officials(
        rendered_new_meetings):
    feb = _new(rendered_new_meetings, "westmeath/", "2025-02-13")
    assert feb["word_check"] == "passed"
    markdown = feb["markdown"]
    assert markdown.index("### Officials present") < markdown.index("### Apologies")
