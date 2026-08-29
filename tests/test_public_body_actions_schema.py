import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
VOCAB_DIR = REPO_ROOT / "public" / "vocabularies"
NS = "https://publicinformation-ie.codeberg.page/publicinformation-data/ns/action#"


def read_vocabulary(name):
    with (VOCAB_DIR / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_status_vocabulary_matches_the_extractors_map():
    """The CSV is the published contract and the step's map is what fills the
    column. If they drift, the publisher's vocabulary-closure invariant fires
    at release time; this catches it at commit time instead."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "pipelines" / "document_pipeline"))
    from steps.extract_action_status.process import STATUS_VOCABULARY
    rows = read_vocabulary("action-status.csv")
    assert {r["notation"] for r in rows} == set(STATUS_VOCABULARY.values())


def test_relationship_vocabulary_matches_the_loaders_map():
    import sys
    sys.path.insert(0, str(REPO_ROOT / "pipelines" / "actions_pipeline"))
    from relationships import VOCABULARY
    rows = read_vocabulary("action-relationship.csv")
    assert {r["notation"]: r["family"] for r in rows} == VOCABULARY


def test_every_vocabulary_uri_follows_the_namespace_pattern():
    for name in ("action-status.csv", "action-relationship.csv"):
        for row in read_vocabulary(name):
            assert row["uri"] == f"{NS}{row['notation']}", row


def test_no_vocabulary_row_has_an_empty_description():
    for name in ("action-status.csv", "action-relationship.csv"):
        for row in read_vocabulary(name):
            assert row["description"].strip(), (name, row["notation"])


def test_each_vocabulary_has_a_matching_csvw_descriptor():
    for name in ("action-status.csv", "action-relationship.csv"):
        descriptor = json.loads((VOCAB_DIR / f"{name}-metadata.json").read_text())
        assert descriptor["url"] == name
        declared = [c["name"] for c in descriptor["tableSchema"]["columns"]]
        with (VOCAB_DIR / name).open(newline="", encoding="utf-8") as f:
            assert next(csv.reader(f)) == declared


CSVW_PATH = REPO_ROOT / "public" / "v1.0.0" / "public-body-actions" / "public-body-actions.csv-metadata.json"
SCHEMA_PATH = REPO_ROOT / "public" / "schemas" / "public-body-actions.schema.json"
TTL_PATH = REPO_ROOT / "public" / "catalog" / "dataset-public-body-actions.ttl"


def csvw():
    return json.loads(CSVW_PATH.read_text())


def test_the_csvw_is_one_tablegroup_covering_three_tables():
    assert [t["url"] for t in csvw()["tables"]] == [
        "actions.csv", "action-status-observations.csv", "action-relationships.csv"]


def test_the_csvw_declares_the_foreign_keys_to_actions():
    tables = {t["url"]: t for t in csvw()["tables"]}
    for url, column in (("action-status-observations.csv", "action_id"),
                        ("action-relationships.csv", "from_action_id")):
        keys = tables[url]["tableSchema"]["foreignKeys"]
        assert any(k["columnReference"] == column
                   and k["reference"] == {"resource": "actions.csv",
                                          "columnReference": "action_id"}
                   for k in keys), url


def test_the_observation_primary_key_is_the_action_and_report_pair():
    tables = {t["url"]: t for t in csvw()["tables"]}
    assert tables["action-status-observations.csv"]["tableSchema"]["primaryKey"] == [
        "action_id", "report_slug"]


def test_the_schema_status_enum_matches_the_status_vocabulary():
    schema = json.loads(SCHEMA_PATH.read_text())
    enum = schema["$defs"]["ActionStatusObservation"]["properties"]["status"]["enum"]
    assert set(enum) == {r["notation"] for r in read_vocabulary("action-status.csv")}


def test_the_schema_relationship_enum_matches_the_relationship_vocabulary():
    schema = json.loads(SCHEMA_PATH.read_text())
    enum = schema["$defs"]["ActionRelationship"]["properties"]["relationship"]["enum"]
    assert set(enum) == {r["notation"] for r in read_vocabulary("action-relationship.csv")}


def test_the_ttl_declares_version_1_0_0_and_a_stampable_dct_modified():
    import re
    text = TTL_PATH.read_text()
    assert 'owl:versionInfo "1.0.0"' in text
    assert len(re.findall(r'(dct:modified\s+")[^"]*("\^\^xsd:date\s*;)', text)) == 1
