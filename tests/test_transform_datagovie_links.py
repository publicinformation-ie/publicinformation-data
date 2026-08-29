from scripts.transform_datagovie_links import (
    build_body_slug_lookup, build_record, transform_to_jsonld, transform_to_csv_rows,
)
from src.lib.body_refs import BASE_URI


def test_build_body_slug_lookup_maps_id_to_slug():
    public_bodies = [
        {"public_body_id": 1608, "name": "Office of the Revenue Commissioners"},
    ]
    lookup = build_body_slug_lookup(public_bodies)
    assert lookup == {1608: "office-of-the-revenue-commissioners"}


def test_build_record_shape():
    record = {
        "datagovie_slug": "an-garda-siochana",
        "datagovie_name": "An Garda Síochána",
        "datagovie_url": "https://data.gov.ie/organization/an-garda-siochana",
        "datagovie_package_count": 3,
        "public_body_id": 1608,
    }
    lookup = {1608: "office-of-the-revenue-commissioners"}
    result = build_record(record, lookup)
    assert result == {
        "@id": f"{BASE_URI}/data-gov-ie-links/an-garda-siochana",
        "@type": "dgi:DataGovIeLink",
        "public_body": f"{BASE_URI}/body/office-of-the-revenue-commissioners",
        "datagovie_slug": "an-garda-siochana",
        "datagovie_url": "https://data.gov.ie/organization/an-garda-siochana",
        "datagovie_package_count": 3,
    }


def test_build_record_raises_for_unknown_public_body_id():
    record = {
        "datagovie_slug": "x", "datagovie_name": "X",
        "datagovie_url": "https://data.gov.ie/organization/x",
        "datagovie_package_count": 0, "public_body_id": 999999,
    }
    try:
        build_record(record, {})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "999999" in str(e)


def test_transform_to_jsonld_wraps_records_in_graph():
    records = [{"@id": "https://example.ie/data-gov-ie-links/x", "@type": "dgi:DataGovIeLink"}]
    doc = transform_to_jsonld(records)
    assert doc["@graph"] == records
    assert doc["@context"]["dgi"] == f"{BASE_URI}/ns/dgi#"


def test_transform_to_csv_rows_flattens_records():
    records = [{
        "@id": f"{BASE_URI}/data-gov-ie-links/an-garda-siochana",
        "@type": "dgi:DataGovIeLink",
        "public_body": f"{BASE_URI}/body/an-garda-siochana",
        "datagovie_slug": "an-garda-siochana",
        "datagovie_url": "https://data.gov.ie/organization/an-garda-siochana",
        "datagovie_package_count": 3,
    }]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == ["id", "public_body", "datagovie_slug", "datagovie_url", "datagovie_package_count"]
    assert rows[0]["id"] == records[0]["@id"]
    assert rows[0]["datagovie_package_count"] == 3


from pathlib import Path

from scripts.transform_datagovie_links import publish
from src.lib.dataset_publish import render_jsonld, render_csv


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/data-gov-ie-links>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "data-gov-ie-links.jsonld"
    csv_path = tmp_path / "data-gov-ie-links.csv"
    ttl_path = tmp_path / "dataset-data-gov-ie-links.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"datagovie_slug": "old"}]}
    fieldnames, rows = ["id", "datagovie_slug"], [{"id": "1", "datagovie_slug": "old"}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "data-gov-ie-links.jsonld"
    csv_path = tmp_path / "data-gov-ie-links.csv"
    ttl_path = tmp_path / "dataset-data-gov-ie-links.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"datagovie_slug": "same"}]}
    fieldnames, rows = ["id", "datagovie_slug"], [{"id": "1", "datagovie_slug": "same"}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()
