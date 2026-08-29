import pytest

from relationships import VOCABULARY, InvalidRelationshipFile, load_relationships

KNOWN = {"plan-a#1", "plan-a#2", "plan-b#7"}


def write(tmp_path, body):
    path = tmp_path / "action_relationships.yml"
    path.write_text(body, encoding="utf-8")
    return path


def test_the_vocabulary_declares_a_family_for_every_term():
    assert VOCABULARY == {
        "renumbered_as": "lineage", "supersedes": "lineage",
        "split_into": "lineage", "merged_into": "lineage",
        "carried_forward_to": "lineage",
        "complements": "reference", "references": "reference"}


def test_an_empty_file_is_valid():
    assert load_relationships(None, KNOWN) == []


def test_an_empty_relationships_list_is_valid(tmp_path):
    assert load_relationships(write(tmp_path, "relationships: []\n"), KNOWN) == []


def test_a_valid_edge_is_loaded_with_its_family_denormalised(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to: plan-b#7
    relationship: carried_forward_to
    evidence: "Action 1 is carried forward as action 7."
""")
    edge = load_relationships(path, KNOWN)[0]
    assert edge["from_action_id"] == "plan-a#1"
    assert edge["to_action_id"] == "plan-b#7"
    assert edge["family"] == "lineage"
    assert edge["method"] == "curated"
    assert edge["to_plan_hint"] == "plan-b"
    assert edge["to_action_number"] == "7"


def test_an_external_target_needs_no_resolvable_endpoint(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to_plan_hint: CAP
    to_action_number: "233"
    external: true
    relationship: complements
    evidence: "Complements CAP action 233."
""")
    edge = load_relationships(path, KNOWN)[0]
    assert edge["to_action_id"] is None
    assert edge["to_plan_hint"] == "CAP"


def test_an_unresolvable_non_external_endpoint_is_fatal(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to: plan-z#99
    relationship: supersedes
    evidence: "x"
""")
    with pytest.raises(InvalidRelationshipFile, match="plan-z#99"):
        load_relationships(path, KNOWN)


def test_an_unresolvable_source_endpoint_is_fatal(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-z#99
    to: plan-a#1
    relationship: supersedes
    evidence: "x"
""")
    with pytest.raises(InvalidRelationshipFile, match="plan-z#99"):
        load_relationships(path, KNOWN)


def test_an_unknown_relationship_term_is_fatal(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to: plan-a#2
    relationship: sort_of_relates_to
    evidence: "x"
""")
    with pytest.raises(InvalidRelationshipFile, match="sort_of_relates_to"):
        load_relationships(path, KNOWN)


def test_a_self_edge_is_fatal(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to: plan-a#1
    relationship: supersedes
    evidence: "x"
""")
    with pytest.raises(InvalidRelationshipFile, match="self"):
        load_relationships(path, KNOWN)


def test_a_duplicate_triple_is_fatal(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to: plan-a#2
    relationship: supersedes
    evidence: "x"
  - from: plan-a#1
    to: plan-a#2
    relationship: supersedes
    evidence: "y"
""")
    with pytest.raises(InvalidRelationshipFile, match="duplicate"):
        load_relationships(path, KNOWN)


def test_the_same_pair_may_carry_two_different_relationships(tmp_path):
    path = write(tmp_path, """relationships:
  - from: plan-a#1
    to: plan-a#2
    relationship: supersedes
    evidence: "x"
  - from: plan-a#1
    to: plan-a#2
    relationship: complements
    evidence: "y"
""")
    assert len(load_relationships(path, KNOWN)) == 2


def test_malformed_yaml_is_fatal(tmp_path):
    with pytest.raises(InvalidRelationshipFile):
        load_relationships(write(tmp_path, "relationships: [oops\n"), KNOWN)


def test_the_shipped_file_parses_against_an_empty_corpus():
    """The committed file must always load — it is a process-fatal input."""
    from pathlib import Path
    shipped = Path(__file__).parents[1] / "action_relationships.yml"
    assert load_relationships(shipped, set()) == []
