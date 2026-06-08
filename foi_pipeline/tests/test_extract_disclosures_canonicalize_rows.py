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
