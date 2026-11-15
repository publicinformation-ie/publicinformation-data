import csv
import json
import re
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "public/schemas/active-travel-allocations.schema.json"
VERSIONED = REPO_ROOT / "public/v1.0.0/active-travel-allocations"
LATEST = REPO_ROOT / "public/latest/active-travel-allocations"
TTL_PATH = REPO_ROOT / "public/catalog/dataset-active-travel-allocations.ttl"

DATASET_URI = "https://data.publicinformation.ie/dataset/active-travel-allocations"
PUBLIC_BODIES_URI = "https://data.publicinformation.ie/dataset/public-bodies"

REQUIRED = {
    "@id", "@type", "year", "recipient_name", "funding_stream", "project_code",
    "project_code_provisional", "project_name", "allocation_eur",
    "source_document_url", "source_document_sha256", "source_page",
}


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def records() -> list[dict]:
    return json.loads((LATEST / "active-travel-allocations.jsonld").read_text(encoding="utf-8"))["@graph"]


def test_the_schema_is_a_valid_json_schema():
    jsonschema.Draft202012Validator.check_schema(schema())


def test_the_schema_requires_the_core_fields():
    assert set(schema()["required"]) == REQUIRED


def test_the_funding_stream_vocabulary_is_closed():
    assert schema()["properties"]["funding_stream"]["enum"] == [
        "active_travel", "other_nta_streams"]
    assert schema()["properties"]["@type"]["const"] == "Allocation"


def test_the_allocation_is_a_non_negative_integer():
    allocation = schema()["properties"]["allocation_eur"]
    assert allocation["type"] == "integer"
    assert allocation["minimum"] == 0


def test_every_published_record_validates_against_the_schema():
    published = records()
    assert published
    for record in published:
        jsonschema.validate(record, schema())


def test_no_published_record_uses_a_stream_outside_the_vocabulary():
    assert {record["funding_stream"] for record in records()} <= {
        "active_travel", "other_nta_streams"}


def test_a_local_authority_record_carries_its_body_link():
    linked = 0
    for record in records():
        if "public_body_id" not in record:
            assert "public_body" not in record
            continue
        assert record["public_body"].startswith("https://data.publicinformation.ie/body/")
        linked += 1
    assert linked > 0


def test_the_csv_header_matches_the_csvw_and_the_jsonld():
    with (LATEST / "active-travel-allocations.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    csvw = json.loads((LATEST / "active-travel-allocations.csv-metadata.json").read_text())
    assert header == [column["name"] for column in csvw["tableSchema"]["columns"]]
    properties = set(schema()["properties"]) - {"@id", "@type", "@context"}
    assert set(header) == properties | {"id"}


def test_the_csv_boolean_column_uses_the_lowercase_lexical_space():
    "CSVW declares project_code_provisional as boolean; 'True' is not in its lexical space."
    with (LATEST / "active-travel-allocations.csv").open(newline="", encoding="utf-8") as fh:
        values = {row["project_code_provisional"] for row in csv.DictReader(fh)}
    assert values <= {"true", "false"}, values


def test_the_csv_row_count_matches_the_jsonld_graph():
    with (LATEST / "active-travel-allocations.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(records())


def test_latest_mirrors_the_versioned_release_byte_for_byte():
    for path in sorted(VERSIONED.iterdir()):
        mirror = LATEST / path.name
        assert mirror.exists(), path.name
        assert mirror.read_bytes() == path.read_bytes(), path.name


def test_the_catalogue_entry_parses_and_versions_with_the_directory():
    text = TTL_PATH.read_text(encoding="utf-8")
    assert f"<{DATASET_URI}>" in text
    assert len(re.findall(r"^    dct:modified \"\d{4}-\d{2}-\d{2}\"\^\^xsd:date ;$", text, re.M)) == 1
    version = re.search(r'owl:versionInfo "([^"]+)"', text).group(1)
    assert VERSIONED.parent.name == f"v{version}"


def test_the_catalogue_entry_relates_the_dataset_to_public_bodies():
    text = TTL_PATH.read_text(encoding="utf-8")
    assert f"dct:relation <{PUBLIC_BODIES_URI}>" in text
    assert f"<{DATASET_URI}>" in text


def test_the_catalogue_entry_declares_both_distributions():
    text = TTL_PATH.read_text(encoding="utf-8")
    assert text.count("a dcat:Distribution") == 2
    assert "latest/active-travel-allocations/active-travel-allocations.jsonld" in text
    assert "latest/active-travel-allocations/active-travel-allocations.csv" in text
    assert "schemas/active-travel-allocations.schema.json" in text


def test_the_readme_record_count_matches_the_published_csv():
    text = (LATEST / "README.md").read_text(encoding="utf-8")
    rows = {int(m.group(1).replace(",", "")): int(m.group(2).replace(",", ""))
            for m in re.finditer(r"^\| (\d{4}) \| ([\d,]+) \|", text, re.M)}
    with (LATEST / "active-travel-allocations.csv").open(newline="", encoding="utf-8") as fh:
        published = list(csv.DictReader(fh))
    counts = {}
    for row in published:
        counts[int(row["year"])] = counts.get(int(row["year"]), 0) + 1
    assert rows == counts
