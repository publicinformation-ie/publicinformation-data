import csv
import json

import jsonschema

SCHEMA_PATH = "public/schemas/motions.schema.json"
JSONLD_PATH = "public/v1.0.0/motions/motions.jsonld"
VOCABULARY_PATH = "public/vocabularies/motion-status.csv"

REQUIRED = {
    "@id", "@type", "public_body", "public_body_id", "motion_id",
    "meeting_date", "meeting_type", "source_file_url", "motion_text", "status",
}


def _schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_schema_is_valid_json_schema():
    jsonschema.Draft202012Validator.check_schema(_schema())


def test_schema_requires_core_fields():
    assert set(_schema()["required"]) == REQUIRED


def test_schema_enums_are_closed():
    schema = _schema()
    assert set(schema["properties"]["meeting_type"]["enum"]) == {
        "council", "municipal_district",
    }
    assert set(schema["properties"]["status"]["enum"]) == {
        "carried", "carried_as_amended", "not_carried",
        "withdrawn", "deferred", "not_recorded",
    }


def test_every_published_record_validates_against_schema():
    schema = _schema()
    with open(JSONLD_PATH) as f:
        records = json.load(f)["@graph"]
    assert len(records) == 3959
    for record in records:
        jsonschema.validate(record, schema)


def test_schema_status_enum_matches_vocabulary():
    schema = _schema()
    with open(VOCABULARY_PATH, newline="", encoding="utf-8") as f:
        terms = {row["notation"] for row in csv.DictReader(f)}
    assert set(schema["properties"]["status"]["enum"]) == terms
    assert len(terms) == 6