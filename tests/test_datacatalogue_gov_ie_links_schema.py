import csv
import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "public/schemas/datacatalogue-gov-ie-links.schema.json"
VERSIONED = REPO_ROOT / "public/v1.0.0/datacatalogue-gov-ie-links"
LATEST = REPO_ROOT / "public/latest/datacatalogue-gov-ie-links"
PUBLIC_BODIES = REPO_ROOT / "public/latest/public-bodies/public-bodies.jsonld"

REQUIRED = {"@id", "@type", "public_body", "datacatalogue_slug", "datacatalogue_url"}


def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def records():
    return json.loads((LATEST / "datacatalogue-gov-ie-links.jsonld").read_text(encoding="utf-8"))["@graph"]


def test_schema_is_a_valid_json_schema():
    jsonschema.Draft202012Validator.check_schema(schema())


def test_schema_requires_the_core_fields():
    assert set(schema()["required"]) == REQUIRED
    assert schema()["properties"]["@type"]["const"] == "dcl:DataCatalogueLink"


def test_every_published_record_validates_against_the_schema():
    published = records()
    assert published
    for record in published:
        jsonschema.validate(record, schema())


def test_optional_fields_are_present_only_when_the_source_provided_them():
    for record in records():
        if "datacatalogue_package_count" in record:
            assert isinstance(record["datacatalogue_package_count"], int)
            assert record["datacatalogue_package_count"] >= 0
        if "datacatalogue_description" in record:
            assert record["datacatalogue_description"].strip()


def test_record_ids_follow_the_dataset_uri_pattern():
    for record in records():
        assert record["@id"] == (
            "https://data.publicinformation.ie/datacatalogue-gov-ie-links/"
            f"{record['datacatalogue_slug']}"
        )
        assert record["datacatalogue_url"] == (
            f"https://datacatalogue.gov.ie/organization/{record['datacatalogue_slug']}"
        )


def test_every_public_body_uri_is_published_by_the_public_bodies_dataset():
    "The spec's body-URI scenario: the link must resolve to a public-bodies @id."
    published = {r["@id"] for r in json.loads(PUBLIC_BODIES.read_text(encoding="utf-8"))["@graph"]}
    unresolved = {r["public_body"] for r in records()} - published
    assert not unresolved, sorted(unresolved)[:5]


def test_csv_mirrors_the_jsonld():
    with (LATEST / "datacatalogue-gov-ie-links.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    published = records()
    assert len(rows) == len(published)
    assert [r["id"] for r in rows] == [r["@id"] for r in published]
    assert [r["public_body"] for r in rows] == [r["public_body"] for r in published]


def test_the_csv_header_matches_the_csvw_metadata():
    with (LATEST / "datacatalogue-gov-ie-links.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    csvw = json.loads((LATEST / "datacatalogue-gov-ie-links.csv-metadata.json").read_text(encoding="utf-8"))
    assert header == [column["name"] for column in csvw["tableSchema"]["columns"]]


def test_latest_mirrors_the_versioned_release_byte_for_byte():
    for path in sorted(VERSIONED.iterdir()):
        mirror = LATEST / path.name
        assert mirror.exists(), path.name
        assert mirror.read_bytes() == path.read_bytes(), path.name
