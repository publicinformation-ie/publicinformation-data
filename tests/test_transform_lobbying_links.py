from pathlib import Path

from scripts.transform_lobbying_links import (
    build_body_slug_lookup, build_record, transform_to_jsonld, transform_to_csv_rows, publish,
)
from scripts.transform_public_bodies import BASE_URI
from src.lib.dataset_publish import render_jsonld, render_csv


def test_build_body_slug_lookup_maps_id_to_slug():
    public_bodies = [
        {"public_body_id": 1600, "name": "Adoption Authority of Ireland"},
    ]
    lookup = build_body_slug_lookup(public_bodies)
    assert lookup == {1600: "adoption-authority-of-ireland"}


def test_build_record_shape():
    record = {
        "lobbyingie_id": 1571,
        "lobbyingie_name": "Some Public Body",
        "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1571",
        "lobbyingie_returns_count": 1777,
        "public_body_id": 1600,
    }
    lookup = {1600: "some-public-body"}
    result = build_record(record, lookup)
    assert result == {
        "@id": f"{BASE_URI}/lobbying-ie-links/1571",
        "@type": "lil:LobbyingIeLink",
        "public_body": f"{BASE_URI}/body/some-public-body",
        "lobbyingie_id": 1571,
        "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1571",
        "lobbyingie_returns_count": 1777,
    }


def test_build_record_raises_for_unknown_public_body_id():
    record = {
        "lobbyingie_id": 1, "lobbyingie_name": "X",
        "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1",
        "lobbyingie_returns_count": None, "public_body_id": 999999,
    }
    try:
        build_record(record, {})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "999999" in str(e)


def test_transform_to_jsonld_wraps_records_in_graph():
    records = [{"@id": "https://example.ie/lobbying-ie-links/1", "@type": "lil:LobbyingIeLink"}]
    doc = transform_to_jsonld(records)
    assert doc["@graph"] == records
    assert doc["@context"]["lil"] == f"{BASE_URI}/ns/lil#"


def test_transform_to_csv_rows_flattens_records():
    records = [{
        "@id": f"{BASE_URI}/lobbying-ie-links/1571",
        "@type": "lil:LobbyingIeLink",
        "public_body": f"{BASE_URI}/body/some-public-body",
        "lobbyingie_id": 1571,
        "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1571",
        "lobbyingie_returns_count": 1777,
    }]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == ["id", "public_body", "lobbyingie_id", "lobbyingie_url", "lobbyingie_returns_count"]
    assert rows[0]["id"] == records[0]["@id"]
    assert rows[0]["lobbyingie_returns_count"] == 1777


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/lobbying-ie-links>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "lobbying-ie-links.jsonld"
    csv_path = tmp_path / "lobbying-ie-links.csv"
    ttl_path = tmp_path / "dataset-lobbying-ie-links.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"lobbyingie_id": 1}]}
    fieldnames, rows = ["id", "lobbyingie_id"], [{"id": "1", "lobbyingie_id": 1}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "lobbying-ie-links.jsonld"
    csv_path = tmp_path / "lobbying-ie-links.csv"
    ttl_path = tmp_path / "dataset-lobbying-ie-links.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"lobbyingie_id": 1}]}
    fieldnames, rows = ["id", "lobbyingie_id"], [{"id": "1", "lobbyingie_id": 1}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()
