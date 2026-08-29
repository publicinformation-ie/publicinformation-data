import pytest
from pathlib import Path

from scripts.transform_foi_request_files import (
    hash_document_id,
    build_record,
    transform_to_jsonld,
    transform_to_csv_rows,
    publish,
)
from src.lib.body_refs import BASE_URI, body_uri
from src.lib.dataset_publish import render_jsonld, render_csv


def test_hash_document_id_deterministic():
    url = "https://www.centralbank.ie/docs/default-source/foi-disclosure-log-q1-2026.pdf"
    assert hash_document_id(url) == hash_document_id(url)


def test_hash_document_id_is_12_hex_chars():
    result = hash_document_id("https://example.ie/foi.pdf")
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_document_id_differs_for_different_urls():
    a = hash_document_id("https://example.ie/foi-2024.pdf")
    b = hash_document_id("https://example.ie/foi-2025.pdf")
    assert a != b


def test_build_record_happy_path():
    file_record = {
        "public_body_id": 1104,
        "document_url": "https://www.centralbank.ie/docs/foi-disclosure-log-q1-2026.pdf",
        "source_page_url": "https://www.centralbank.ie/about/freedom-of-information/foi-disclosure-log",
        "file_type": "pdf",
    }
    body_slug_lookup = {1104: "central-bank-of-ireland"}
    record = build_record(file_record, body_slug_lookup)
    assert record["@id"] == f"{BASE_URI}/foi-request-file/" + record["@id"].rsplit("/", 1)[1]
    assert len(record["@id"].rsplit("/", 1)[1]) == 12
    assert record["@type"] == "foi:FoiRequestFile"
    assert record["public_body"] == f"{BASE_URI}/body/central-bank-of-ireland"
    assert record["document_url"] == file_record["document_url"]
    assert record["source_page_url"] == file_record["source_page_url"]
    assert record["file_type"] == "pdf"


def test_build_record_public_body_matches_shared_body_uri():
    file_record = {
        "public_body_id": 1104,
        "document_url": "https://www.centralbank.ie/docs/foi-disclosure-log-q1-2026.pdf",
        "source_page_url": "https://www.centralbank.ie/about/freedom-of-information/foi-disclosure-log",
        "file_type": "pdf",
    }
    slug = "central-bank-of-ireland"
    body_slug_lookup = {1104: slug}
    record = build_record(file_record, body_slug_lookup)
    assert record["public_body"] == body_uri(slug)


def test_build_record_unknown_public_body_id_raises():
    file_record = {
        "public_body_id": 9999,
        "document_url": "https://example.ie/foi.pdf",
        "source_page_url": "https://example.ie/foi-log",
        "file_type": "pdf",
    }
    with pytest.raises(ValueError, match="Unknown public_body_id"):
        build_record(file_record, body_slug_lookup={})


SAMPLE_RECORDS = [
    {
        "@id": f"{BASE_URI}/foi-request-file/aaaaaaaaaaaa",
        "@type": "foi:FoiRequestFile",
        "public_body": f"{BASE_URI}/body/central-bank-of-ireland",
        "document_url": "https://www.centralbank.ie/foi-2026.pdf",
        "source_page_url": "https://www.centralbank.ie/foi-log",
        "file_type": "pdf",
    },
    {
        "@id": f"{BASE_URI}/foi-request-file/bbbbbbbbbbbb",
        "@type": "foi:FoiRequestFile",
        "public_body": f"{BASE_URI}/body/ability-west",
        "document_url": "https://www.abilitywest.ie/foi-2025.xlsx",
        "source_page_url": "https://www.abilitywest.ie/foi-log",
        "file_type": "xlsx",
    },
]


def test_transform_to_jsonld_single_context_and_graph():
    doc = transform_to_jsonld(SAMPLE_RECORDS)
    assert "@context" in doc
    assert doc["@graph"] == SAMPLE_RECORDS
    assert all("@context" not in r for r in doc["@graph"])


def test_transform_to_csv_rows_columns_and_values():
    fieldnames, rows = transform_to_csv_rows(SAMPLE_RECORDS)
    assert fieldnames == ["id", "public_body", "document_url", "source_page_url", "file_type"]
    assert rows[0]["id"] == SAMPLE_RECORDS[0]["@id"]
    assert rows[0]["public_body"] == SAMPLE_RECORDS[0]["public_body"]
    assert rows[1]["file_type"] == "xlsx"


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/foi-request-files>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.1.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "foi-request-files.jsonld"
    csv_path = tmp_path / "foi-request-files.csv"
    ttl_path = tmp_path / "dataset-foi-request-files.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"document_url": "old"}]}
    fieldnames, rows = ["id", "document_url"], [{"id": "1", "document_url": "old"}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "foi-request-files.jsonld"
    csv_path = tmp_path / "foi-request-files.csv"
    ttl_path = tmp_path / "dataset-foi-request-files.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"document_url": "same"}]}
    fieldnames, rows = ["id", "document_url"], [{"id": "1", "document_url": "same"}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()
