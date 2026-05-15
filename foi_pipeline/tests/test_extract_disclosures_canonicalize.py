import pytest
from steps.extract_disclosures_canonicalize.column_map import (
    canonicalize_header,
    canonicalize_headers,
    CANONICAL_COLUMNS,
    REQUIRED_COLUMNS,
)


def test_canonical_columns_order():
    assert CANONICAL_COLUMNS == [
        "foi_reference_id", "decision_date", "requester_type",
        "decision_status", "review_status", "related_request", "request_description",
    ]


def test_required_columns():
    assert "foi_reference_id" in REQUIRED_COLUMNS
    assert "request_description" in REQUIRED_COLUMNS


def test_canonicalize_our_reference():
    assert canonicalize_header("Our Reference") == "foi_reference_id"


def test_canonicalize_date_recd():
    assert canonicalize_header("Date Rec'd") == "decision_date"


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
        "Date Rec'd": "decision_date",
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
    assert results[0]["decision_date"] == "2016-01-05"
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


def test_canonicalize_file_returns_error_when_required_column_missing():
    rows = [["Request Details"], ["some request"]]
    results, errors = canonicalize_file({**BASE_META, "rows": rows, "header_row_idx": 0})
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "MissingRequiredColumns"
    assert "foi_reference_id" in errors[0]["error_message"]


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
    assert errors_out[0]["error_type"] == "MissingRequiredColumns"


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
