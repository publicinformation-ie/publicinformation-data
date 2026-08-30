import json
from pathlib import Path

from steps.extract_actions import process as extract_actions_process
from steps.extract_actions.process import (
    ACTION_KEYWORDS,
    DATE_KEYWORDS,
    classify_table,
    extract_document,
    extract_table,
    parse_date,
    process,
)


def table_block(rows, index=0):
    return {"number": 1, "blocks": [{"type": "table", "index": index, "text": rows,
                                     "y": 100.0}]}


def clean_record(pages, doc_slug="fixture-doc"):
    return {"doc_slug": doc_slug, "body_size": 10.0, "pages": pages}


def dated_rows():
    return [
        ["ACTION", "LEAD", "SUPPORT", "DEADLINE", "OUTPUT"],
        ["Build the road", "DoT", "NTA, TII", "Q4 2027", "Road built"],
        ["Ship the buses", "NTA", "DoT", "2030", "Fleet delivered"],
    ]


# --- keyword vocabularies --------------------------------------------------

def test_action_and_date_keywords_are_normalized_lowercase():
    assert "action" in ACTION_KEYWORDS
    assert "action(s)" in ACTION_KEYWORDS
    assert "strategic action" in ACTION_KEYWORDS
    assert "deadline" in DATE_KEYWORDS
    assert "target date" in DATE_KEYWORDS
    assert "quarter" in DATE_KEYWORDS


# --- header detection -------------------------------------------------------

def test_a_table_with_action_and_deadline_columns_is_a_dated_action_table():
    verdict = classify_table(dated_rows())
    assert verdict.is_action_table
    assert verdict.dated
    assert verdict.action_col == 0
    assert verdict.date_col == 3


def test_a_table_with_action_but_no_date_column_is_undated():
    rows = [
        ["Action", "Lead", "Support Partner(s)"],
        ["Expand the network", "NTA", "Local Authorities"],
    ]
    verdict = classify_table(rows)
    assert verdict.is_action_table
    assert not verdict.dated
    assert verdict.date_col is None


def test_a_progress_tracker_without_an_action_column_is_excluded():
    rows = [
        ["Quarter", "Complete", "Delayed", "Total"],
        ["Q1", "3", "1", "4"],
    ]
    verdict = classify_table(rows)
    assert not verdict.is_action_table
    assert verdict.error_type is None


def test_a_plain_data_table_without_an_action_column_is_excluded():
    rows = [
        ["Mode", "Share"],
        ["Walk", "25%"],
    ]
    assert not classify_table(rows).is_action_table


def test_an_empty_table_is_excluded():
    assert not classify_table([]).is_action_table
    assert not classify_table([["", ""]]).is_action_table


def test_headers_match_case_insensitively_and_across_normalized_whitespace():
    rows = [
        ["Action(s)", "Lead", "Target Date"],
        ["Build", "DoT", "2026"],
    ]
    verdict = classify_table(rows)
    assert verdict.is_action_table and verdict.dated


def test_a_title_only_row_above_the_real_header_is_skipped():
    """A section-title row (e.g. "CORE ACTIONS") merged in above the real
    ACTION/OWNER/... header — as seen in the SMP 2022-2025 action plan PDF
    — must not be mistaken for the header itself."""
    rows = [
        ["CORE ACTIONS", "", "", ""],
        ["ACTION", "OWNER", "SUPPORT", "TIMELINE & OUTPUT"],
        ["Build the road", "DoT", "NTA, TII", "2027"],
    ]
    verdict = classify_table(rows)
    assert verdict.is_action_table
    assert verdict.header_index == 1
    assert verdict.action_col == 0


def test_a_table_of_only_title_shaped_rows_falls_back_to_the_first_row():
    """If every row looks title-shaped (single populated cell, not a known
    keyword), there is no real header to land on — fall back to the first
    non-empty row rather than raising or returning no verdict."""
    rows = [
        ["Notes"],
        ["See appendix for detail"],
    ]
    verdict = classify_table(rows)
    assert verdict.header_index == 0
    assert not verdict.is_action_table


# --- fail-closed error paths -----------------------------------------------

def test_a_table_with_an_action_column_but_an_empty_data_action_cell_is_unclassified():
    rows = [
        ["Action", "Deadline"],
        ["Build the thing", "2030"],
        ["", "2031"],
    ]
    verdict = classify_table(rows)
    assert not verdict.is_action_table
    assert verdict.error_type == "UnclassifiedTable"


def test_a_header_with_two_action_columns_is_ambiguous():
    rows = [
        ["Action", "Action", "Deadline"],
        ["Build", "x", "2030"],
    ]
    assert classify_table(rows).error_type == "ActionHeaderAmbiguous"


def test_a_header_with_two_date_columns_is_ambiguous():
    rows = [
        ["Action", "Deadline", "Delivery Date"],
        ["Build", "2030", "2031"],
    ]
    assert classify_table(rows).error_type == "ActionHeaderAmbiguous"


# --- date parsing -----------------------------------------------------------

def test_parse_date_bare_year():
    parsed = parse_date("2030")
    assert parsed["precision"] == "year"
    assert parsed["year"] == 2030
    assert parsed["quarter"] is None
    assert parsed["start"] == "2030-01-01"
    assert parsed["end"] == "2030-12-31"


def test_parse_date_quarter():
    parsed = parse_date("Q2 2027")
    assert parsed["precision"] == "quarter"
    assert parsed["year"] == 2027
    assert parsed["quarter"] == 2
    assert parsed["start"] == "2027-04-01"
    assert parsed["end"] == "2027-06-30"


def test_parse_date_quarter_range():
    parsed = parse_date("Q1 2026 – Q4 2027")
    assert parsed["precision"] == "range"
    assert parsed["year"] is None
    assert parsed["start"] == "2026-01-01"
    assert parsed["end"] == "2027-12-31"


def test_parse_date_year_range():
    parsed = parse_date("2026–2030")
    assert parsed["precision"] == "range"
    assert parsed["start"] == "2026-01-01"
    assert parsed["end"] == "2030-12-31"


def test_parse_date_month():
    parsed = parse_date("January 2026")
    assert parsed["precision"] == "month"
    assert parsed["year"] == 2026
    assert parsed["month"] == 1
    assert parsed["start"] == "2026-01-01"
    assert parsed["end"] == "2026-01-31"


def test_parse_date_day_month_year():
    parsed = parse_date("15 January 2026")
    assert parsed["precision"] == "day"
    assert (parsed["year"], parsed["month"], parsed["day"]) == (2026, 1, 15)
    assert parsed["start"] == "2026-01-15"
    assert parsed["end"] == "2026-01-15"


def test_parse_date_iso():
    parsed = parse_date("2026-01-15")
    assert parsed["precision"] == "day"
    assert parsed["start"] == "2026-01-15"
    assert parsed["end"] == "2026-01-15"


def test_parse_date_empty_or_unparseable_returns_none():
    assert parse_date("") is None
    assert parse_date("Ongoing") is None
    assert parse_date("Annual") is None
    assert parse_date("31 February 2026") is None   # invalid date
    assert parse_date("Notadate") is None


# --- row extraction ---------------------------------------------------------

def test_extract_table_builds_stable_ids_structured_dates_and_columns():
    rows = dated_rows()
    verdict = classify_table(rows)
    actions = extract_table(rows, page_number=10, table_index=0, verdict=verdict,
                            doc_slug="fixture-doc", errors=[])

    assert [a["action_id"] for a in actions] == ["p010-t01-r01", "p010-t01-r02"]
    first, second = actions
    assert first["action"] == "Build the road"
    assert first["raw_date"] == "Q4 2027"
    assert first["precision"] == "quarter"
    assert first["source_page"] == 10
    assert first["source_table"] == 0
    assert first["columns"] == {"LEAD": "DoT", "SUPPORT": "NTA, TII",
                                "OUTPUT": "Road built"}
    assert second["precision"] == "year"
    assert second["start"] == "2030-01-01"


def test_extract_table_normalizes_multiline_cells():
    rows = [
        ["ACTION", "DEADLINE"],
        ["1. Establish a\nTransport\nSecurity Force", "2029"],
    ]
    verdict = classify_table(rows)
    (action,) = extract_table(rows, 9, 0, verdict, "fixture-doc", [])
    assert action["action"] == "1. Establish a Transport Security Force"
    assert action["raw_date"] == "2029"


def test_extract_table_skips_empty_rows_and_numbers_only_data_rows():
    rows = [
        ["ACTION", "DEADLINE"],
        ["First", "2030"],
        ["", ""],
        ["Second", "2031"],
    ]
    verdict = classify_table(rows)
    actions = extract_table(rows, 1, 0, verdict, "fixture-doc", [])
    assert [a["action_id"] for a in actions] == ["p001-t01-r01", "p001-t01-r02"]
    assert [a["action"] for a in actions] == ["First", "Second"]


def test_extract_table_skips_a_mid_table_title_and_repeated_header_row():
    """A table block that clean_text didn't split at a subsection boundary
    can contain a second title row and a second, repeated header row
    partway through — as seen in the SMP 2022-2025 action plan PDF (e.g.
    "COMPLEMENTARY ACTION IN HOUSING FOR ALL" followed by a second
    ACTION/OWNER/... header). Neither should be extracted as a data row."""
    rows = [
        ["ACTION", "OWNER", "SUPPORT", "TIMELINE & OUTPUT"],
        ["1. Build the road", "DoT", "NTA, TII", "2027"],
        ["COMPLEMENTARY ACTION IN HOUSING FOR ALL", "", "", ""],
        ["ACTION", "OWNER", "SUPPORT", "TIMELINE & OUTPUT"],
        ["2. Ship the buses", "NTA", "DoT", "2030"],
    ]
    verdict = classify_table(rows)
    actions = extract_table(rows, 1, 0, verdict, "fixture-doc", [])
    assert len(actions) == 2
    assert [a["action"] for a in actions] == ["1. Build the road", "2. Ship the buses"]
    assert [a["action_id"] for a in actions] == ["p001-t01-r01", "p001-t01-r02"]


def test_a_genuine_action_row_matching_a_keyword_text_is_kept():
    """The repeated-header skip must match the whole row against the
    header, not just the action cell against ACTION_KEYWORDS — a genuine
    action row whose action-column text happens to equal a keyword (e.g.
    "Measures") is not a repeated header row as long as its other cells
    differ from the header's, and must not be silently dropped."""
    rows = [
        ["ACTION", "OWNER", "SUPPORT", "TIMELINE & OUTPUT"],
        ["Measures", "DoT", "NTA", "2028"],
    ]
    verdict = classify_table(rows)
    actions = extract_table(rows, 1, 0, verdict, "fixture-doc", [])
    assert len(actions) == 1
    assert actions[0]["action"] == "Measures"


def test_an_undated_table_emits_actions_with_empty_dates():
    rows = [
        ["Action", "Lead"],
        ["Do a thing", "DoT"],
    ]
    verdict = classify_table(rows)
    (action,) = extract_table(rows, 3, 0, verdict, "fixture-doc", [])
    assert action["raw_date"] == ""
    assert action["precision"] is None
    assert action["year"] is None


def test_an_unparseable_date_is_kept_raw_and_logged():
    rows = [
        ["ACTION", "DEADLINE"],
        ["Build", "Ongoing"],
    ]
    verdict = classify_table(rows)
    errors = []
    actions = extract_table(rows, 1, 0, verdict, "fixture-doc", errors)
    (action,) = actions
    assert action["raw_date"] == "Ongoing"
    assert action["precision"] is None
    assert action["start"] is None
    assert len(errors) == 1
    assert errors[0]["error_type"] == "DateParseError"
    assert errors[0]["context"]["doc_slug"] == "fixture-doc"
    assert errors[0]["context"]["raw_date"] == "Ongoing"


# --- document-level classification ------------------------------------------

def test_extract_document_categorises_dated_actions():
    record = clean_record([table_block(dated_rows())])
    category, dated, undated, actions, errors = extract_document(record, "fixture-doc")
    assert category == "dated-actions"
    assert dated == 1
    assert undated == 0
    assert len(actions) == 2
    assert errors == []


def test_extract_document_categorises_undated_actions():
    record = clean_record([table_block([
        ["Action", "Lead"],
        ["Do a thing", "DoT"],
    ])])
    category, dated, undated, actions, _ = extract_document(record, "fixture-doc")
    assert category == "undated-actions"
    assert dated == 0 and undated == 1
    assert len(actions) == 1


def test_extract_document_categorises_no_action_tables():
    record = clean_record([table_block([
        ["Quarter", "Complete", "Delayed", "Total"],
        ["Q1", "3", "1", "4"],
    ])])
    category, dated, undated, actions, _ = extract_document(record, "fixture-doc")
    assert category == "no-action-tables"
    assert dated == 0 and undated == 0
    assert actions == []


def test_a_mixed_document_prefers_dated_and_counts_both_kinds():
    record = clean_record([
        table_block([["ACTION", "DEADLINE"], ["A", "2030"]], index=0),
        table_block([["ACTION"], ["B"]], index=1),
    ])
    category, dated, undated, actions, _ = extract_document(record, "fixture-doc")
    assert category == "dated-actions"
    assert dated == 1 and undated == 1
    assert len(actions) == 2


def test_unclassified_tables_are_reported_but_not_extracted():
    record = clean_record([table_block([
        ["Action", "Deadline"],
        ["Build", "2030"],
        ["", "2031"],
    ])])
    category, dated, undated, actions, errors = extract_document(record, "fixture-doc")
    assert category == "no-action-tables"
    assert actions == []
    assert [e["error_type"] for e in errors] == ["UnclassifiedTable"]


# --- published side artifact removal ----------------------------------------

def test_the_step_no_longer_publishes_a_flat_actions_file(tmp_path, make_writer):
    """public/documents/actions.json is superseded by the public-body-actions
    dataset, which carries public_body_id, stable identities and status
    history that the flat file never had."""
    from steps.extract_actions import process as module
    assert not hasattr(module, "write_public_actions")
    assert not hasattr(module, "flatten_actions")


# --- end-to-end step behaviour ----------------------------------------------

def test_process_writes_a_record_and_isolates_a_malformed_document(tmp_path):
    good = {"doc_slug": "good-doc", "body_size": 10.0, "pages": [
        {"number": 1, "blocks": [{"type": "table", "index": 0, "y": 1.0,
                                  "text": [["ACTION", "DEADLINE"], ["A", "2030"]]}]}]}
    bad = {"doc_slug": "bad-doc", "body_size": 10.0, "pages": ["garbage"]}
    records = [good, bad]

    step_dir = tmp_path / "extract_actions"
    step_dir.mkdir()
    writer = extract_actions_process.IncrementalWriter(
        step_dir / "output.json", "extract_actions", key_field="doc_slug", force=True)
    meta = {"good-doc": {"doc_title": "Good", "source_url": "https://x",
                         "public_body_id": 1, "publisher": None, "published_date": None}}

    process(records, meta, step_dir, writer)
    writer.finalize()

    results = json.loads((step_dir / "output.json").read_text())["results"]
    (record,) = results
    assert record["doc_slug"] == "good-doc"
    assert record["category"] == "dated-actions"
    assert record["action_count"] == 1
    assert record["doc_title"] == "Good"

    errors = json.loads((step_dir / "errors.json").read_text())
    failed = [e for e in errors if e["error_type"] == "ExtractActionsFailed"]
    assert [e["context"]["doc_slug"] for e in failed] == ["bad-doc"]
    # Not marked processed, so a later run retries it.
    assert "bad-doc" not in writer.processed_keys


def report_meta(slug):
    return {slug: {"doc_title": slug, "source_url": "", "publisher": None,
                   "published_date": None, "public_body_id": 1213,
                   "role": "report"}}


def plan_meta(slug):
    meta = report_meta(slug)
    meta[slug]["role"] = "plan"
    return meta


def test_a_report_document_yields_no_actions(tmp_path, make_writer):
    writer = make_writer("extract_actions")
    records = [clean_record([table_block(dated_rows())], doc_slug="a-report")]
    process(records, report_meta("a-report"), tmp_path, writer)
    writer.finalize()
    assert json.loads((tmp_path / "output.json").read_text())["results"] == []


def test_a_document_with_no_role_is_still_treated_as_a_plan(tmp_path, make_writer):
    writer = make_writer("extract_actions")
    records = [clean_record([table_block(dated_rows())], doc_slug="legacy-doc")]
    process(records, {"legacy-doc": {}}, tmp_path, writer)
    writer.finalize()
    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert len(results) == 1
    assert results[0]["action_count"] > 0


def test_an_explicit_plan_document_still_yields_actions(tmp_path, make_writer):
    writer = make_writer("extract_actions")
    records = [clean_record([table_block(dated_rows())], doc_slug="a-plan")]
    process(records, plan_meta("a-plan"), tmp_path, writer)
    writer.finalize()
    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert len(results) == 1
