import pytest
from scripts.transform_foi_request_files import (
    hash_document_id,
    build_body_slug_lookup,
    build_record,
    transform_to_jsonld,
    transform_to_csv_rows,
)
from scripts.transform_public_bodies import BASE_URI


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


def test_build_body_slug_lookup_maps_id_to_slug():
    pipeline_bodies = [
        {"public_body_id": 1104, "public_body_name": "Central Bank of Ireland"},
        {"public_body_id": 1002, "public_body_name": "Ability West"},
    ]
    lookup = build_body_slug_lookup(pipeline_bodies)
    assert lookup == {
        1104: "central-bank-of-ireland",
        1002: "ability-west",
    }


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
