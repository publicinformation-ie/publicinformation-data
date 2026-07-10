import pytest
from scripts.transform_foi_disclosures import (
    build_record,
    transform_to_jsonld,
    transform_to_csv_rows,
    DATASET_VERSION,
)
from scripts.lib.body_refs import BASE_URI


SAMPLE_DISCLOSURE = {
    "public_body_id": 1052,
    "name": "Bord Bia",
    "file_url": "https://www.bordbia.ie/foi-disclosure-log-2019.pdf",
    "file_type": "pdf",
    "foi_reference_id": None,
    "date_received": "2019-01-02",
    "decision_date": "2019-01-15",
    "requester_type": "Journalist",
    "decision_status": "Granted",
    "review_status": None,
    "related_request": None,
    "request_description": "Total amount spent on bottled water in 2017 and 2018.",
    "row_id": "f292642e7af3",
    "known_issues": [],
    "missing_columns": ["foi_reference_id", "related_request", "review_status"],
}


def test_build_record_happy_path():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    assert record["@id"] == f"{BASE_URI}/foi-disclosure/f292642e7af3"
    assert record["@type"] == "foi:FoiDisclosure"
    assert record["public_body"] == f"{BASE_URI}/body/bord-bia"
    assert record["name"] == "Bord Bia"
    assert record["file_url"] == SAMPLE_DISCLOSURE["file_url"]
    assert record["file_type"] == "pdf"
    assert record["known_issues"] == []
    assert record["missing_columns"] == ["foi_reference_id", "related_request", "review_status"]


def test_build_record_omits_null_fields():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    assert "foi_reference_id" not in record
    assert "review_status" not in record
    assert "related_request" not in record
    assert record["decision_date"] == "2019-01-15"
    assert record["requester_type"] == "Journalist"
    assert record["decision_status"] == "Granted"
    assert record["date_received"] == "2019-01-02"
    assert record["request_description"] == SAMPLE_DISCLOSURE["request_description"]


def test_build_record_unknown_public_body_id_raises():
    with pytest.raises(ValueError, match="Unknown public_body_id"):
        build_record(SAMPLE_DISCLOSURE, body_slug_lookup={})


def test_transform_to_jsonld_includes_version_and_graph():
    records = [build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})]
    doc = transform_to_jsonld(records)
    assert doc["version"] == DATASET_VERSION
    assert doc["@graph"] == records
    assert doc["@context"]["public_body"] == {"@id": "foi:publicBody", "@type": "@id"}


def test_transform_to_csv_rows_flattens_arrays_with_pipe_delimiter():
    disclosure = dict(SAMPLE_DISCLOSURE)
    disclosure["known_issues"] = ["ocr_low_confidence", "misaligned_row"]
    record = build_record(disclosure, {1052: "bord-bia"})
    fieldnames, rows = transform_to_csv_rows([record])
    row = rows[0]
    assert row["known_issues"] == "ocr_low_confidence|misaligned_row"
    assert row["missing_columns"] == "foi_reference_id|related_request|review_status"


def test_transform_to_csv_rows_empty_string_for_null_fields():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    fieldnames, rows = transform_to_csv_rows([record])
    row = rows[0]
    assert row["foi_reference_id"] == ""
    assert row["review_status"] == ""
    assert row["related_request"] == ""
    assert row["decision_date"] == "2019-01-15"
