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
