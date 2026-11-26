from datetime import date

import pytest

from steps.parse_meeting_header.header import (
    MeetingDateMismatch,
    MeetingDateUnparseable,
    UnrecognisedHeaderLayout,
    label_category,
    link_month_year,
    parse_date_and_venue,
    parse_end_time,
    parse_entries,
    parse_record,
    run,
)

EXPECTED_DATES = {
    "2025-02-20", "2025-05-27", "2025-09-11",
    "2025-11-20", "2026-02-19", "2026-05-21",
}


def _word(text, x0, top, width=None):
    width = width if width is not None else max(5, 5.0 * len(text))
    return {"text": text, "x0": x0, "x1": x0 + width, "top": top, "bottom": top + 10}


def _attendance_words(value_rows, label_x=77.6, value_x=189.8, start_top=166.8):
    """Build words for an attendance table.

    ``value_rows`` is a list of ``(label_lines, [value_line, ...])``. Each
    value line is a list of token strings.
    """
    words = []
    top = start_top
    for labels, value_lines in value_rows:
        label_top = top
        for offset, label in enumerate(labels):
            for part in label.split(" "):
                words.append(_word(part, label_x, label_top + offset * 13.5))
        value_top = label_top - 0.4
        for line in value_lines:
            x = value_x
            for token in line:
                words.append(_word(token, x, value_top))
                x += 5.0 * len(token) + 2
            value_top += 13.5
        top = value_top + 10
    return words


def _values(words):
    """The value column only (parse_record does this filtering itself)."""
    return [w for w in words if w["x0"] >= 180]


def _page(words):
    return {"page": 1, "width": 595.32, "height": 841.92, "words": words}


def test_header_date_venue_and_start_time():
    text = ("Transportation & Urban Regeneration Strategic Policy Committee "
            "20th February 2025, Swift Room, Buvinda House, Dublin Rd, Navan, "
            "C15 C7X3 at 2.30 pm")
    date_text, meeting_date, venue, start = parse_date_and_venue(text)
    assert date_text == "20th February 2025"
    assert meeting_date == date(2025, 2, 20)
    assert venue == "Swift Room, Buvinda House, Dublin Rd, Navan, C15 C7X3"
    assert start == "2.30 pm"


def test_missing_date_is_unparseable():
    with pytest.raises(MeetingDateUnparseable):
        parse_date_and_venue("Transportation Strategic Policy Committee, Swift Room")


def test_link_month_year():
    assert link_month_year("February 2026 - Minutes - SPC") == (2, 2026)
    assert link_month_year("Minutes - SPC") is None
    assert link_month_year(None) is None


def test_end_time_formats():
    assert parse_end_time("Meeting ended @16.15pm") == "16.15pm"
    assert parse_end_time("Meeting ended @17.00 pm") == "17.00 pm"
    assert parse_end_time("Meeting ended @16.21") == "16.21"
    assert parse_end_time("no ending printed") is None


def test_labels_map_to_categories():
    assert label_category("Attendees - (Councillors):") == "councillors"
    assert label_category("Attendees - (Sectoral Representatives):") == "sectoral_representatives"
    assert label_category("Absent Apologies:") == "apologies"
    assert label_category("(Officials):") == "officials"
    assert label_category("Presenters") == "presenters"


def test_unknown_label_is_unrecognised():
    with pytest.raises(UnrecognisedHeaderLayout):
        label_category("Attendees - (Observers):")


def test_two_names_without_a_comma_are_split():
    words = _attendance_words([
        (["Attendees", "-"], [
            ["Cllr", "Mike", "Bray", "(MB)", "Chair,"],
            ["Cllr", "Sean", "Drew", "Cllr", "Paddy", "Meade", "(PM)", "online"],
        ]),
    ])
    entries, _ = parse_entries(_values(words), "councillors")
    assert [e["printed_name"] for e in entries] == ["Mike Bray", "Sean Drew", "Paddy Meade"]
    assert entries[-1]["markers"] == ["remote"]


def test_stray_title_fragment_is_ignored_and_counted():
    words = _attendance_words([
        (["Attendees", "-"], [["Cllr,", "Cllr", "Wayne", "Harding", "(WH)"]]),
    ])
    entries, ignored = parse_entries(_values(words), "apologies")
    assert [e["printed_name"] for e in entries] == ["Wayne Harding"]
    assert ignored == 1


def test_marker_after_a_comma_applies_to_the_previous_entry():
    words = _attendance_words([
        (["Attendees", "-"], [
            ["Ms.", "Josephine", "Reynolds", "O’Connor", "(JROC),", "PPN", "Rep,",
             "in", "person."],
            ["Ms.", "Paula", "Mc", "Caul", "(PMC)", "PPN", "Rep", "online"],
        ]),
    ])
    entries, _ = parse_entries(_values(words), "sectoral_representatives")
    assert [e["markers"] for e in entries] == [["in_person"], ["remote"]]


def test_role_fragment_attaches_to_the_name_before_it():
    words = _attendance_words([
        (["(Officials):"], [
            ["Martin", "Murray", "(MM),", "DOS,", "Fiona", "Beers", "(FB)", "Acting",
             "Senior", "Engineer"],
        ]),
    ])
    entries, _ = parse_entries(_values(words), "officials")
    assert [(e["printed_name"], e["role"]) for e in entries] == [
        ("Martin Murray", "DOS"),
        ("Fiona Beers", "Acting Senior Engineer"),
    ]
    # The printed text kept for the verbatim minutes must include the role
    # fragment, even though it arrived as a separate printed fragment.
    assert entries[0]["raw"] == "Martin Murray (MM), DOS"


def test_role_printed_before_the_name_is_kept_in_the_printed_text():
    words = _attendance_words([
        (["(Officials):"], [[
            "Chair,", "Martin", "Murray", "(MM),", "DOS",
        ]]),
    ])
    entries, _ = parse_entries(_values(words), "officials")
    assert entries[0]["role"] == "Chair, DOS"
    assert entries[0]["raw"] == "Chair, Martin Murray (MM), DOS"


def test_wrapped_line_without_a_comma_starts_a_new_person():
    words = _attendance_words([
        (["Absent"], [["Cllr,", "Cllr", "Wayne", "Harding", "(WH)"]]),
        (["Apologies:"], [[
            "Martin", "Murray", "(MM),", "DOS,",
        ]]),
    ])
    entries, _ = parse_entries(_values(words), "apologies")
    assert [e["printed_name"] for e in entries] == ["Wayne Harding", "Martin Murray"]


def test_presentation_label_is_skipped_and_bullets_split_presenters():
    words = _attendance_words([
        (["Presentations", "made", "by", "-"], [
            ["•", "Caroline", "Corrigan", "-", "Senior", "Engineer", "–", "Footpath",
             "Programme"],
            ["•", "John", "McGrath", "-", "Senior", "Engineer", "-", "Regeneration"],
        ]),
    ])
    # The label sits in the value column in this layout; the parser receives
    # the block's value words, with the label already removed.
    entries, _ = parse_entries(_values(words), "presenters")
    names = [e["printed_name"] for e in entries]
    assert names == ["Caroline Corrigan", "John McGrath"]


def _synthetic_source(link_text="February 2026 - Minutes - SPC"):
    words = [_word("Transportation", 73.7, 125.5), _word("Committee", 200.0, 125.5),
             _word("19th", 375.6, 125.5), _word("February", 395.4, 125.5),
             _word("2026,", 438.6, 125.5), _word("Swift", 466.3, 125.5),
             _word("Room", 492.1, 125.5), _word("at", 374.4, 139.0),
             _word("2.30", 386.5, 139.0), _word("pm", 408.6, 139.0)]
    words += _attendance_words([
        (["Attendees", "-"], [["Cllr", "Mike", "Bray", "(MB)"]]),
        (["(Councillors):"], []),
        (["(Officials):"], [["Joan", "Carroll", "(JC)", "Senior", "Executive", "Officer"]]),
    ])
    words.append(_word("Item", 77.6, 500.0))
    return {
        "committee_id": "meath/transportation-urban-regeneration",
        "committee_name": "Transportation & Urban Regeneration Strategic Policy Committee",
        "public_body_id": 1511,
        "page_url": "https://www.meath.ie/page",
        "file_url": "https://www.meath.ie/files/minutes.pdf",
        "link_text": link_text,
        "sha256": "abc",
        "page_count": 1,
        "pages": [_page(words)],
    }


def test_header_date_must_agree_with_link_text():
    source = _synthetic_source(link_text="February 2025 - Minutes - SPC")
    with pytest.raises(MeetingDateMismatch):
        parse_record(source)


def test_synthetic_meeting_parses_end_to_end():
    source = _synthetic_source(link_text="February 2026 - Minutes - SPC")
    record = parse_record(source)
    assert record["meeting_id"] == "meath/transportation-urban-regeneration/2026-02-19"
    assert [e["printed_name"] for e in record["attendance"]] == ["Mike Bray", "Joan Carroll"]


def test_all_six_real_meetings_have_the_expected_dates(fetched_meetings):
    records, errors = run({"results": fetched_meetings})
    assert errors == []
    assert {r["meeting_date"] for r in records} == EXPECTED_DATES


def test_all_six_real_meetings_resolve_their_attendance_without_errors(fetched_meetings):
    records, _ = run({"results": fetched_meetings})
    by_id = {r["meeting_id"].rsplit("/", 1)[-1]: r for r in records}
    # The interleaved "Cllr Sean Drew Cllr Paddy Meade" row.
    feb26 = by_id["2026-02-19"]
    councillors = [e["printed_name"] for e in feb26["attendance"]
                   if e["category"] == "councillors"]
    assert councillors == ["Mike Bray", "Amanda Smith", "Sean Drew", "Paddy Meade",
                           "Caroline O’Reilly"]
    # A stray "Cllr," is counted, never a person.
    assert feb26["ignored_fragments"] >= 1
    assert all(e["printed_name"] != "Cllr" for e in feb26["attendance"])
    # "Absent Apologies:" is one category.
    assert [e["printed_name"] for e in feb26["attendance"]
            if e["category"] == "apologies"] == ["Wayne Harding", "Paula Mc Caul"]
    # The presenters row contains "apologies" mid-list.
    may26 = by_id["2026-05-21"]
    presenters = {e["printed_name"]: e for e in may26["attendance"]
                  if e["category"] == "presenters"}
    assert presenters["Helen Meyer"]["markers"] == ["apologies"]
    assert presenters["Alan Tobin"]["markers"] == []


def test_duplicate_meeting_withholds_both_files():
    first = _synthetic_source()
    second = dict(first, file_url="https://www.meath.ie/files/other.pdf")
    records, errors = run({"results": [first, second]})
    assert records == []
    assert [e["error_type"] for e in errors] == ["DuplicateMeeting"]
