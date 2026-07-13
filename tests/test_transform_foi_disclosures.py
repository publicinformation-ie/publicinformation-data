import pytest
from scripts.transform_foi_disclosures import (
    build_record,
    compute_disclosure_id,
    transform_to_jsonld,
    transform_to_csv_rows,
    DATASET_VERSION,
)
from scripts.lib.body_refs import BASE_URI


# Real pipeline records have no row_id field, and file_url is not unique
# per record (many disclosure rows share one source file) — the id is
# derived from (file_url, row_index) instead. See compute_disclosure_id().
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
    "known_issues": [],
    "missing_columns": ["foi_reference_id", "related_request", "review_status"],
}

EXPECTED_ID = compute_disclosure_id(SAMPLE_DISCLOSURE["file_url"], 0)


def test_build_record_happy_path():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"}, row_index=0)
    assert record["@id"] == f"{BASE_URI}/foi-disclosure/{EXPECTED_ID}"
    assert record["@type"] == "foi:FoiDisclosure"
    assert record["public_body"] == f"{BASE_URI}/body/bord-bia"
    assert record["name"] == "Bord Bia"
    assert record["file_url"] == SAMPLE_DISCLOSURE["file_url"]
    assert record["file_type"] == "pdf"
    assert record["known_issues"] == []
    assert record["missing_columns"] == ["foi_reference_id", "related_request", "review_status"]


def test_build_record_omits_null_fields():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"}, row_index=0)
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
        build_record(SAMPLE_DISCLOSURE, body_slug_lookup={}, row_index=0)


def test_build_record_different_row_index_yields_different_id():
    record_a = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"}, row_index=0)
    record_b = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"}, row_index=1)
    assert record_a["@id"] != record_b["@id"]


def test_transform_to_jsonld_includes_version_and_graph():
    records = [build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"}, row_index=0)]
    doc = transform_to_jsonld(records)
    assert doc["version"] == DATASET_VERSION
    assert doc["@graph"] == records
    assert doc["@context"]["public_body"] == {"@id": "foi:publicBody", "@type": "@id"}


def test_transform_to_csv_rows_flattens_arrays_with_pipe_delimiter():
    disclosure = dict(SAMPLE_DISCLOSURE)
    disclosure["known_issues"] = ["ocr_low_confidence", "misaligned_row"]
    record = build_record(disclosure, {1052: "bord-bia"}, row_index=0)
    fieldnames, rows = transform_to_csv_rows([record])
    row = rows[0]
    assert row["known_issues"] == "ocr_low_confidence|misaligned_row"
    assert row["missing_columns"] == "foi_reference_id|related_request|review_status"


def test_transform_to_csv_rows_empty_string_for_null_fields():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"}, row_index=0)
    fieldnames, rows = transform_to_csv_rows([record])
    row = rows[0]
    assert row["foi_reference_id"] == ""
    assert row["review_status"] == ""
    assert row["related_request"] == ""
    assert row["decision_date"] == "2019-01-15"


from pathlib import Path

from scripts.transform_foi_disclosures import publish
from src.lib.dataset_publish import render_jsonld, render_csv


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/foi-disclosures>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "foi-disclosures.jsonld"
    csv_path = tmp_path / "foi-disclosures.csv"
    ttl_path = tmp_path / "dataset-foi-disclosures.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"version": "1.0.0", "@graph": [{"name": "old"}]}
    fieldnames, rows = ["id", "name"], [{"id": "1", "name": "old"}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "foi-disclosures.jsonld"
    csv_path = tmp_path / "foi-disclosures.csv"
    ttl_path = tmp_path / "dataset-foi-disclosures.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"version": "1.0.0", "@graph": [{"name": "same"}]}
    fieldnames, rows = ["id", "name"], [{"id": "1", "name": "same"}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()
