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
