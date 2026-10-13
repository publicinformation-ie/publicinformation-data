import csv
import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipelines" / "document_pipeline"))
sys.path.insert(0, str(REPO_ROOT / "src"))
V1 = REPO_ROOT / "public" / "v1.0.0" / "transport-policies"
LATEST = REPO_ROOT / "public" / "latest" / "transport-policies"
SCHEMA = REPO_ROOT / "public" / "schemas" / "transport-policies.schema.json"
TTL = REPO_ROOT / "public" / "catalog" / "dataset-transport-policies.ttl"
SEP = "|"


def _rows():
    with (V1 / "transport-policies.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _record(row):
    """Apply the CSVW parsing the descriptor declares (separator, boolean)."""
    return {
        **row,
        "source_urls": [u for u in row["source_urls"].split(SEP) if u],
        "doc_slugs": [s for s in row["doc_slugs"].split(SEP) if s],
        "has_document": row["has_document"] == "true",
    }


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_every_row_validates_against_the_schema():
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    rows = _rows()
    assert rows
    for row in rows:
        validator.validate(_record(row))


def test_csvw_columns_match_the_csv_header():
    csvw = json.loads((V1 / "transport-policies.csv-metadata.json").read_text(encoding="utf-8"))
    names = [c["name"] for c in csvw["tableSchema"]["columns"]]
    header = next(csv.reader((V1 / "transport-policies.csv").open(newline="", encoding="utf-8")))
    assert names == header
    assert csvw["tableSchema"]["primaryKey"] == "policy_id"


def test_policy_ids_are_unique_and_match_the_inventory():
    from policies import load_policies
    assert [r["policy_id"] for r in _rows()] == [p["policy_id"] for p in load_policies()]


def test_doc_slugs_exist_in_documents_yml():
    from documents import load_documents
    curated = {d["doc_slug"]: d["policy_id"] for d in load_documents()}
    for row in _rows():
        for slug in _record(row)["doc_slugs"]:
            assert curated[slug] == row["policy_id"], slug
    assert {s for r in _rows() for s in _record(r)["doc_slugs"]} == set(curated)


def test_latest_is_an_exact_copy_of_v1():
    for name in ("transport-policies.csv", "transport-policies.csv-metadata.json", "README.md"):
        assert (LATEST / name).read_bytes() == (V1 / name).read_bytes(), name


def test_ttl_has_the_stampable_modified_line_and_the_csv_distribution():
    text = TTL.read_text(encoding="utf-8")
    assert len(re.findall(r'^    dct:modified "\d{4}-\d{2}-\d{2}"\^\^xsd:date ;$', text, re.M)) == 1
    assert "/latest/transport-policies/transport-policies.csv" in text
    assert "transport-policies.csv-metadata.json" in text
