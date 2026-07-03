import pytest
from lib.column_map import (
    canonicalize_header,
    canonicalize_headers,
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
    COMBINED_DATE_HEADERS,
    compute_row_id,
)


def test_combined_date_headers_contains_date_and_details():
    assert 'date and details of request received' in COMBINED_DATE_HEADERS

def test_combined_date_headers_contains_short_form():
    assert 'date and details of request' in COMBINED_DATE_HEADERS


def test_canonical_columns_order():
    assert CANONICAL_COLUMNS == [
        "foi_reference_id", "date_received", "decision_date", "requester_type",
        "decision_status", "review_status", "related_request", "request_description",
    ]


def test_required_columns():
    assert "foi_reference_id" in REQUIRED_COLUMNS
    assert "request_description" in REQUIRED_COLUMNS


def test_compute_row_id_deterministic():
    url = "https://example.ie/foi.pdf"
    assert compute_row_id(url, 5) == compute_row_id(url, 5)


def test_compute_row_id_is_12_hex_chars():
    result = compute_row_id("https://example.ie/foi.pdf", 0)
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_compute_row_id_differs_by_row_index():
    url = "https://example.ie/foi.pdf"
    assert compute_row_id(url, 1) != compute_row_id(url, 2)


def test_compute_row_id_differs_by_file_url():
    assert compute_row_id("https://example.ie/a.pdf", 1) != compute_row_id("https://example.ie/b.pdf", 1)


def test_compute_row_id_matches_golden_value():
    # Pins the exact sha1-based formula so a future refactor can't silently
    # change row_id's format while still satisfying the property tests above.
    assert compute_row_id("https://example.ie/foi.pdf", 5) == "397a0921ddc1"


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


def test_strip_iso_datetime_suffix():
    # Monaghan/Cavan PDFs embed an ISO datetime in the "Date of Decision" column header
    assert canonicalize_header("Date of Decision 2024-01-31T00:00:00") == "decision_date"
    assert canonicalize_header("Date of Decision 2023-02-13T00:00:00") == "decision_date"
    assert canonicalize_header("Date of Decision Letter 2023-01-17T00:00:00") == "decision_date"


def test_strip_iso_datetime_does_not_affect_plain_headers():
    # Ensure ISO stripping doesn't break headers without a datetime suffix
    assert canonicalize_header("Date of Decision") == "decision_date"
    assert canonicalize_header("Decision Date") == "decision_date"


# ── canonicalize_file and process() tests ─────────────────────────────────────

from steps.extract_disclosures_canonicalize.process import (
    canonicalize_file,
    process,
    STEP_NAME,
    _apply_manual_mapping,
    _load_column_mappings,
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
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/002"
    assert results[0]["request_description"] == "some request"
    assert results[0]["date_received"] == "2016-01-05"
    assert results[0]["decision_date"] is None
    assert errors == []


def test_canonicalize_file_assigns_row_id():
    rows = [
        ["Our Reference", "Request Details"],
        ["16/001", "first request"],
        ["16/002", "second request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 2
    assert results[0]["row_id"] == compute_row_id(BASE_META["file_url"], 1)
    assert results[1]["row_id"] == compute_row_id(BASE_META["file_url"], 2)
    assert results[0]["row_id"] != results[1]["row_id"]


def test_canonicalize_file_row_id_survives_a_dropped_row_in_between():
    # Row at absolute index 2 is a stray column-letter row (dropped, no record).
    # The kept row after it must still use its own absolute index (3), not a
    # renumbered index (2) as if the drop never happened.
    rows = [
        ["Our Reference", "Request Details"],
        ["16/001", "first request"],
        ["A", "B"],
        ["16/002", "second request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 2
    assert results[1]["row_id"] == compute_row_id(BASE_META["file_url"], 3)


def test_canonicalize_file_attaches_known_issues_from_date_known_issues():
    rows = [
        ["Our Reference", "Date Received"],
        ["16/001", "32/13/2023"],
    ]
    item = {
        **BASE_META,
        "rows": rows,
        "header_row_idx": 0,
        "date_known_issues": {
            "1": [{"field": "date_received", "issue_type": "UnparseableDate", "raw_value": "32/13/2023"}]
        },
    }
    results, errors, _ = canonicalize_file(item)
    assert results[0]["known_issues"] == [
        {"field": "date_received", "issue_type": "UnparseableDate", "raw_value": "32/13/2023"}
    ]


def test_canonicalize_file_known_issues_defaults_to_empty_list():
    rows = [
        ["Our Reference", "Request Details"],
        ["16/001", "first request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results[0]["known_issues"] == []


def test_canonicalize_file_includes_metadata_fields():
    rows = [["Our Reference", "Request Details"], ["16/003", "a request"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results[0]["public_body_id"] == 1001
    assert results[0]["name"] == "Dept A"
    assert results[0]["file_url"] == BASE_META["file_url"]
    assert results[0]["file_type"] == "xlsx"


def test_canonicalize_file_fills_none_for_optional_missing_columns():
    rows = [["Our Reference", "Request Details"], ["16/004", "some request"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
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
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
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
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 2


def test_canonicalize_file_insufficient_columns_when_only_one_maps():
    # Only request_description maps — fewer than 2 canonical columns → InsufficientColumns
    rows = [["Request Details"], ["some request"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "InsufficientColumns"
    assert "foi_reference_id" not in errors[0]["error_message"]  # new error type, no column list in message


def test_canonicalize_file_emits_partial_record_when_foi_ref_absent():
    # request_description + date_received map (≥2), foi_reference_id absent → partial record.
    # missing_columns now reports every unmapped canonical field, not just the required ones
    # (kept in sync with test_partial_record_emitted_when_foi_reference_id_missing below).
    rows = [["Request Details", "Date Received"], ["some request", "2016-01-01"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results != []
    assert errors == []
    assert results[0]["missing_columns"] == [
        "decision_date", "decision_status", "foi_reference_id",
        "related_request", "requester_type", "review_status",
    ]


def test_canonicalize_file_uses_header_row_idx():
    rows = [
        ["January - September 2011", None, None],
        ["FOI Reference", "Date", "Request Description"],
        ["11/001", "2011-01-15", "some request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 1})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "11/001"
    assert results[0]["request_description"] == "some request"


def test_canonicalize_file_returns_empty_for_null_rows():
    results, errors, _ = canonicalize_file({**BASE_META, "rows": None, "header_row_idx": None})
    assert results == []
    assert errors == []


def test_canonicalize_file_multiple_data_rows():
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002", "2016-01-05", "first request"],
        ["16/003", "2016-01-11", "second request"],
        ["16/004", "2016-01-12", "third request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 3
    assert results[1]["foi_reference_id"] == "16/003"


def test_canonicalize_file_row_shorter_than_headers_gets_none():
    rows = [
        ["Our Reference", "Date Rec'd", "Request Details"],
        ["16/002"],  # only 1 cell
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
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
    results, errors, _ = canonicalize_file({**BASE_META, "rows": [], "header_row_idx": 0})
    assert results == []
    assert errors == []


def test_canonicalize_file_none_header_row_idx_with_rows_returns_empty():
    rows = [["Our Reference", "Request Details"], ["16/001", "a request"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": None})
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

def test_canonicalize_number():
    assert canonicalize_header("Number") == "foi_reference_id"

def test_canonicalize_foi_file_no():
    assert canonicalize_header("FOI File No") == "foi_reference_id"


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

def test_canonicalize_request_outcome():
    assert canonicalize_header("Request Outcome") == "decision_status"


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
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "InsufficientColumns"


def test_insufficient_columns_error_has_context():
    rows = [["Date Received"], ["2016-01-01"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert errors[0]["context"]["file_url"] == BASE_META["file_url"]
    assert "mapped_columns" in errors[0]["context"]


def test_partial_record_emitted_when_foi_reference_id_missing():
    # ≥2 columns map but foi_reference_id absent → partial record, no error.
    # missing_columns now reports every unmapped canonical field, not just the
    # required ones.
    rows = [["Request Details", "Date Received"], ["some request", "2016-01-01"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert errors == []
    assert results[0]["missing_columns"] == [
        "decision_date", "decision_status", "foi_reference_id",
        "related_request", "requester_type", "review_status",
    ]


def test_partial_record_emitted_when_request_description_missing():
    # ≥2 columns map but request_description absent → partial record
    rows = [["Our Reference", "Date Received"], ["16/001", "2016-01-01"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert errors == []
    assert results[0]["missing_columns"] == [
        "decision_date", "decision_status", "related_request",
        "request_description", "requester_type", "review_status",
    ]


def test_only_required_columns_present_still_reports_other_missing_columns():
    # Both REQUIRED_COLUMNS present, but the other 5 canonical fields are
    # structurally absent from this file — missing_columns must say so.
    rows = [["Our Reference", "Request Details"], ["16/001", "some request"]]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert errors == []
    assert results[0]["missing_columns"] == [
        "date_received", "decision_date", "decision_status",
        "related_request", "requester_type", "review_status",
    ]


def test_all_canonical_columns_present_has_no_missing_columns_key():
    rows = [
        ["Our Reference", "Date Received", "Decision Date", "Category of Requester",
         "Decision", "Review Status", "Related Request", "Request Details"],
        ["16/001", "2016-01-01", "2016-02-01", "Journalist",
         "Granted", "N/A", "N/A", "some request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
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
from lib.file_utils import read_json as _read_json, write_json as _write_json
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


# ── Column swap override tests ────────────────────────────────────────────────

def test_education_from_qua_url_in_column_swaps_config():
    """The from-qua Education PDF URL must be in column_swaps.json with the correct swap pair."""
    import json
    from pathlib import Path
    swaps_path = (
        Path(__file__).parents[1]
        / "steps/extract_disclosures_canonicalize/column_swaps.json"
    )
    swaps = json.loads(swaps_path.read_text())
    url = (
        "https://assets.gov.ie/static/documents/"
        "foi-summary-of-non-personal-requests-submitted-to-the-"
        "department-of-education-from-qua.pdf"
    )
    assert url in swaps, f"URL not found in column_swaps.json: {url}"
    assert ["decision_status", "request_description"] in swaps[url]


def test_canonicalize_file_applies_column_swap():
    """Swapping decision_status ↔ request_description corrects transposed columns."""
    swaps = {BASE_META["file_url"]: [("decision_status", "request_description")]}
    rows = [
        ["Our Reference", "Request Details", "Status"],
        ["16/001", "Granted", "Records about planning"],
    ]
    item = {**BASE_META, "rows": rows, "header_row_idx": 0}
    results, errors, _ = canonicalize_file(item, column_swaps=swaps)
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["request_description"] == "Records about planning"
    assert errors == []


def test_canonicalize_file_no_swap_when_url_not_in_config():
    """Rows whose file_url is not in swaps config are unaffected."""
    swaps = {"https://other-url.example/file.xlsx": [("decision_status", "request_description")]}
    rows = [
        ["Our Reference", "Request Details", "Status"],
        ["16/001", "actual description", "Granted"],
    ]
    item = {**BASE_META, "rows": rows, "header_row_idx": 0}
    results, errors, _ = canonicalize_file(item, column_swaps=swaps)
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["request_description"] == "actual description"


def test_canonicalize_file_supports_multiple_swap_pairs():
    """Multiple swap pairs are all applied."""
    swaps = {BASE_META["file_url"]: [
        ("decision_status", "request_description"),
        ("date_received", "decision_date"),
    ]}
    rows = [
        ["Our Reference", "Request Details", "Status", "Date Received", "Decision Date"],
        ["16/001", "Granted", "Records about X", "2023-01-15", "2023-01-01"],
    ]
    item = {**BASE_META, "rows": rows, "header_row_idx": 0}
    results, errors, _ = canonicalize_file(item, column_swaps=swaps)
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["request_description"] == "Records about X"
    assert results[0]["date_received"] == "2023-01-01"
    assert results[0]["decision_date"] == "2023-01-15"


# ── Header-row detection tests ────────────────────────────────────────────────

from steps.extract_disclosures_canonicalize.process import is_header_row, _is_column_letter_row


def test_is_header_row_true_when_two_fields_match_column_headers():
    row = {
        "foi_reference_id": "Our Ref",        # matches → foi_reference_id
        "request_description": "Request",     # matches → request_description
        "decision_status": "Granted",
        "date_received": None,
        "decision_date": None,
        "requester_type": None,
        "review_status": None,
        "related_request": None,
    }
    assert is_header_row(row) is True


def test_is_header_row_false_when_only_one_field_matches():
    row = {
        "foi_reference_id": "Reference",      # matches → 1 match only
        "request_description": "Records about planning",
        "decision_status": "Granted",
        "date_received": None,
        "decision_date": None,
        "requester_type": None,
        "review_status": None,
        "related_request": None,
    }
    assert is_header_row(row) is False


def test_is_header_row_false_for_normal_data_row():
    row = {
        "foi_reference_id": "16/001",
        "request_description": "Records about planning approval",
        "decision_status": "Granted",
        "date_received": "2016-01-05",
        "decision_date": "2016-03-01",
        "requester_type": "Journalist",
        "review_status": None,
        "related_request": None,
    }
    assert is_header_row(row) is False


def test_canonicalize_file_drops_header_rows():
    rows = [
        ["Our Reference", "Request Details", "Status"],
        ["16/001", "first request", "Granted"],
        ["Our Ref", "Request", "Decision"],     # re-printed header: 2 matches → dropped
        ["16/002", "second request", "Refused"],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 2
    assert dropped == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert results[1]["foi_reference_id"] == "16/002"
    assert errors == []


def test_header_row_not_written_to_errors():
    rows = [
        ["Our Reference", "Request Details"],
        ["Our Ref", "Request"],   # 2 matches → dropped silently
        ["16/001", "first request"],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert dropped == 1
    assert errors == []


from steps.extract_disclosures_canonicalize.process import _is_repeated_header_row


def test_is_repeated_header_row_true_for_two_header_synonyms():
    row = [None, "Our reference", "Brief Description of Request", None, None,
           "Decision Granted/part granted/refused", "Date decision letter issued"]
    assert _is_repeated_header_row(row) is True


def test_is_repeated_header_row_false_for_normal_data_row():
    row = ["16/001", "some request about planning", "Granted", "2016-01-05"]
    assert _is_repeated_header_row(row) is False


def test_is_repeated_header_row_false_for_single_synonym_match():
    # Only one cell matches a known header synonym — must not false-positive.
    row = ["Our Reference", "a normal description value", "Granted"]
    assert _is_repeated_header_row(row) is False


def test_repeated_header_row_at_overflow_length_dropped_before_rlm_error():
    # Westmeath pattern: a repeated header row, corrupted by the same wrap
    # artifact that produces RowLengthMismatch, lands 4 cells longer than the
    # header. It must be dropped as a header repeat, not logged as an error.
    rows = [
        ["Date received", "Our reference", "Brief Description of Request",
         "Requester category", "Decision Granted/part granted/refused",
         "Date decision letter issued"],
        ["2024-01-05", "16/001", "some request", "Journalist", "Granted", "2024-02-01"],
        # Repeated header, corrupted to 10 cells against a 6-col header:
        [None, "Our reference", "Brief Description of Request ", None, None, None, None,
         "Requester category", "Decision Granted/part granted/refused",
         "Date decision letter issued"],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert errors == []
    assert dropped == 1


def test_repeated_header_row_at_minus_one_length_not_realigned_into_garbage():
    # Without the fix, this 5-col repeated-header row (header is 6 cols) would
    # hit Root Cause A and get silently spacer-inserted into a fabricated record.
    rows = [
        [None, "Our Reference", "Request Details", "Category", "Decision Made", "Date"],
        [None, "16/001", "some request", "Journalist", "Granted", "2024-02-01"],
        # Repeated header, one cell short of the 6-col header:
        ["Our Reference", "Request Details", "Category", "Decision Made", "Date"],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert dropped == 1


def test_repeated_header_row_at_plus_one_length_not_realigned_into_garbage():
    # Without the fix, this 7-col repeated-header row (header is 6 cols) would
    # hit Root Cause B and get silently None-stripped into a fabricated record.
    rows = [
        ["Our Reference", "Request Details", "Category", "Decision Made", "Date", "Status"],
        ["16/001", "some request", "Journalist", "Granted", "2024-02-01", "Closed"],
        # Repeated header, one cell longer than the 6-col header:
        ["Our Reference", "Request Details", None, "Category", "Decision Made", "Date", "Status"],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert dropped == 1


def test_single_matching_field_value_not_dropped():
    rows = [
        ["Our Reference", "Request Details"],
        ["Reference", "actual description of the request"],  # only 1 match
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert dropped == 0
    assert len(results) == 1


def test_process_returns_total_header_rows_dropped():
    item_with_header_row = {
        **BASE_META,
        "header_row_idx": 0,
        "rows": [
            ["Our Reference", "Request Details"],
            ["Our Ref", "Request"],   # header row → dropped
            ["16/001", "real request"],
        ],
    }
    results, errors_out = [], []
    dropped = process(_make_canonicalize_input([item_with_header_row]), results, errors_out)
    assert dropped == 1
    assert len(results) == 1


def test_canonicalize_header_trailing_slash_stripped():
    # Fingal PDFs produce 'Decision/' when pdfplumber splits a bilingual header
    assert canonicalize_header("Decision/") == "decision_status"


def test_normalize_header_strips_trailing_slash():
    from lib.text_utils import normalize_header
    assert normalize_header("Decision/") == "decision"
    assert normalize_header("Dáta Eisiúna /") == "dáta eisiúna"
    assert normalize_header("iarrthóra /") == "iarrthóra"


def test_canonicalize_bilingual_irish_english_slash():
    # Fingal Jan-Mar 2018 PDF: full Irish/English bilingual headers
    assert canonicalize_header("Uimhir thagartha/Reference Number") == "foi_reference_id"
    assert canonicalize_header("Dáta an Iarratais/Date of Request") == "date_received"
    assert canonicalize_header("Tuairisc ar Iarratais/Description of Request") == "request_description"
    assert canonicalize_header("Catagóir on iarrathóa/Requester Category") == "requester_type"
    assert canonicalize_header("Dáta Eisiúna/ Date of Release") == "decision_date"

def test_canonicalize_bilingual_slash_does_not_match_ambiguous_parts():
    # 'Grant/Refuse' — neither part is a known synonym, should return None
    assert canonicalize_header("Grant/Refuse") is None


def test_canonicalize_irish_reference_synonyms():
    assert canonicalize_header("Uimhir thagartha") == "foi_reference_id"
    assert canonicalize_header("Uimhir") == "foi_reference_id"


def test_canonicalize_irish_decision_synonyms():
    assert canonicalize_header("Cinneadh") == "decision_status"
    assert canonicalize_header("Decision Type") == "decision_status"
    assert canonicalize_header("Date decision") == "decision_status"


def test_canonicalize_irish_requester_synonyms():
    assert canonicalize_header("Catagóir") == "requester_type"
    assert canonicalize_header("iarrthóra") == "requester_type"


def test_canonicalize_irish_description_synonyms():
    assert canonicalize_header("Tuairisc ar") == "request_description"
    assert canonicalize_header("Tuairisc ar Iarrataís / Description of") == "request_description"
    assert canonicalize_header("Title (summary description)") == "request_description"
    assert canonicalize_header("Request Detail") == "request_description"


def test_canonicalize_subject_matter():
    assert canonicalize_header("Subject matter") == "request_description"


def test_canonicalize_subject_matter_of_request():
    assert canonicalize_header("Subject Matter of Request") == "request_description"


def test_canonicalize_subject_matter_nonpersonal():
    assert canonicalize_header("Subject matter of request (non-personal only)") == "request_description"


def test_canonicalize_subject_matter_nonpersonal_nospace():
    # Cork CoCo 2022 variant with non- hyphen and space
    assert canonicalize_header("Subject matter of request (non- personal only)") == "request_description"


def test_canonicalize_personal_records():
    assert canonicalize_header("Personal records") == "request_description"


def test_canonicalize_irish_date_synonyms():
    assert canonicalize_header("Dáta Eisiúna") == "decision_date"
    assert canonicalize_header("Date of Receipt") == "date_received"
    assert canonicalize_header("Date When") == "date_received"
    assert canonicalize_header("Date Outcome") == "decision_date"

def test_canonicalize_response_sent_date():
    assert canonicalize_header("Response Sent Date") == "decision_date"


def test_galway_city_2024_ocr_header_maps_to_decision_date():
    # 2024 PDF: space before "Decision" (not \n), different inner OCR spacing.
    # Without this synonym, the bilingual fallback splits on "/" and picks up
    # "decision" → decision_status, putting dates in the status column.
    assert canonicalize_header('C i n n eadh Eisithe/ Decision Made') == 'decision_date'


def test_canonicalize_irish_review_synonyms():
    assert canonicalize_header("Athbhreithniú") == "review_status"


# ── Column-letter separator row tests (RC3) ──────────────────────────────────

def test_is_column_letter_row_true_for_abc_pattern():
    # DEASP 2017 separator: [None, 'A', 'B', 'C', 'D', 'E']
    assert _is_column_letter_row([None, 'A', 'B', 'C', 'D', 'E']) is True


def test_is_column_letter_row_true_for_all_none_plus_letters():
    assert _is_column_letter_row(['A', 'B', 'C']) is True


def test_is_column_letter_row_false_for_multi_char_cell():
    # 'BC' is two characters — not a single letter
    assert _is_column_letter_row(['A', 'BC', 'D']) is False


def test_is_column_letter_row_false_for_all_none():
    assert _is_column_letter_row([None, None, None]) is False


def test_is_column_letter_row_false_for_data_row():
    assert _is_column_letter_row(['16/001', None, 'some request', None]) is False


def test_is_column_letter_row_false_for_lowercase():
    assert _is_column_letter_row(['a', 'b', 'c']) is False


def test_canonicalize_file_drops_column_letter_separator_rows():
    """DEASP 2017 pattern: [None, 'A', 'B', 'C', 'D', 'E'] rows should be silently dropped."""
    rows = [
        ["Our Reference", "Date Received", "Category", "Summary", "Decision Made", "Date of Reply"],
        [None, 'A', 'B', 'C', 'D', 'E'],    # separator — must be dropped
        ['1', '2017-01-10', 'Business', 'Records re planning', 'Granted', '2017-03-10'],
        [None, 'F', 'G', 'H', 'I', 'J'],    # another separator — must be dropped
        ['2', '2017-02-05', 'Media', 'Records re finance', 'Refused', '2017-04-05'],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 2
    assert results[0]['decision_status'] == 'Granted'
    assert results[1]['decision_status'] == 'Refused'
    assert errors == []


# ── Row-length correction tests (Root Cause A / B) ────────────────────────────

def test_duplicate_header_column_pads_short_rows():
    # Body 1012 pattern: header has duplicate 'Request Details' at positions 1 and 2.
    # Short rows (missing the duplicate) should be padded at the duplicate position,
    # not left unpadded (which would shift requester_type into decision_status).
    rows = [
        ["Our Reference", "Request Details", "Request Details", "Decision Made", "Category"],
        # 4-col row — missing the duplicate at position 2:
        ["16/001", "some request", "Granted", "Journalist"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["request_description"] == "some request"
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["requester_type"] == "Journalist"
    assert errors == []


def test_unmapped_string_header_not_used_for_padding():
    # Body 1135 pattern: header has an unmapped string column at pos 1 (Irish/partial text
    # with no synonym) AND an actual None spacer at pos 5. Short rows (missing the trailing
    # spacer) must be padded at pos 5, not pos 1 — otherwise every value shifts right by
    # one and requester_type gets the description text instead of 'Journalist'.
    rows = [
        ["Our Reference", "partial text col", "Category", "Decision Made", "Date", None],
        # 5-col row — missing the trailing None at position 5.
        # pos 1 holds the unmapped description value; pos 2 holds the requester type.
        ["16/001", "some description", "Journalist", "Granted", "01/01/2016"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["requester_type"] == "Journalist"
    assert results[0]["decision_status"] == "Granted"
    assert errors == []


def test_none_header_at_col_zero_is_silently_ignored():
    """None at column 0 (structural row-number spacer) does not break canonicalization.

    The None column is excluded from canonical_to_col_idx; data in subsequent columns
    maps normally. This is the graceful-handling guarantee for Pattern A leading-None PDFs.
    """
    rows = [
        [None, "Our Reference", "Request Details"],  # None spacer at col 0
        [1, "16/001", "some request"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert results[0]["request_description"] == "some request"
    assert errors == []


def test_long_row_with_extra_none_removes_blank_column():
    # Body 1143 pattern: some PDF pages produce a 6-col row against a 5-col header
    # because pdfplumber picks up an extra blank column. Remove the first None to
    # restore alignment so decision_status gets 'Granted' not 'Journalist'.
    rows = [
        ["Our Reference", "Request Details", "Category", "Decision Made", "Date"],
        # 6-col row — extra None at position 2:
        ["16/001", "some request", None, "Journalist", "Granted", "01/01/2016"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["requester_type"] == "Journalist"
    assert results[0]["decision_status"] == "Granted"
    assert errors == []


# ── Row-length +2 mismatch tests (RC4 — DEASP 2017 8-col shift) ──────────────

def test_row_two_longer_than_header_is_dropped_not_emitted():
    """Rows 2 cells longer than the header cannot be reliably realigned;
    they must be skipped rather than emitting a record with garbage values."""
    rows = [
        [None, "Date of Request", "Category of Requester", "Summary", "Decision Made", "Date of Reply"],
        # Normal 6-col row — must still be processed:
        [None, "01/02/2017", "Journalist", "Records about planning", "Granted", "01/04/2017"],
        # 8-col row (2 extra) — must be skipped:
        [None, "28/03/2017", None, None, "Member of the", "Notes, minutes and records", None, None],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    # Only the normal 6-col row produces a record
    assert len(results) == 1
    assert results[0]["date_received"] == "01/02/2017"
    assert results[0]["decision_status"] == "Granted"


def test_row_two_longer_emits_error():
    """Dropped ±2 rows must be logged so they're auditable."""
    rows = [
        [None, "Date of Request", "Category of Requester", "Summary", "Decision Made", "Date of Reply"],
        [None, "28/03/2017", None, None, "Member of the", "Notes, minutes", None, None],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "RowLengthMismatch"
    assert errors[0]["context"]["expected_cols"] == 6
    assert errors[0]["context"]["actual_cols"] == 8


def test_row_one_longer_still_corrected_not_dropped():
    """The existing ±1 correction must NOT be affected by the new ±2 drop logic.
    A row 1 cell longer than the header must still be corrected via None removal."""
    rows = [
        ["Our Reference", "Request Details", "Category", "Decision Made", "Date"],
        # 6-col row against 5-col header (1 extra None) — existing Root Cause B logic:
        ["16/001", "some request", None, "Journalist", "Granted", "01/01/2016"],
    ]
    results, errors, _ = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["decision_status"] == "Granted"
    assert errors == []


def test_overflow_row_with_clean_blank_collapse_recovers_record():
    # Dept. Housing 2025 Q3 pattern: a wrapped description cell injects 6 extra
    # blank columns into a 6-col header row, but all 6 real values are present
    # and in original order. Collapsing blanks must recover the record exactly.
    rows = [
        ["FOI Reference Number", "FOI Request Date Received", "Request Description",
         "Decision Date", "Decision Made", "Requester Category"],
        ["FOI-0311-2025", "2025-06-09", "a long wrapped description of the request",
         None, None, None, None, None, None, "2025-07-02", "Granted", "Journalist"],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "FOI-0311-2025"
    assert results[0]["date_received"] == "2025-06-09"
    assert results[0]["request_description"] == "a long wrapped description of the request"
    assert results[0]["decision_date"] == "2025-07-02"
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["requester_type"] == "Journalist"
    assert errors == []
    assert dropped == 0


def test_overflow_row_with_text_fragment_dropped_silently():
    # Westmeath pattern: a stray continuation of a wrapped line emitted as its
    # own pseudo-row, e.g. "...vacan" / "t" split off a neighbouring row's
    # description. Only 2 non-blank cells against a 6-col header — must be
    # dropped without emitting a misleading RowLengthMismatch error.
    rows = [
        ["Date received", "Our reference", "Brief Description of Request",
         "Requester category", "Decision Granted/part granted/refused",
         "Date decision letter issued"],
        ["2024-01-05", "16/001", "some request", "Journalist", "Granted", "2024-02-01"],
        [None, None, "currently vacan", None, None, "t", None, None, None],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert errors == []
    assert dropped == 1


def test_overflow_row_that_is_genuinely_ambiguous_still_errors():
    # Neither a clean blank-collapse (3 non-blank cells != 6-col header) nor an
    # obvious fragment (3 > 2 non-blank cells) — must keep the existing
    # log-and-drop behavior rather than guessing at alignment.
    rows = [
        [None, "Date of Request", "Category of Requester", "Summary", "Decision Made", "Date of Reply"],
        [None, "01/02/2017", "Journalist", "Records about planning", "Granted", "01/04/2017"],
        [None, "28/03/2017", None, None, "Member of the", "Notes, minutes and records", None, None],
    ]
    results, errors, dropped = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert len(results) == 1  # only the normal row
    assert len(errors) == 1
    assert errors[0]["error_type"] == "RowLengthMismatch"
    assert errors[0]["context"]["expected_cols"] == 6
    assert errors[0]["context"]["actual_cols"] == 8


# ── Meath County Council merged-header synonyms ───────────────────────────────

class TestMeathSynonyms:
    """Column names assembled by normalize_header from Meath 2016–2019 7-row PDF headers."""

    def test_meath_foi_reference_id_2018(self):
        assert canonicalize_header('Number Assigned by the Department') == 'foi_reference_id'

    def test_meath_foi_reference_id_2016(self):
        assert canonicalize_header('Reference Number Assigned by the Department') == 'foi_reference_id'

    def test_meath_date_received(self):
        assert canonicalize_header('Date of Receipt of Request in Department') == 'date_received'

    def test_meath_decision_date_2018(self):
        assert canonicalize_header('the Decision Issued to the Applicant') == 'decision_date'

    def test_meath_decision_date_2016(self):
        assert canonicalize_header('Date When the Decision Issued to the Applicant') == 'decision_date'

    def test_meath_decision_status(self):
        assert canonicalize_header('Summary of Decision') == 'decision_status'

    def test_synonyms_are_case_insensitive(self):
        assert canonicalize_header('date of receipt of request in department') == 'date_received'
        assert canonicalize_header('THE DECISION ISSUED TO THE APPLICANT') == 'decision_date'


# ── Column mapping override tests ────────────────────────────────────────────

MANUAL_META = {
    "public_body_id": 2001,
    "name": "Fingal",
    "file_url": "https://www.fingal.ie/sites/default/files/2019-03/FOI%20Disclosure%20Log%202016.pdf",
    "file_type": "pdf",
}


def test_apply_manual_mapping_basic():
    """A simple 3-column manual mapping maps cells to canonical fields."""
    mapping = {
        "source_method": "manual",
        "overridden": True,
        "column_mapping": {
            "0": "foi_reference_id",
            "1": "request_description",
            "2": "decision_status",
        },
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Description", "Status"],
            ["FOI/2016/0001", "Records about planning", "Granted"],
        ],
    }
    results, errors, dropped = _apply_manual_mapping(item, mapping)
    assert errors == []
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "FOI/2016/0001"
    assert results[0]["request_description"] == "Records about planning"
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["public_body_id"] == 2001
    assert results[0]["source_method"] == "manual"
    assert results[0]["overridden"] is True


def test_apply_manual_mapping_assigns_row_id_and_known_issues():
    mapping = {
        "source_method": "manual",
        "overridden": True,
        "column_mapping": {
            "0": "foi_reference_id",
            "1": "request_description",
            "2": "decision_status",
        },
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Description", "Status"],
            ["FOI/2016/0001", "Records about planning", "Granted"],
        ],
    }
    results, errors, dropped = _apply_manual_mapping(item, mapping)
    assert len(results) == 1
    assert results[0]["row_id"] == compute_row_id(MANUAL_META["file_url"], 1)
    assert results[0]["known_issues"] == []


def test_apply_manual_mapping_null_column_ignored():
    """A null target column is skipped; the field stays None in the record."""
    mapping = {
        "source_method": "manual",
        "overridden": True,
        "column_mapping": {
            "0": "foi_reference_id",
            "1": "request_description",
            "2": None,
        },
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Description", "Ignore"],
            ["FOI/2016/0001", "Records about planning", "should be skipped"],
        ],
    }
    results, errors, dropped = _apply_manual_mapping(item, mapping)
    assert errors == []
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "FOI/2016/0001"
    assert results[0]["request_description"] == "Records about planning"
    # col 2 mapped to None → the cell value is not assigned anywhere
    assert results[0]["decision_status"] is None


def test_apply_manual_mapping_array_target_splits_cell():
    """Array target splits cell by whitespace into multiple canonical fields."""
    mapping = {
        "source_method": "manual",
        "overridden": True,
        "column_mapping": {
            "0": ["date_received", "foi_reference_id"],
            "1": "request_description",
        },
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["DateRef", "Description"],
            ["05/01/2016 FOI/2016/0001", "Records about planning"],
        ],
    }
    results, errors, dropped = _apply_manual_mapping(item, mapping)
    assert errors == []
    assert len(results) == 1
    assert results[0]["date_received"] == "05/01/2016"
    assert results[0]["foi_reference_id"] == "FOI/2016/0001"
    assert results[0]["request_description"] == "Records about planning"


def test_apply_manual_mapping_missing_required_columns_returns_error():
    """Mapping that omits request_description returns a MissingRequiredColumns error."""
    mapping = {
        "source_method": "manual",
        "overridden": True,
        "column_mapping": {
            "0": "foi_reference_id",
            "1": "date_received",
        },
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Date"],
            ["FOI/2016/0001", "05/01/2016"],
        ],
    }
    results, errors, dropped = _apply_manual_mapping(item, mapping)
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "MissingRequiredColumns"
    assert "request_description" in errors[0]["error_message"]


def test_canonicalize_file_uses_manual_mapping_when_present():
    """canonicalize_file() delegates to _apply_manual_mapping when file_url is in column_mappings."""
    column_mappings = {
        MANUAL_META["file_url"]: {
            "source_method": "manual",
            "overridden": True,
            "column_mapping": {
                "0": "foi_reference_id",
                "1": "request_description",
            },
        }
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Description"],
            ["FOI/2016/0001", "Records about planning"],
        ],
    }
    results, errors, dropped = canonicalize_file(item, column_mappings=column_mappings)
    assert errors == []
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "FOI/2016/0001"
    assert results[0]["source_method"] == "manual"
    assert results[0]["overridden"] is True


def test_canonicalize_file_falls_back_to_auto_when_no_mapping():
    """file_url not in column_mappings → automated header-detection path is used."""
    column_mappings = {"https://other-url.ie/other.pdf": {}}
    rows = [
        ["Our Reference", "Request Details"],
        ["16/001", "some request"],
    ]
    item = {**BASE_META, "rows": rows, "header_row_idx": 0}
    results, errors, dropped = canonicalize_file(item, column_mappings=column_mappings)
    assert errors == []
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "16/001"
    assert results[0]["request_description"] == "some request"
    # Auto path does not set overridden
    assert "overridden" not in results[0]


def test_process_passes_column_mappings_to_canonicalize_file():
    """process() with a column_mappings dict applies the manual override for matching URLs."""
    column_mappings = {
        MANUAL_META["file_url"]: {
            "source_method": "manual",
            "overridden": True,
            "column_mapping": {
                "0": "foi_reference_id",
                "1": "request_description",
            },
        }
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Description"],
            ["FOI/2016/0001", "Records about planning"],
        ],
    }
    results, errors_out = [], []
    process(_make_canonicalize_input([item]), results, errors_out, column_mappings=column_mappings)
    assert errors_out == []
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "FOI/2016/0001"
    assert results[0]["source_method"] == "manual"


def test_apply_manual_mapping_row_shorter_than_mapping():
    """A data row shorter than the highest column index: missing fields stay None, no IndexError."""
    mapping = {
        "source_method": "manual",
        "overridden": True,
        "column_mapping": {
            "0": "foi_reference_id",
            "1": "request_description",
            "2": "decision_status",
        },
    }
    item = {
        **MANUAL_META,
        "header_row_idx": 0,
        "rows": [
            ["Ref", "Description", "Status"],
            ["FOI/2016/0001", "Records about planning"],  # only 2 cells — col 2 missing
        ],
    }
    results, errors, dropped = _apply_manual_mapping(item, mapping)
    assert errors == []
    assert len(results) == 1
    assert results[0]["foi_reference_id"] == "FOI/2016/0001"
    assert results[0]["request_description"] == "Records about planning"
    assert results[0]["decision_status"] is None


def test_load_column_mappings_returns_empty_when_file_missing(tmp_path):
    """When column_mappings.json does not exist, returns an empty dict."""
    result = _load_column_mappings(tmp_path)
    assert result == {}


def test_load_column_mappings_reads_file_when_present(tmp_path):
    """When column_mappings.json exists, its contents are returned."""
    import json
    data = {
        "https://example.ie/file.pdf": {
            "source_method": "manual",
            "overridden": True,
            "column_mapping": {"0": "foi_reference_id", "1": "request_description"},
        }
    }
    (tmp_path / "column_mappings.json").write_text(json.dumps(data))
    result = _load_column_mappings(tmp_path)
    assert result == data
