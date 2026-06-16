import pytest
from lib.status_map import canonicalize_status, CANONICAL_STATUSES
from lib.review_status_map import canonicalize_review_status, CANONICAL_REVIEW_STATUSES


def test_status_map_importable_from_lib():
    assert "Granted" in CANONICAL_STATUSES
    assert canonicalize_status("Granted") == "Granted"
    assert canonicalize_status("Grant") == "Granted"
    assert canonicalize_status(None) is None


def test_canonical_review_statuses_list():
    assert set(CANONICAL_REVIEW_STATUSES) == {"Upheld", "Partially Upheld", "Varied", "Annulled"}


def test_upheld_canonical():
    assert canonicalize_review_status("Upheld") == "Upheld"


def test_affirmed_maps_to_upheld():
    assert canonicalize_review_status("Affirmed") == "Upheld"


def test_confirmed_maps_to_upheld():
    assert canonicalize_review_status("Confirmed") == "Upheld"


def test_partially_upheld_canonical():
    assert canonicalize_review_status("Partially Upheld") == "Partially Upheld"


def test_partially_overturned_maps_to_partially_upheld():
    assert canonicalize_review_status("Partially Overturned") == "Partially Upheld"


def test_partially_varied_maps_to_partially_upheld():
    assert canonicalize_review_status("Partially Varied") == "Partially Upheld"


def test_varied_canonical():
    assert canonicalize_review_status("Varied") == "Varied"


def test_annulled_canonical():
    assert canonicalize_review_status("Annulled") == "Annulled"


def test_review_status_case_insensitive():
    assert canonicalize_review_status("upheld") == "Upheld"
    assert canonicalize_review_status("AFFIRMED") == "Upheld"
    assert canonicalize_review_status("varied") == "Varied"


def test_review_status_none_returns_none():
    assert canonicalize_review_status(None) is None


def test_review_status_empty_returns_none():
    assert canonicalize_review_status("") is None
    assert canonicalize_review_status("   ") is None


def test_review_status_unrecognized_returns_none():
    assert canonicalize_review_status("Granted") is None
    assert canonicalize_review_status("Refused") is None
    assert canonicalize_review_status("Unknown status") is None


from steps.extract_disclosures_canonicalize_rows.process import process_records

_BASE_RECORD = {
    "public_body_id": 1006,
    "file_url": "https://assets.gov.ie/log.pdf",
    "foi_reference_id": "16/001",
    "request_description": "some request",
    "date_received": None,
    "decision_date": None,
    "requester_type": None,
    "related_request": None,
}


def _make_record(**kwargs):
    return {**_BASE_RECORD, **kwargs}


def test_upheld_reclassified_to_review_status():
    record = _make_record(decision_status="Upheld", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert results[0]["review_status"] == "Upheld"
    assert results[0]["decision_status"] is None
    assert errors == []


def test_affirmed_reclassified_to_review_status():
    record = _make_record(decision_status="Affirmed", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["review_status"] == "Upheld"
    assert results[0]["decision_status"] is None
    assert errors == []


def test_varied_reclassified_to_review_status():
    record = _make_record(decision_status="Varied", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["review_status"] == "Varied"
    assert results[0]["decision_status"] is None
    assert errors == []


def test_annulled_reclassified_to_review_status():
    record = _make_record(decision_status="Annulled", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["review_status"] == "Annulled"
    assert results[0]["decision_status"] is None
    assert errors == []


def test_reclassification_does_not_overwrite_existing_review_status():
    """When review_status is already populated, emit error and leave both unchanged."""
    record = _make_record(decision_status="Upheld", review_status="Varied")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["review_status"] == "Varied"    # not overwritten
    assert results[0]["decision_status"] == "Upheld"  # not cleared
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_reclassified_record_is_not_also_an_error():
    record = _make_record(decision_status="Affirmed", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors == []


def test_normal_canonical_status_unaffected_by_reclassification():
    """Granted/Refused etc. still canonicalize as decision_status."""
    record = _make_record(decision_status="Granted", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Granted"
    assert results[0]["review_status"] is None
    assert errors == []


# ── Error subtype enrichment tests ───────────────────────────────────────────


def test_status_value_is_requester_type_emitted_for_category():
    record = _make_record(decision_status="Category", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsRequesterType"


def test_status_value_is_requester_type_emitted_for_requester():
    record = _make_record(decision_status="Requester Type", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsRequesterType"


def test_status_value_is_column_header_emitted_for_date_received():
    record = _make_record(decision_status="Date Received", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsColumnHeader"


def test_status_value_is_column_header_emitted_for_our_ref():
    record = _make_record(decision_status="Our Ref", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsColumnHeader"


def test_status_value_is_date_emitted_for_dd_mm_yyyy():
    record = _make_record(decision_status="15/01/2023", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsDate"


def test_status_value_is_date_emitted_for_dd_dash_mm_yyyy():
    record = _make_record(decision_status="15-01-2023", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsDate"


def test_unrecognized_stays_unrecognized_for_arbitrary_value():
    record = _make_record(decision_status="Frobulated Zymurgical Request Blob", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_error_context_fields_all_present():
    record = _make_record(decision_status="15/01/2023", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    ctx = errors[0]["context"]
    assert ctx["public_body_id"] == 1006
    assert ctx["file_url"] == "https://assets.gov.ie/log.pdf"
    assert ctx["foi_reference_id"] == "16/001"
    assert ctx["raw_status"] == "15/01/2023"


def test_requester_type_check_takes_priority_over_date():
    record = _make_record(decision_status="Category", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert errors[0]["error_type"] == "StatusValueIsRequesterType"


def test_record_still_passes_through_on_subtyped_error():
    """Record is still included in results even when an error is emitted."""
    record = _make_record(decision_status="15/01/2023", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert len(errors) == 1


# ── Synonym gap fixes (root cause 1 from backlog investigation) ───────────────


def test_part_gran_maps_to_part_granted():
    """Limerick CC abbreviation PART-GRAN should canonicalize to Part-Granted."""
    record = _make_record(decision_status="PART-GRAN", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Part-Granted"
    assert errors == []


def test_part_alone_maps_to_part_granted():
    """Dept of Social Protection uses bare 'Part' to mean Part-Granted."""
    record = _make_record(decision_status="Part", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Part-Granted"
    assert errors == []


def test_queried_maps_to_unknown():
    """DCEDIY uses 'Queried' for requests where clarification was sought — outcome unknown."""
    record = _make_record(decision_status="Queried", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Unknown"
    assert errors == []


# ── Session 1: easy synonym additions ─────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ("outside of FOI", "Handled outside of FOI"),
    ("OUTSIDE OF FOI", "Handled outside of FOI"),
    ("outside of FOI Act", "Handled outside of FOI"),
    ("WITHDRA WN/OUT", "Withdrawn"),
    ("Not Valid", "Refused"),
    ("Request not Valid", "Refused"),
    ("Invalid Request", "Refused"),
])
def test_new_synonym_mappings(raw, expected):
    assert canonicalize_status(raw) == expected
