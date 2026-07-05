import pytest
from lib.status_map import canonicalize_status, CANONICAL_STATUSES


def test_status_map_importable_from_lib():
    assert "Granted" in CANONICAL_STATUSES
    assert canonicalize_status("Granted") == "Granted"
    assert canonicalize_status("Grant") == "Granted"
    assert canonicalize_status(None) is None


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
    "known_issues": [],
}


def _make_record(**kwargs):
    record = {**_BASE_RECORD, **kwargs}
    # Create a new list to avoid sharing mutable state across tests
    record["known_issues"] = list(record["known_issues"])
    return record


# ── review_status values are NOT reinterpreted: error only, no silent null ────
# Decision (2026-06-25): we do not move review-status-looking values out of
# decision_status. Reinterpreting silently nulled decision_status with no error.
# Instead we leave the value in place and flag it for a human reviewer.


def test_upheld_not_reclassified_flagged_for_human():
    record = _make_record(decision_status="Upheld", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert results[0]["decision_status"] == "Upheld"   # left untouched, not nulled
    assert results[0]["review_status"] is None          # not moved
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_affirmed_not_reclassified_flagged_for_human():
    record = _make_record(decision_status="Affirmed", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Affirmed"
    assert results[0]["review_status"] is None
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_varied_not_reclassified_flagged_for_human():
    record = _make_record(decision_status="Varied", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Varied"
    assert results[0]["review_status"] is None
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_annulled_not_reclassified_flagged_for_human():
    record = _make_record(decision_status="Annulled", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["decision_status"] == "Annulled"
    assert results[0]["review_status"] is None
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_review_status_value_does_not_overwrite_existing_review_status():
    """An existing review_status is never touched; the odd decision_status is flagged."""
    record = _make_record(decision_status="Upheld", review_status="Varied")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["review_status"] == "Varied"    # not overwritten
    assert results[0]["decision_status"] == "Upheld"  # not cleared
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


def test_normal_canonical_status_still_canonicalizes():
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


def test_record_dropped_on_subtyped_error():
    """Records with confirmed contamination (StatusValueIsDate etc.) are dropped, not passed through."""
    record = _make_record(decision_status="15/01/2023", review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 0
    assert len(errors) == 1


# ── RC6: confirmed-contamination records are skipped, not passed through ──────


def test_slash_date_in_decision_status_skips_record():
    record = _make_record(decision_status="28/11/2022")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "StatusValueIsDate"


def test_two_digit_year_slash_date_skips_record():
    record = _make_record(decision_status="20/09/22")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "StatusValueIsDate"


def test_requester_type_value_in_decision_status_skips_record():
    # "Category" triggers StatusValueIsRequesterType (column-shift artefact)
    record = _make_record(decision_status="Category")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "StatusValueIsRequesterType"


def test_column_header_in_decision_status_skips_record():
    # "Decision" triggers StatusValueIsColumnHeader
    record = _make_record(decision_status="Decision")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "StatusValueIsColumnHeader"


def test_unrecognised_decision_status_still_passes_through():
    # Values that are merely unrecognised (not confirmed contamination) still pass through
    record = _make_record(decision_status="UnknownStatus")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert results[0]["decision_status"] == "UnknownStatus"
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedDecisionStatus"


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


# ── Task 1: genuine status synonym additions ────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    # Granted variants
    ("Issued", "Granted"),
    ("issued", "Granted"),
    ("G r a n t e d", "Granted"),
    ("GGrraanntteedd", "Granted"),
    ("Gtant", "Granted"),
    # Withdrawn variants
    ("Not Progressed", "Withdrawn"),
    ("sought refinement", "Withdrawn"),
    # Transferred variants
    ("RETURNED", "Transferred"),
    ("Redirected", "Transferred"),
    ("Transfered", "Transferred"),
    # Handled outside of FOI variants
    ("Information provided outside of the FOI Act.", "Handled outside of FOI"),
    ("Outside AIE", "Handled outside of FOI"),
    ("Directed to NMI website", "Handled outside of FOI"),
    ("dealt with outside of F", "Handled outside of FOI"),
    # Unknown variants
    ("In Progress", "Unknown"),
    ("Awaiting decision", "Unknown"),
    ("Active", "Unknown"),
    ("Blank Error", "Unknown"),
    # Refused variants
    ("37(1)", "Refused"),
])
def test_task1_genuine_status_synonyms(raw, expected):
    """New synonym entries: real FOI outcomes not yet in the mapping."""
    assert canonicalize_status(raw) == expected, f"Expected {raw!r} → {expected!r}"


# ── RC5: missing status synonyms ──────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Gtrant", "Granted"),
    ("S & R", "Deemed Refused"),
    ("S & R Exceed", "Deemed Refused"),
    ("Dealt with out", "Handled outside of FOI"),
    ("Ext of time", "Unknown"),
])
def test_rc5_missing_status_synonyms(raw, expected):
    """RC5: status values present in real PDFs but missing from status_map."""
    assert canonicalize_status(raw) == expected, f"Expected {raw!r} → {expected!r}"


# ── Task 2: column-header leakage reclassification ─────────────────────────

@pytest.mark.parametrize("raw,expected_error_type", [
    # requester_type headers — should become StatusValueIsRequesterType
    ("Type", "StatusValueIsRequesterType"),
    ("Cineál", "StatusValueIsRequesterType"),
    ("NON PERS", "StatusValueIsRequesterType"),
    ("Member of the", "StatusValueIsRequesterType"),
    ("Category of", "StatusValueIsRequesterType"),
    ("Catagóir on", "StatusValueIsRequesterType"),
    # decision_status / date headers — should become StatusValueIsColumnHeader
    ("Made", "StatusValueIsColumnHeader"),
    ("Dáta", "StatusValueIsColumnHeader"),
])
def test_task2_header_leakage_reclassification(raw, expected_error_type):
    """Column-header values leaked into decision_status should be classified correctly."""
    record = _make_record(decision_status=raw, review_status=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(errors) == 1, f"Expected exactly 1 error for {raw!r}"
    assert errors[0]["error_type"] == expected_error_type, (
        f"Expected {raw!r} → {expected_error_type!r}, got {errors[0]['error_type']!r}"
    )


# ── Task 3: requester_type normalisation ──────────────────────────────────────


def test_process_records_normalises_requester_type_case():
    record = _make_record(requester_type="JOURNALIST", decision_status="Granted")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["requester_type"] == "Journalist"
    assert errors == []


def test_process_records_normalises_requester_type_others():
    record = _make_record(decision_status="Granted",requester_type="Others")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["requester_type"] == "Other"
    assert errors == []


def test_process_records_normalises_non_pers():
    record = _make_record(decision_status="Granted",requester_type="NON PERS")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["requester_type"] == "Non-Personal"
    assert errors == []


def test_process_records_none_requester_type_passes_through():
    record = _make_record(decision_status="Granted",requester_type=None)
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["requester_type"] is None
    assert errors == []


def test_process_records_unknown_requester_type_logged_as_error():
    # "SU" is not in lookup — treated as unrecognised, original value passes through
    record = _make_record(decision_status="Granted",requester_type="SU")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["requester_type"] == "SU"  # original passes through
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedRequesterType"
    assert "SU" in errors[0]["error_message"]


def test_process_records_junk_requester_type_logged_as_error():
    # "Category" is not in lookup — original value passes through with error
    record = _make_record(decision_status="Granted",requester_type="Category")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert results[0]["requester_type"] == "Category"  # original passes through
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognizedRequesterType"


# ── Task 4: append value-rejection issues to known_issues ───────────────────────


def test_unrecognized_requester_type_appends_to_known_issues():
    record = _make_record(requester_type="Alien")
    results = []
    errors = []
    process_records({"results": [record]}, results, errors)
    assert results[0]["known_issues"] == [
        {"field": "requester_type", "issue_type": "UnrecognizedRequesterType", "raw_value": "Alien"}
    ]


def test_unrecognized_decision_status_appends_to_known_issues():
    record = _make_record(decision_status="Request")
    results = []
    errors = []
    process_records({"results": [record]}, results, errors)
    # "Request" is dropped entirely (StatusValueIsColumnHeader), so it lands in
    # errors_out but the record itself never reaches results_out — assert via errors.
    assert errors[0]["error_type"] == "StatusValueIsColumnHeader"


def test_unrecognized_but_kept_decision_status_appends_to_known_issues():
    # A genuinely unrecognised (not confirmed-contaminated) status is kept,
    # and its known_issues entry travels with it.
    record = _make_record(decision_status="Some Novel Status Text")
    results = []
    errors = []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert results[0]["known_issues"] == [
        {
            "field": "decision_status",
            "issue_type": "UnrecognizedDecisionStatus",
            "raw_value": "Some Novel Status Text",
        }
    ]


def test_known_issues_from_prior_step_are_preserved_alongside_new_ones():
    record = _make_record(
        requester_type="Alien",
        known_issues=[{"field": "date_received", "issue_type": "UnparseableDate", "raw_value": "32/13/2023"}],
    )
    results = []
    errors = []
    process_records({"results": [record]}, results, errors)
    assert results[0]["known_issues"] == [
        {"field": "date_received", "issue_type": "UnparseableDate", "raw_value": "32/13/2023"},
        {"field": "requester_type", "issue_type": "UnrecognizedRequesterType", "raw_value": "Alien"},
    ]


def test_na_requester_type_cleared_no_error():
    record = _make_record(requester_type="N/A")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert results[0]["requester_type"] is None
    assert not any(e["error_type"] == "UnrecognizedRequesterType" for e in errors)


def test_blank_error_requester_type_cleared_no_error():
    record = _make_record(requester_type="Blank Error")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert results[0]["requester_type"] is None
    assert errors == []


def test_unknown_requester_type_still_errors():
    record = _make_record(requester_type="Wizard")
    results, errors = [], []
    process_records({"results": [record]}, results, errors)
    assert len(results) == 1
    assert any(e["error_type"] == "UnrecognizedRequesterType" for e in errors)
