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
