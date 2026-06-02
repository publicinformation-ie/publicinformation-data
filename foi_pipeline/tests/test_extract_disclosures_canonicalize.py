import pytest
from steps.extract_disclosures_canonicalize.column_map import (
    canonicalize_header,
    canonicalize_headers,
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
)


def test_canonical_columns_order():
    assert CANONICAL_COLUMNS == [
        "foi_reference_id", "date_received", "decision_date", "requester_type",
        "decision_status", "review_status", "related_request", "request_description",
    ]


def test_required_columns():
    assert "foi_reference_id" in REQUIRED_COLUMNS
    assert "request_description" in REQUIRED_COLUMNS


def test_canonicalize_our_reference():
    assert canonicalize_header("Our Reference") == "foi_reference_id"


def test_canonicalize_date_recd():
    assert canonicalize_header("Date Rec'd") == "date_received"


def test_canonicalize_request_details():
    assert canonicalize_header("Request Details") == "request_description"


def test_canonicalize_outcome():
    assert canonicalize_header("Outcome") is None  # not in schema — archive dropped it


def test_canonicalize_case_insensitive():
    assert canonicalize_header("our reference") == "foi_reference_id"
    assert canonicalize_header("OUR REFERENCE") == "foi_reference_id"


def test_canonicalize_whitespace_trimmed():
    assert canonicalize_header("  Request Details  ") == "request_description"


def test_canonicalize_none_returns_none():
    assert canonicalize_header(None) is None


def test_canonicalize_empty_returns_none():
    assert canonicalize_header("") is None
    assert canonicalize_header("   ") is None


def test_canonicalize_headers_maps_list():
    result = canonicalize_headers(["Our Reference", "Date Rec'd", "Request Details"])
    assert result == {
        "Our Reference": "foi_reference_id",
        "Date Rec'd": "date_received",
        "Request Details": "request_description",
    }


def test_strip_year_suffix():
    # Archive strips trailing 4-digit year from headers like "Decision Date 2016"
    assert canonicalize_header("Decision Date 2016") == "decision_date"


# ── canonicalize_file and process() tests ─────────────────────────────────────

from steps.extract_disclosures_canonicalize.process import (
    canonicalize_file,
    process,
    STEP_NAME,
)


BASE_META = {
    "public_body_id": 1001,
    "name": "Dept A",
    "file_url": "https://assets.gov.ie/log.xlsx",
    "file_type": "xlsx",
}


def test_canonicalize_file_maps_known_headers():
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002", "2016-01-05", "some request"],
    ]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/002"
    assert results[0]["request_description"] == "some request"
    assert results[0]["date_received"] == "2016-01-05"
    assert results[0]["decision_date"] is None
    assert errors == []


def test_canonicalize_file_includes_metadata_fields():
    rows = [["Our Reference", "Request Details"], ["16/003", "a request"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results[0]["public_body_id"] == 1001
    assert results[0]["name"] == "Dept A"
    assert results[0]["file_url"] == BASE_META["file_url"]
    assert results[0]["file_type"] == "xlsx"


def test_canonicalize_file_fills_none_for_optional_missing_columns():
    rows = [["Our Reference", "Request Details"], ["16/004", "some request"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results[0]["decision_date"] is None
    assert results[0]["requester_type"] is None
    assert results[0]["decision_status"] is None
    assert results[0]["review_status"] is None
    assert results[0]["related_request"] is None


def test_canonicalize_file_drops_unrecognised_columns():
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details", "Outcome", "Refusal under Section"],
        ["16/005", "2016-01-10", "some request", "Transferred", None],
    ]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert "Outcome" not in results[0]
    assert "Refusal under Section" not in results[0]


def test_canonicalize_file_skips_empty_data_rows():
    rows = [
        ["Our Reference", "Request Details"],
        ["16/001", "first request"],
        [],
        ["16/002", "second request"],
    ]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 2


def test_canonicalize_file_insufficient_columns_when_only_one_maps():
    # Only request_description maps — fewer than 2 canonical columns → InsufficientColumns
    rows = [["Request Details"], ["some request"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "InsufficientColumns"
    assert "foi_reference_id" not in errors[0]["error_message"]  # new error type, no column list in message


def test_canonicalize_file_emits_partial_record_when_foi_ref_absent():
    # request_description + date_received map (≥2), foi_reference_id absent → partial record
    rows = [["Request Details", "Date Received"], ["some request", "2016-01-01"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results != []
    assert errors == []
    assert results[0]["missing_columns"] == ["foi_reference_id"]


def test_canonicalize_file_uses_header_row_idx():
    rows = [
        ["January - September 2011", None, None],
        ["FOI Reference", "Date", "Request Description"],
        ["11/001", "2011-01-15", "some request"],
    ]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 1})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "11/001"
    assert results[0]["request_description"] == "some request"


def test_canonicalize_file_returns_empty_for_null_rows():
    results, errors = canonicalize_file({**BASE_META, "rows": None, "header_row_idx": None})
    assert results == []
    assert errors == []


def test_canonicalize_file_multiple_data_rows():
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002", "2016-01-05", "first request"],
        ["16/003", "2016-01-11", "second request"],
        ["16/004", "2016-01-12", "third request"],
    ]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 3
    assert results[1]["foi_reference_id"] == "16/003"


def test_canonicalize_file_row_shorter_than_headers_gets_none():
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002"],  # only 1 cell
    ]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/002"
    assert results[0]["decision_date"] is None
    assert results[0]["request_description"] is None


# ── process() integration tests ───────────────────────────────────────────────

def _make_canonicalize_input(results):
    return {"metadata": {"step": "extract_disclosures_detect_header_row"}, "results": results}


FULL_ITEM = {
    **BASE_META,
    "sheet_name": "Sheet1",
    "header_row_idx": 0,
    "rows": [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002", "2016-01-05", "some request"],
    ],
}

PDF_ITEM = {
    **BASE_META,
    "file_url": "https://assets.gov.ie/log.pdf",
    "file_type": "pdf",
    "sheet_name": None,
    "header_row_idx": None,
    "rows": None,
}


def test_process_emits_flat_foi_records(tmp_path):
    results, errors_out = [], []
    process(_make_canonicalize_input([FULL_ITEM]), results, errors_out)
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/002"


def test_process_skips_pdf_records(tmp_path):
    results, errors_out = [], []
    process(_make_canonicalize_input([PDF_ITEM]), results, errors_out)
    assert results == []
    assert errors_out == []


def test_process_logs_error_for_missing_required_columns(tmp_path):
    # 1 column maps → InsufficientColumns error (replaces MissingRequiredColumns)
    item = {
        **BASE_META,
        "sheet_name": "Sheet1",
        "header_row_idx": 0,
        "rows": [["Date Received"], ["2016-01-01"]],
    }
    results, errors_out = [], []
    process(_make_canonicalize_input([item]), results, errors_out)
    assert results == []
    assert len(errors_out) == 1
    assert errors_out[0]["error_type"] == "InsufficientColumns"


def test_process_multiple_files_multiple_records(tmp_path):
    item2 = {
        **BASE_META,
        "file_url": "https://assets.gov.ie/log2.xlsx",
        "header_row_idx": 0,
        "rows": [
            ["Our Reference", "Request Details"],
            ["17/001", "first"],
            ["17/002", "second"],
        ],
    }
    results, errors_out = [], []
    process(_make_canonicalize_input([FULL_ITEM, item2]), results, errors_out)
    assert len(results) == 3


def test_canonicalize_file_empty_rows_returns_empty():
    results, errors = canonicalize_file({**BASE_META, "rows": [], "header_row_idx": 0})
    assert results == []
    assert errors == []


def test_canonicalize_file_none_header_row_idx_with_rows_returns_empty():
    rows = [["Our Reference", "Request Details"], ["16/001", "a request"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": None})
    assert results == []
    assert errors == []


def test_process_uses_two_list_args(tmp_path):
    # Confirm process() signature: no step_dir param
    results, errors_out = [], []
    process(_make_canonicalize_input([FULL_ITEM]), results, errors_out)
    assert len(results) == 1


# ── New synonym tests — foi_reference_id ──────────────────────────────────────

def test_canonicalize_file_ref_dot():
    assert canonicalize_header("File Ref.") == "foi_reference_id"

def test_canonicalize_file_ref():
    assert canonicalize_header("File Ref") == "foi_reference_id"


# ── New synonym tests — request_description ───────────────────────────────────

def test_canonicalize_foi_request():
    assert canonicalize_header("FOI Request") == "request_description"

def test_canonicalize_brief_description_of_the_request():
    assert canonicalize_header("Brief Description of the Request") == "request_description"

def test_canonicalize_summary_of_the_information_records_requested():
    assert canonicalize_header("Summary of the Information/Records Requested") == "request_description"

def test_canonicalize_records_requested():
    assert canonicalize_header("Records Requested") == "request_description"

def test_canonicalize_query_re():
    assert canonicalize_header("Query Re") == "request_description"

def test_canonicalize_long_pdf_concatenated_header():
    assert canonicalize_header(
        "Disclosure Log for 2023 Description of the Request (Categories of Records Sought)"
    ) == "request_description"


# ── New synonym tests — decision_status ───────────────────────────────────────

def test_canonicalize_decisions_made():
    assert canonicalize_header("Decisions Made") == "decision_status"


# ── New synonym tests — requester_type ────────────────────────────────────────

def test_canonicalize_category_of_applicant():
    assert canonicalize_header("Category of Applicant") == "requester_type"

def test_canonicalize_personal_non_personal_ocr():
    assert canonicalize_header("Personal (P)/Non- Persona (NP)") == "requester_type"

def test_canonicalize_ocr_spaced_category_of_requester():
    # OCR artefact: each character separated by a space
    assert canonicalize_header("C a t e g o r y o f requester") == "requester_type"


# ── Two-level column gate tests ───────────────────────────────────────────────

def test_insufficient_columns_returns_error_no_records():
    # Only 1 canonical column maps — hard gate triggers
    rows = [["Date Received"], ["2016-01-01"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "InsufficientColumns"


def test_insufficient_columns_error_has_context():
    rows = [["Date Received"], ["2016-01-01"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert errors[0]["context"]["file_url"] == BASE_META["file_url"]
    assert "mapped_columns" in errors[0]["context"]


def test_partial_record_emitted_when_foi_reference_id_missing():
    # ≥2 columns map but foi_reference_id absent → partial record, no error
    rows = [["Request Details", "Date Received"], ["some request", "2016-01-01"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert errors == []
    assert results[0]["missing_columns"] == ["foi_reference_id"]


def test_partial_record_emitted_when_request_description_missing():
    # ≥2 columns map but request_description absent → partial record
    rows = [["Our Reference", "Date Received"], ["16/001", "2016-01-01"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert errors == []
    assert results[0]["missing_columns"] == ["request_description"]


def test_complete_record_has_no_missing_columns_key():
    # All required columns present → missing_columns key absent entirely
    rows = [["Our Reference", "Request Details"], ["16/001", "some request"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert errors == []
    assert "missing_columns" not in results[0]


def test_process_logs_insufficient_columns_error():
    item = {
        **BASE_META,
        "sheet_name": "Sheet1",
        "header_row_idx": 0,
        "rows": [["Date Received"], ["2016-01-01"]],
    }
    results, errors_out = [], []
    process(_make_canonicalize_input([item]), results, errors_out)
    assert results == []
    assert len(errors_out) == 1
    assert errors_out[0]["error_type"] == "InsufficientColumns"


import sys as _sys
from scripts.file_utils import read_json as _read_json, write_json as _write_json
import steps.extract_disclosures_canonicalize.process as _proc


def test_public_body_scoped_preserves_other_bodies(tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    # Existing output: prior rows for 1001 and 1002.
    _write_json(out, {"metadata": {"step": "extract_disclosures_canonicalize"}, "results": [
        {"public_body_id": 1001, "foi_reference_id": "A", "marker": "keep"},
        {"public_body_id": 1002, "foi_reference_id": "OLD", "marker": "stale"},
    ]})

    # Input has files for both bodies; only 1002 passes the filter.
    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "name": "A", "file_url": "a.xlsx", "file_type": "xlsx",
         "header_row_idx": 0, "rows": [["Our Reference", "Request Details"], ["X-001", "req A"]]},
        {"public_body_id": 1002, "name": "B", "file_url": "b.xlsx", "file_type": "xlsx",
         "header_row_idx": 0, "rows": [["Our Reference", "Request Details"], ["Y-001", "req B"]]},
    ]})

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    # 1001's prior row preserved exactly:
    assert {"public_body_id": 1001, "foi_reference_id": "A", "marker": "keep"} in results
    # 1002's stale row removed; new rows present:
    assert not any(r.get("marker") == "stale" for r in results)
    assert any(r["public_body_id"] == 1002 for r in results)
