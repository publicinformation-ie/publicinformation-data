from scripts.transform_who_does_what import (
    build_body_slug_lookup, build_record, transform_to_jsonld, transform_to_csv_rows,
)
from src.lib.body_refs import BASE_URI


def test_build_body_slug_lookup_maps_id_to_slug():
    public_bodies = [
        {"public_body_id": 1608, "name": "Office of the Revenue Commissioners"},
        {"public_body_id": 1651, "name": "Public Appointments Service"},
    ]
    lookup = build_body_slug_lookup(public_bodies)
    assert lookup == {
        1608: "office-of-the-revenue-commissioners",
        1651: "public-appointments-service",
    }


def test_build_record_shape():
    wdw_record = {
        "wdw_name": "Revenue Commissioners",
        "wdw_url": "https://www.gov.ie/en/office-of-the-revenue-commissioners/organisation-information/revenue-commissioners-who-does-what/",
        "wdw_slug": "office-of-the-revenue-commissioners",
        "public_body_id": 1608,
    }
    lookup = {1608: "office-of-the-revenue-commissioners"}
    record = build_record(wdw_record, lookup)
    assert record == {
        "@id": f"{BASE_URI}/who-does-what/office-of-the-revenue-commissioners",
        "@type": "wdw:WhoDoesWhatLink",
        "public_body": f"{BASE_URI}/body/office-of-the-revenue-commissioners",
        "wdw_slug": "office-of-the-revenue-commissioners",
        "wdw_url": "https://www.gov.ie/en/office-of-the-revenue-commissioners/organisation-information/revenue-commissioners-who-does-what/",
    }


def test_build_record_raises_for_unknown_public_body_id():
    wdw_record = {
        "wdw_name": "X", "wdw_url": "https://example.ie/x/",
        "wdw_slug": "x", "public_body_id": 999999,
    }
    try:
        build_record(wdw_record, {})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "999999" in str(e)


def test_transform_to_jsonld_wraps_records_in_graph():
    records = [{"@id": "https://example.ie/who-does-what/x", "@type": "wdw:WhoDoesWhatLink"}]
    doc = transform_to_jsonld(records)
    assert doc["@graph"] == records
    assert doc["@context"]["wdw"] == f"{BASE_URI}/ns/wdw#"


def test_transform_to_csv_rows_flattens_records():
    records = [{
        "@id": f"{BASE_URI}/who-does-what/office-of-the-revenue-commissioners",
        "@type": "wdw:WhoDoesWhatLink",
        "public_body": f"{BASE_URI}/body/office-of-the-revenue-commissioners",
        "wdw_slug": "office-of-the-revenue-commissioners",
        "wdw_url": "https://www.gov.ie/en/office-of-the-revenue-commissioners/organisation-information/revenue-commissioners-who-does-what/",
    }]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == ["id", "public_body", "wdw_slug", "wdw_url"]
    assert rows[0]["id"] == records[0]["@id"]
    assert rows[0]["wdw_slug"] == "office-of-the-revenue-commissioners"


from pathlib import Path

from scripts.transform_who_does_what import publish
from src.lib.dataset_publish import render_jsonld, render_csv


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/who-does-what>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "who-does-what.jsonld"
    csv_path = tmp_path / "who-does-what.csv"
    ttl_path = tmp_path / "dataset-who-does-what.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"wdw_slug": "old"}]}
    fieldnames, rows = ["id", "wdw_slug"], [{"id": "1", "wdw_slug": "old"}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "who-does-what.jsonld"
    csv_path = tmp_path / "who-does-what.csv"
    ttl_path = tmp_path / "dataset-who-does-what.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"wdw_slug": "same"}]}
    fieldnames, rows = ["id", "wdw_slug"], [{"id": "1", "wdw_slug": "same"}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()
