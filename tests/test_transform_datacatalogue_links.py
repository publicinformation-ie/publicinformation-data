from pathlib import Path

import pytest

from scripts.transform_datacatalogue_links import (
    CSV_FIELDNAMES, build_record, publish, transform_to_csv_rows, transform_to_jsonld,
)
from src.lib.body_refs import BASE_URI
from src.lib.dataset_publish import render_csv, render_jsonld

LOOKUP = {1608: "office-of-the-revenue-commissioners"}

RECORD = {
    "datacatalogue_slug": "revenue-commissioners",
    "datacatalogue_name": "Revenue Commissioners",
    "datacatalogue_url": "https://datacatalogue.gov.ie/organization/revenue-commissioners",
    "datacatalogue_package_count": 12,
    "datacatalogue_description": "The Revenue Commissioners collect taxes and duties.",
    "public_body_id": 1608,
}


def test_build_record_shape():
    result = build_record(RECORD, LOOKUP)
    assert result == {
        "@id": f"{BASE_URI}/datacatalogue-gov-ie-links/revenue-commissioners",
        "@type": "dcl:DataCatalogueLink",
        "public_body": f"{BASE_URI}/body/office-of-the-revenue-commissioners",
        "datacatalogue_slug": "revenue-commissioners",
        "datacatalogue_name": "Revenue Commissioners",
        "datacatalogue_url": "https://datacatalogue.gov.ie/organization/revenue-commissioners",
        "datacatalogue_package_count": 12,
        "datacatalogue_description": "The Revenue Commissioners collect taxes and duties.",
    }


def test_build_record_omits_count_and_description_the_source_did_not_provide():
    record = {**RECORD, "datacatalogue_package_count": None, "datacatalogue_description": ""}
    result = build_record(record, LOOKUP)
    assert "datacatalogue_package_count" not in result
    assert "datacatalogue_description" not in result


def test_build_record_raises_for_unknown_public_body_id():
    record = {**RECORD, "public_body_id": 999999}
    with pytest.raises(ValueError, match="999999"):
        build_record(record, LOOKUP)


def test_build_record_uses_the_seeded_body_slug_verbatim():
    "SEED: a diacritic name keeps its published slug rather than a fresh slugify()."
    result = build_record({**RECORD, "public_body_id": 1010}, {1010: "an-coimisiun-pleanala"})
    assert result["public_body"] == f"{BASE_URI}/body/an-coimisiun-pleanala"


def test_transform_to_jsonld_wraps_records_in_graph():
    records = [{"@id": f"{BASE_URI}/datacatalogue-gov-ie-links/x", "@type": "dcl:DataCatalogueLink"}]
    doc = transform_to_jsonld(records)
    assert doc["@graph"] == records
    assert doc["@context"]["dcl"] == f"{BASE_URI}/ns/dcl#"


def test_transform_to_csv_rows_flattens_records():
    built = build_record(RECORD, LOOKUP)
    fieldnames, rows = transform_to_csv_rows([built])
    assert fieldnames == CSV_FIELDNAMES
    assert rows[0]["id"] == built["@id"]
    assert rows[0]["public_body"] == built["public_body"]
    assert rows[0]["datacatalogue_package_count"] == 12


def test_transform_to_csv_rows_leaves_absent_optional_values_empty():
    built = build_record({**RECORD, "datacatalogue_package_count": None, "datacatalogue_description": ""}, LOOKUP)
    _, rows = transform_to_csv_rows([built])
    assert rows[0]["datacatalogue_package_count"] == ""
    assert rows[0]["datacatalogue_description"] == ""


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/datacatalogue-gov-ie-links>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "datacatalogue-gov-ie-links.jsonld"
    csv_path = tmp_path / "datacatalogue-gov-ie-links.csv"
    ttl_path = tmp_path / "dataset-datacatalogue-gov-ie-links.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"datacatalogue_slug": "old"}]}
    fieldnames, rows = ["id", "datacatalogue_slug"], [{"id": "1", "datacatalogue_slug": "old"}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "datacatalogue-gov-ie-links.jsonld"
    csv_path = tmp_path / "datacatalogue-gov-ie-links.csv"
    ttl_path = tmp_path / "dataset-datacatalogue-gov-ie-links.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"datacatalogue_slug": "same"}]}
    fieldnames, rows = ["id", "datacatalogue_slug"], [{"id": "1", "datacatalogue_slug": "same"}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()
