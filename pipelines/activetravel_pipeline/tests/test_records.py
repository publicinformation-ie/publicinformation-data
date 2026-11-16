"""Record identity and the fixed published field set."""
import pytest

from allocations import is_provisional_code
from steps.canonicalize_allocations.process import identity_key, run as canonicalize_run
from steps.export_allocations.process import RECORD_FIELDS, run as export_run

BASE = "https://data.publicinformation.ie/allocation"


def _row(code: str, name: str, amount: int, *, year: int = 2026, page: int = 1,
         row_index: int = 0, stream: str = "active_travel") -> dict:
    return {
        "document_id": f"nta-active-travel-{year}", "year": year, "page": page,
        "row_index": row_index, "part": "project_table", "cells": [code, name, str(amount)],
        "kind": "project", "detail": {"code": code, "name": name},
        "amount_eur": amount, "section_id": "section", "block_index": 0,
        "funding_stream": stream, "recipient_name": "Wicklow County Council",
        "recipient_kind": "local_authority", "recipient_slug": "wicklow-county-council",
        "public_body_id": 1876,
        "public_body": "https://data.publicinformation.ie/body/wicklow-county-council",
    }


def _documents(year: int = 2026) -> list[dict]:
    return [{"document_id": f"nta-active-travel-{year}", "year": year,
             "url": f"https://example.ie/{year}.pdf", "sha256": "a" * 64,
             "kinds": ["project_table"]}]


def test_identity_key_of_a_real_code_collapses_punctuation():
    assert identity_key("CW/21/0001", "Any name") == "cw-21-0001"
    assert identity_key("TU DUBLIN", "Cycle Parking") == "tu-dublin"


def test_identity_key_of_a_provisional_code_is_the_project_name():
    assert is_provisional_code("WCC/26/XXXX")
    assert is_provisional_code("DCC/25/00xx")
    assert identity_key("WCC/26/XXXX", "Vale Road Pedestrian Improvement Scheme, Arklow") == (
        "vale-road-pedestrian-improvement-scheme-arklow")


def test_a_canonical_record_carries_the_identity_grammar():
    output, errors = canonicalize_run({
        "rows": [_row("WCC/25/0003", "Vale Road Pedestrian Improvement Scheme, Arklow", 350000)],
        "documents": _documents(),
    })
    record = output["results"][0]
    assert record["@id"] == f"{BASE}/wicklow-county-council/2026/active_travel/wcc-25-0003"
    assert record["project_code_provisional"] is False
    assert errors == []


def test_two_provisional_rows_with_the_same_placeholder_get_distinct_ids():
    rows = [
        _row("WCC/26/XXXX", "Arklow MD Junction Tightening Works", 200000, row_index=0),
        _row("WCC/26/XXXX", "Arklow MD Permeability Links", 250000, row_index=1),
    ]
    output, _ = canonicalize_run({"rows": rows, "documents": _documents()})
    ids = [record["@id"] for record in output["results"]]
    assert len(set(ids)) == 2
    assert ids[0].endswith("/arklow-md-junction-tightening-works")
    assert ids[1].endswith("/arklow-md-permeability-links")
    assert all(record["project_code_provisional"] for record in output["results"])


def test_the_same_code_in_two_years_is_two_records_with_two_ids():
    rows = [_row("WCC/25/0003", "Vale Road", 350000, year=2025, page=22),
            _row("WCC/25/0003", "Vale Road", 200000, year=2026, page=22)]
    documents = _documents(2025) + _documents(2026)
    output, _ = canonicalize_run({"rows": rows, "documents": documents})
    ids = [record["@id"] for record in output["results"]]
    assert ids == [
        f"{BASE}/wicklow-county-council/2025/active_travel/wcc-25-0003",
        f"{BASE}/wicklow-county-council/2026/active_travel/wcc-25-0003",
    ]


def test_a_repeated_real_code_is_suffixed_in_document_order():
    rows = [
        _row("NTA/15/0001", "Regional Bikes operating costs", 1500000, row_index=0),
        _row("NTA/15/0001", "Regional Bikes Capital Costs", 1500000, row_index=1),
    ]
    output, _ = canonicalize_run({"rows": rows, "documents": _documents()})
    ids = [record["@id"] for record in output["results"]]
    assert ids[0].endswith("/nta-15-0001")
    assert ids[1].endswith("/nta-15-0001-2")


def test_an_identical_duplicate_row_is_dropped_and_reported():
    row = _row("WCC/25/0003", "Vale Road", 350000, row_index=0)
    output, _ = canonicalize_run({"rows": [row, {**row, "row_index": 1}],
                                  "documents": _documents()})
    assert len(output["results"]) == 1
    assert output["metadata"]["duplicates_dropped"] == 1
    assert output["duplicates"][0]["kept_page"] == 1


def test_a_local_authority_without_a_public_body_is_fatal():
    row = _row("WCC/25/0003", "Vale Road", 350000)
    row["public_body_id"] = None
    with pytest.raises(ValueError) as excinfo:
        canonicalize_run({"rows": [row], "documents": _documents()})
    assert "no public body" in str(excinfo.value)


def test_the_exported_record_matches_the_fixed_field_set():
    row = _row("WCC/25/0003", "Vale Road Pedestrian Improvement Scheme, Arklow", 350000, page=22)
    row["@id"] = f"{BASE}/wicklow-county-council/2026/active_travel/wcc-25-0003"
    row["project_code"] = row["detail"]["code"]
    row["project_name"] = row["detail"]["name"]
    row["project_code_provisional"] = False
    output, errors = export_run({"results": [row], "documents": _documents()})
    assert errors == []
    record = output["results"][0]
    assert tuple(record) == RECORD_FIELDS
    assert record["@type"] == "Allocation"
    assert record["year"] == 2026
    assert record["allocation_eur"] == 350000
    assert record["source_page"] == 22
    assert record["source_document_url"] == "https://example.ie/2026.pdf"
    assert record["source_document_sha256"] == "a" * 64
    assert all(record[field] is not None for field in RECORD_FIELDS
               if field not in ("public_body", "public_body_id"))


def test_a_non_local_authority_record_has_no_body_link():
    row = _row("TCD/17/0001", "Cycle Parking", 50000)
    row.update(recipient_name="Campuses, Hospitals, Educational Institutions and Others",
               recipient_kind="other", recipient_slug="campuses", public_body_id=None,
               public_body=None,
               project_code="TCD/17/0001", project_name="Cycle Parking",
               project_code_provisional=False)
    row["@id"] = f"{BASE}/campuses/2026/active_travel/tcd-17-0001"
    output, _ = export_run({"results": [row], "documents": _documents()})
    record = output["results"][0]
    assert record["public_body"] is None
    assert record["public_body_id"] is None
    assert record["recipient_name"].startswith("Campuses")


def test_counts_by_year_add_up():
    rows = [
        _row("WCC/25/0003", "A", 100, row_index=0),
        _row("WCC/25/0004", "B", 200, row_index=1),
        _row("WCC/25/0005", "C", 300, row_index=2, stream="other_nta_streams"),
    ]
    for row in rows:
        row["@id"] = f"{BASE}/wicklow-county-council/2026/{row['funding_stream']}/x"
        row["project_code"] = row["detail"]["code"]
        row["project_name"] = row["detail"]["name"]
        row["project_code_provisional"] = False
    output, _ = export_run({"results": rows, "documents": _documents()})
    counts = output["metadata"]["counts_by_year"]["2026"]
    assert counts["records"] == 3
    assert counts["allocations_eur"] == 600
    assert counts["active_travel_eur"] == 300
    assert counts["other_nta_streams_eur"] == 300
