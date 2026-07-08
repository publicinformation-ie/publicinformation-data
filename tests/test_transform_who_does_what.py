from scripts.transform_who_does_what import (
    build_body_slug_lookup, build_record, transform_to_jsonld, transform_to_csv_rows,
)
from scripts.transform_public_bodies import BASE_URI


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
