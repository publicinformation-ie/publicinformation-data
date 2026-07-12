from scripts.transform_datagovie_links import (
    build_body_slug_lookup, build_record, transform_to_jsonld, transform_to_csv_rows,
)
from scripts.transform_public_bodies import BASE_URI


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
