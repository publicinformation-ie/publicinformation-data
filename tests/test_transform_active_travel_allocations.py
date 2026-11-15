import json
from pathlib import Path

import pytest

from scripts.transform_active_travel_allocations import (
    CSV_FIELDNAMES, build_record, mirror_to_latest, publish,
    transform_to_csv_rows, transform_to_jsonld,
)
from src.lib.body_refs import BASE_URI
from src.lib.dataset_publish import render_csv, render_jsonld

import scripts.transform_active_travel_allocations as transform

SLUG_LOOKUP = {1876: "wicklow-county-council", 1085: "carlow-county-council"}


def _allocation():
    return {
        "@id": f"{BASE_URI}/allocation/wicklow-county-council/2026/active_travel/wcc-25-0003",
        "@type": "Allocation",
        "year": 2026,
        "public_body": f"{BASE_URI}/body/wicklow-county-council",
        "public_body_id": 1876,
        "recipient_name": "Wicklow County Council",
        "funding_stream": "active_travel",
        "project_code": "WCC/25/0003",
        "project_code_provisional": False,
        "project_name": "Vale Road Pedestrian Improvement Scheme, Arklow",
        "allocation_eur": 350000,
        "source_document_url": "https://www.nationaltransport.ie/x.pdf",
        "source_document_sha256": "a" * 64,
        "source_page": 22,
    }


def test_build_record_publishes_the_fixed_field_set():
    record = build_record(_allocation(), SLUG_LOOKUP)
    assert record == _allocation()


def test_build_record_omits_the_body_link_for_a_non_local_authority():
    allocation = _allocation()
    allocation.update(public_body=None, public_body_id=None,
                      recipient_name="Campuses, Hospitals, Educational Institutions and Others")
    record = build_record(allocation, SLUG_LOOKUP)
    assert "public_body" not in record
    assert "public_body_id" not in record
    assert record["recipient_name"].startswith("Campuses")


def test_build_record_rejects_a_body_uri_that_does_not_match_the_permanent_slug():
    allocation = _allocation()
    allocation["public_body"] = f"{BASE_URI}/body/wicklow"
    with pytest.raises(ValueError) as excinfo:
        build_record(allocation, SLUG_LOOKUP)
    assert "permanent slug" in str(excinfo.value)


def test_build_record_rejects_an_unknown_public_body_id():
    allocation = _allocation()
    allocation["public_body_id"] = 9999
    with pytest.raises(ValueError) as excinfo:
        build_record(allocation, SLUG_LOOKUP)
    assert "9999" in str(excinfo.value)


def test_build_record_rejects_a_body_link_without_an_id():
    allocation = _allocation()
    allocation["public_body_id"] = None
    with pytest.raises(ValueError):
        build_record(allocation, SLUG_LOOKUP)


def test_transform_to_jsonld_wraps_records_in_a_graph():
    records = [build_record(_allocation(), SLUG_LOOKUP)]
    document = transform_to_jsonld(records)
    assert document["@graph"] == records
    assert document["@context"]["ata"] == f"{BASE_URI}/ns/active-travel#"
    assert document["@context"]["public_body"]["@type"] == "@id"


def test_transform_to_csv_rows_uses_the_published_columns():
    records = [build_record(_allocation(), SLUG_LOOKUP)]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == CSV_FIELDNAMES
    assert rows[0]["id"] == records[0]["@id"]
    assert rows[0]["public_body_id"] == 1876
    # CSVW's boolean lexical space is lowercase, matching public-bodies.csv.
    assert rows[0]["project_code_provisional"] == "false"


def test_transform_to_csv_rows_writes_a_true_flag_as_lowercase():
    allocation = _allocation()
    allocation.update(project_code="WCC/26/XXXX", project_code_provisional=True)
    _, rows = transform_to_csv_rows([build_record(allocation, SLUG_LOOKUP)])
    assert rows[0]["project_code_provisional"] == "true"


def test_transform_to_csv_rows_leaves_the_body_columns_empty_for_other_recipients():
    allocation = _allocation()
    allocation.update(public_body=None, public_body_id=None)
    records = [build_record(allocation, SLUG_LOOKUP)]
    _, rows = transform_to_csv_rows(records)
    assert rows[0]["public_body"] == ""
    assert rows[0]["public_body_id"] == ""


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix dcat: <http://www.w3.org/ns/dcat#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/active-travel-allocations>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_payloads_and_stamps_the_catalogue_on_change(tmp_path):
    jsonld_path = tmp_path / "a.jsonld"
    csv_path = tmp_path / "a.csv"
    ttl_path = tmp_path / "dataset.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    document = {"@graph": [{"@id": "1"}]}
    rows = [{"id": "1"}]

    changed = publish(document, ["id"], rows, jsonld_path=jsonld_path,
                      csv_path=csv_path, ttl_path=ttl_path)

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(document)
    assert csv_path.read_bytes() == render_csv(["id"], rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_a_no_op_when_the_content_is_identical(tmp_path):
    jsonld_path = tmp_path / "a.jsonld"
    csv_path = tmp_path / "a.csv"
    ttl_path = tmp_path / "dataset.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    document = {"@graph": [{"@id": "1"}]}
    rows = [{"id": "1"}]
    jsonld_path.write_bytes(render_jsonld(document))
    csv_path.write_bytes(render_csv(["id"], rows))

    changed = publish(document, ["id"], rows, jsonld_path=jsonld_path,
                      csv_path=csv_path, ttl_path=ttl_path)

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()


def test_latest_mirrors_the_versioned_directory_byte_for_byte(tmp_path, monkeypatch):
    versioned = tmp_path / "v1.0.0"
    latest = tmp_path / "latest"
    versioned.mkdir()
    (versioned / "a.jsonld").write_bytes(b'{"@graph": []}')
    (versioned / "README.md").write_text("# readme")
    monkeypatch.setattr(transform, "OUTPUT_DIR", str(versioned))
    monkeypatch.setattr(transform, "LATEST_DIR", str(latest))

    assert mirror_to_latest() is True
    for name in ("a.jsonld", "README.md"):
        assert (latest / name).read_bytes() == (versioned / name).read_bytes()

    # A second pass with unchanged content writes nothing at all.
    before = {name: (latest / name).stat().st_mtime_ns for name in ("a.jsonld", "README.md")}
    assert mirror_to_latest() is False
    assert {name: (latest / name).stat().st_mtime_ns for name in before} == before
