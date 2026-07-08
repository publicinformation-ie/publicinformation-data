import json

import jsonschema
import pytest

SCHEMA_PATH = "public/schemas/who-does-what.schema.json"
JSONLD_PATH = "public/v1.0.0/who-does-what/who-does-what.jsonld"


def test_schema_is_valid_json_schema():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_requires_core_fields():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    assert set(schema["required"]) == {"@id", "@type", "public_body", "wdw_slug", "wdw_url"}


def test_all_27_published_records_validate_against_schema():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    with open(JSONLD_PATH) as f:
        doc = json.load(f)
    records = doc["@graph"]
    assert len(records) == 27
    for record in records:
        jsonschema.validate(record, schema)
