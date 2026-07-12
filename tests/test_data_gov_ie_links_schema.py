import json

import jsonschema

SCHEMA_PATH = "public/schemas/data-gov-ie-links.schema.json"
JSONLD_PATH = "public/v1.0.0/data-gov-ie-links/data-gov-ie-links.jsonld"


def test_schema_is_valid_json_schema():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_requires_core_fields():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    assert set(schema["required"]) == {
        "@id", "@type", "public_body", "datagovie_slug", "datagovie_url", "datagovie_package_count",
    }


def test_all_published_records_validate_against_schema():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    with open(JSONLD_PATH) as f:
        doc = json.load(f)
    records = doc["@graph"]
    assert len(records) > 0
    for record in records:
        jsonschema.validate(record, schema)
