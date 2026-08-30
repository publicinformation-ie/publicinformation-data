import json

from steps.extract_action_status.process import (
    STATUS_VOCABULARY,
    detect_format,
    extract_document,
    extract_table,
    normalize_status,
    process,
    status_sections,
)

FORMAT_A_HEADER = ["No.", "Action", "Proposed Output", "SMP Deadline",
                   "Status", "Progress", "ASI"]
FORMAT_B_HEADER = ["No.", "Action", "Proposed Output", "SMP Deadline", "Progress"]


def table_block(rows, index=0, page=9):
    return {"number": page,
            "blocks": [{"type": "table", "index": index, "text": rows, "y": 100.0}]}


def status_page(label, page):
    """A page whose only content is a standalone Complete/Modified/Delayed
    label — the real corpus shape a Format B table's status is read from."""
    return {"number": page,
            "blocks": [{"type": "paragraph", "text": label, "y": 50.0}]}


def blank_page(page):
    """A page with no relevant content — every real document has one page
    record per page number, whether or not this step cares about its blocks."""
    return {"number": page, "blocks": []}


def clean_record(pages, doc_slug="a-report"):
    return {"doc_slug": doc_slug, "body_size": 10.0, "pages": pages}


def report(slug="a-report", **overrides):
    doc = {"doc_title": "A Report", "source_url": "https://example.ie/r.pdf",
           "published_date": "2024-08-27", "public_body_id": 1213,
           "role": "report", "reports_on": "a-plan"}
    doc.update(overrides)
    return doc


# --- format detection -------------------------------------------------------

def test_a_seven_column_header_is_format_a():
    assert detect_format(FORMAT_A_HEADER) == "A"


def test_a_five_column_header_is_format_b():
    assert detect_format(FORMAT_B_HEADER) == "B"


def test_header_detection_ignores_case_and_trailing_punctuation():
    assert detect_format(["NO.", "ACTION", "PROPOSED OUTPUT:", "SMP Deadline",
                          "status", "Progress", "asi"]) == "A"


def test_an_unrecognised_header_is_neither_format():
    assert detect_format(["Action", "Owner", "Support", "Timeline & Output"]) is None
    assert detect_format([]) is None


def test_an_unrecognised_header_makes_the_document_unknown_format():
    errors = []
    record = extract_document(
        clean_record([table_block([["Action", "Owner"], ["Do a thing", "DoT"]])]),
        report(), errors)
    assert record is None
    assert [e["error_type"] for e in errors] == ["UnknownReportFormat"]


def test_a_format_a_table_is_not_silently_emptied_by_the_format_b_path():
    """The failure this guards: running the B reader over an A report finds no
    status heading anywhere and emits UnknownStatusSection for every table —
    a 100% data loss indistinguishable from 'this document has no actions'."""
    errors = []
    record = extract_document(
        clean_record([table_block([FORMAT_A_HEADER,
                                   ["01", "Do a thing", "A thing", "Q4 2024",
                                    "Complete", "Done", "Improve"]])]),
        report(), errors)
    assert record["report_format"] == "A"
    assert record["observation_count"] == 1
    assert not [e for e in errors if e["error_type"] == "UnknownStatusSection"]


# --- format A ---------------------------------------------------------------

def test_format_a_reads_status_from_the_status_column_and_captures_asi():
    errors = []
    rows = [FORMAT_A_HEADER,
            ["01", "Do a thing", "A thing", "Q4 2024", "Complete", "Done", "Improve"]]
    observations = extract_table(rows, 9, 0, "A", None, "a-report", errors)
    assert len(observations) == 1
    obs = observations[0]
    assert obs["action_number"] == 1
    assert obs["status"] == "Complete"
    assert obs["asi"] == "Improve"
    assert obs["reported_deadline_raw"] == "Q4 2024"
    assert obs["reported_deadline_precision"] == "quarter"
    assert obs["reported_deadline_start"] == "2024-10-01"
    assert obs["source_ref"] == "p009-t01-r01"
    assert errors == []


def test_a_zero_padded_action_number_becomes_an_integer():
    observations = extract_table(
        [FORMAT_A_HEADER,
         ["05", "Do a thing", "A thing", "2025", "Delayed", "Slipped", "Shift"]],
        9, 0, "A", None, "a-report", [])
    assert observations[0]["action_number"] == 5


# --- format B ---------------------------------------------------------------

def test_status_sections_map_pages_to_the_last_seen_status_label():
    mapping = status_sections(clean_record([
        blank_page(5),
        status_page("Complete", 10),
        blank_page(19),
        status_page("Delayed", 20),
        blank_page(25),
        status_page("Modified", 30),
        blank_page(31),
    ]))
    assert mapping[10] == "Complete"
    assert mapping[19] == "Complete"
    assert mapping[25] == "Delayed"
    assert mapping[31] == "Modified"
    assert 5 not in mapping


def test_a_page_before_any_status_label_is_not_mapped():
    mapping = status_sections(clean_record([status_page("Complete", 10)]))
    assert 5 not in mapping


def test_format_b_derives_status_from_the_preceding_label():
    errors = []
    record = extract_document(
        clean_record([status_page("Complete", 10),
                      table_block(
            [FORMAT_B_HEADER,
             ["01", "Do a thing", "A thing", "Q4 2024", "Done"]], page=12)]),
        report(), errors)
    assert record["report_format"] == "B"
    assert record["observations"][0]["status"] == "Complete"
    assert record["observations"][0]["asi"] is None
    assert errors == []


def test_a_format_b_table_before_any_status_label_is_skipped_and_logged():
    errors = []
    record = extract_document(
        clean_record([table_block(
            [FORMAT_B_HEADER,
             ["01", "Do a thing", "A thing", "Q4 2024", "Done"]], page=12)]),
        report(), errors)
    assert record["observation_count"] == 0
    assert [e["error_type"] for e in errors] == ["UnknownStatusSection"]


# --- continuation rows ------------------------------------------------------

def test_a_continuation_row_is_appended_to_the_previous_row():
    errors = []
    observations = extract_table(
        [FORMAT_A_HEADER,
         ["01", "Do a thing", "A thing", "Q4 2024", "Complete", "Started well", "Improve"],
         ["", "", "", "", "", "and then finished", ""]],
        9, 0, "A", None, "a-report", errors)
    assert len(observations) == 1
    assert observations[0]["progress_text"] == "Started well and then finished"
    assert errors == []


def test_a_repeated_header_row_mid_table_is_not_a_continuation():
    observations = extract_table(
        [FORMAT_A_HEADER,
         ["01", "A", "A", "2024", "Complete", "p", "Improve"],
         FORMAT_A_HEADER,
         ["02", "B", "B", "2025", "Delayed", "q", "Shift"]],
        9, 0, "A", None, "a-report", [])
    assert [o["action_number"] for o in observations] == [1, 2]
    assert observations[0]["progress_text"] == "p"


def test_an_orphaned_continuation_row_is_skipped_and_logged():
    errors = []
    observations = extract_table(
        [FORMAT_A_HEADER, ["", "", "", "", "", "orphaned text", ""]],
        9, 0, "A", None, "a-report", errors)
    assert observations == []
    assert [e["error_type"] for e in errors] == ["ContinuationRowOrphaned"]


# --- status normalisation ---------------------------------------------------

def test_status_normalisation_handles_line_breaks_and_casing():
    assert normalize_status("On\nschedule") == "OnSchedule"
    assert normalize_status("  COMPLETE ") == "Complete"
    assert normalize_status("ongoing") == "Ongoing"
    assert normalize_status("Modified") == "Modified"


def test_an_unmappable_status_is_not_coerced_to_a_nearest_match():
    assert normalize_status("Substantially complete") is None
    assert normalize_status("") is None


def test_an_unmappable_status_skips_the_observation_and_logs():
    errors = []
    observations = extract_table(
        [FORMAT_A_HEADER,
         ["01", "Do a thing", "A thing", "2024", "Substantially complete", "p", "Improve"]],
        9, 0, "A", None, "a-report", errors)
    assert observations == []
    assert [e["error_type"] for e in errors] == ["UnknownStatusValue"]


def test_every_vocabulary_value_is_a_notation_not_a_display_name():
    assert set(STATUS_VOCABULARY.values()) == {
        "Complete", "OnSchedule", "Delayed", "Ongoing", "Modified"}


# --- deadlines --------------------------------------------------------------

def test_an_unparseable_reported_deadline_keeps_the_raw_and_logs():
    errors = []
    observations = extract_table(
        [FORMAT_A_HEADER,
         ["01", "Do a thing", "A thing", "Ongoing", "Complete", "p", "Improve"]],
        9, 0, "A", None, "a-report", errors)
    assert observations[0]["reported_deadline_raw"] == "Ongoing"
    assert observations[0]["reported_deadline_start"] is None
    assert [e["error_type"] for e in errors] == ["DateParseError"]


def test_the_reported_deadline_uses_the_same_parser_as_extract_actions():
    from steps.extract_actions.process import parse_date
    observations = extract_table(
        [FORMAT_A_HEADER,
         ["01", "A", "A", "Q1 2024 - Q3 2025", "Complete", "p", "Improve"]],
        9, 0, "A", None, "a-report", [])
    expected = parse_date("Q1 2024 - Q3 2025")
    assert observations[0]["reported_deadline_precision"] == expected["precision"]
    assert observations[0]["reported_deadline_start"] == expected["start"]
    assert observations[0]["reported_deadline_end"] == expected["end"]


# --- document record and scoping --------------------------------------------

def test_as_of_is_the_reports_published_date_not_document_content():
    record = extract_document(
        clean_record([table_block(
            [FORMAT_A_HEADER,
             ["01", "A", "A", "2024", "Complete", "Completed in 2019", "Improve"]])]),
        report(published_date="2024-08-27"), [])
    assert record["as_of"] == "2024-08-27"
    assert record["reports_on"] == "a-plan"


def test_status_counts_tally_the_observations():
    record = extract_document(
        clean_record([table_block(
            [FORMAT_A_HEADER,
             ["01", "A", "A", "2024", "Complete", "p", "Improve"],
             ["02", "B", "B", "2025", "Delayed", "q", "Shift"],
             ["03", "C", "C", "2025", "Complete", "r", "Avoid"]])]),
        report(), [])
    assert record["status_counts"] == {"Complete": 2, "Delayed": 1}
    assert record["observation_count"] == 3


def test_a_plan_document_is_skipped_without_error(tmp_path, make_writer):
    writer = make_writer("extract_action_status")
    process([clean_record([table_block([FORMAT_A_HEADER])], doc_slug="a-plan")],
            {"a-plan": report("a-plan", role="plan", reports_on=None)},
            tmp_path, writer)
    writer.finalize()
    assert json.loads((tmp_path / "output.json").read_text())["results"] == []
    assert json.loads((tmp_path / "errors.json").read_text()) == []


def test_an_unknown_format_document_is_not_marked_processed(tmp_path, make_writer):
    """Not marked processed so a later run retries it once the reader learns
    the layout — without needing --force."""
    writer = make_writer("extract_action_status")
    process([clean_record([table_block([["Action", "Owner"]])])],
            {"a-report": report()}, tmp_path, writer)
    writer.finalize()
    assert json.loads((tmp_path / "output.json").read_text())["results"] == []
    assert not writer.is_processed("a-report")
    assert [e["error_type"] for e in
            json.loads((tmp_path / "errors.json").read_text())] == ["UnknownReportFormat"]
