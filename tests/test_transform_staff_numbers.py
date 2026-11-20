import pytest

from scripts.transform_staff_numbers import (
    CSV_FIELDS, build_record, build_records, transform_to_csv_rows, transform_to_jsonld,
)
from src.lib.body_refs import BASE_URI

LOOKUP = {1600: "adoption-authority-of-ireland"}


def src(**kw):
    base = {"source_key": "Civil Service | Finance", "source_name": "Finance", "year": 2025, "quarter": 4,
            "level_2": "Finance", "level_4": "Civil Service", "fte": 410.4,
            "public_body_id": 1600, "match_status": "override"}
    return {**base, **kw}


def test_linked_record_shape():
    r = build_record(src(), LOOKUP)
    assert r["@id"] == f"{BASE_URI}/staff-numbers/2025-q4/civil-service-finance"
    assert r["public_body"] == f"{BASE_URI}/body/adoption-authority-of-ireland"
    assert r["@type"] == "sn:StaffNumbersRecord" and r["fte"] == 410.4


def test_unmatched_record_keeps_row_with_null_body():
    r = build_record(src(public_body_id=None, match_status="unmatched"), LOOKUP)
    assert r["public_body"] is None


def test_unknown_body_aborts():
    with pytest.raises(ValueError, match="Unknown public_body_id"):
        build_record(src(public_body_id=1), LOOKUP)


@pytest.mark.parametrize("kw", [{"match_status": "fuzzy"},
                                {"match_status": "unmatched"},
                                {"public_body_id": None}])
def test_inconsistent_status_aborts(kw):
    with pytest.raises(ValueError):
        build_record(src(**kw), LOOKUP)


def test_duplicate_id_aborts():
    with pytest.raises(ValueError, match="Duplicate"):
        build_records([src(), src()], LOOKUP)


def test_csv_blank_for_null_and_jsonld_wraps_graph():
    recs = build_records([src(public_body_id=None, match_status="unmatched", fte=None)], LOOKUP)
    fields, rows = transform_to_csv_rows(recs)
    assert fields == CSV_FIELDS and rows[0]["public_body"] == "" and rows[0]["fte"] == ""
    assert transform_to_jsonld(recs)["@graph"] == recs
