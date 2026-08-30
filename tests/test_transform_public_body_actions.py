import csv
import io
import json

import pytest

import transform_public_body_actions as transform

PLAN = "smp-2022-2025"


def action(number=1, **overrides):
    record = {"action_id": f"{PLAN}#{number}", "public_body_id": 1213,
              "plan_slug": PLAN, "plan_title": "SMP 2022-2025",
              "source_url": "https://example.ie/plan.pdf", "action_number": number,
              "action_text": "Do a thing", "original_deadline_raw": "Q4 2024",
              "original_deadline_start": "2024-10-01",
              "original_deadline_end": "2024-12-31",
              "original_deadline_precision": "quarter",
              "original_deadline_confidence": "stated",
              "original_timeline_raw": "Q4 2024", "lead": "DoT", "support": "NTA",
              "output": "", "source_page": 9, "source_ref": "p009-t01-r01"}
    record.update(overrides)
    return record


def observation(number=1, report="year-one", **overrides):
    record = {"action_id": f"{PLAN}#{number}", "report_slug": report,
              "report_title": "Year One", "as_of": "2023-10-20",
              "status": "Delayed", "reported_deadline_raw": "Q4 2025",
              "reported_deadline_start": "2025-10-01",
              "reported_deadline_end": "2025-12-31",
              "reported_deadline_precision": "quarter",
              "progress_text": "Underway", "asi": "Improve",
              "source_page": 12, "source_ref": "p012-t01-r01"}
    record.update(overrides)
    return record


def relationship(**overrides):
    record = {"from_action_id": f"{PLAN}#1", "to_action_id": None,
              "to_plan_hint": "CAP", "to_action_number": "233",
              "relationship": "complements", "family": "reference",
              "method": "extracted", "asserted_in": PLAN,
              "evidence": "(Complements CAP action 233)"}
    record.update(overrides)
    return record


VOCABULARIES = {"status": {"Complete", "OnSchedule", "Delayed", "Ongoing", "Modified"},
                "relationship": {"complements", "references", "supersedes",
                                 "renumbered_as", "split_into", "merged_into",
                                 "carried_forward_to"}}


def check(actions, observations, relationships, expectations=None):
    return transform.check_invariants(
        actions, observations, relationships, expectations or {},
        VOCABULARIES["status"], VOCABULARIES["relationship"])


# --- invariant 1: action count ---------------------------------------------

def test_a_declared_action_count_must_match():
    violations = check([action(1)], [], [],
                       {PLAN: {"expected_action_count": 2}})
    assert any("expected_action_count" in v for v in violations)


def test_a_matching_action_count_passes():
    assert check([action(1)], [], [], {PLAN: {"expected_action_count": 1}}) == []


def test_a_plan_declaring_no_expected_count_is_not_checked():
    assert check([action(1)], [], [], {PLAN: {}}) == []


# --- invariant 2: published split -------------------------------------------

def test_a_declared_status_split_must_match():
    violations = check(
        [action(1), action(2)],
        [observation(1, status="Complete"), observation(2, status="Complete")],
        [], {"year-one": {"expected_status_counts": {"Complete": 1, "Delayed": 1}}})
    assert any("StatusCountMismatch" in v for v in violations)


def test_a_matching_status_split_passes():
    assert check(
        [action(1), action(2)],
        [observation(1, status="Complete"), observation(2, status="Delayed")],
        [], {"year-one": {"expected_status_counts": {"Complete": 1, "Delayed": 1}}}
    ) == []


# --- invariant 3: referential integrity -------------------------------------

def test_an_observation_referencing_no_action_is_a_violation():
    violations = check([action(1)], [observation(99)], [])
    assert any("action_id" in v for v in violations)


def test_a_relationship_source_referencing_no_action_is_a_violation():
    violations = check([action(1)], [], [relationship(from_action_id=f"{PLAN}#99")])
    assert any("from_action_id" in v for v in violations)


def test_a_non_null_relationship_target_must_resolve():
    violations = check([action(1)], [], [relationship(to_action_id=f"{PLAN}#99")])
    assert any("to_action_id" in v for v in violations)


def test_a_null_relationship_target_is_not_a_violation():
    assert check([action(1)], [], [relationship(to_action_id=None)]) == []


# --- invariant 4: vocabulary closure ----------------------------------------

def test_a_status_outside_the_vocabulary_is_a_violation():
    violations = check([action(1)], [observation(1, status="Nearly")], [])
    assert any("vocabulary" in v.lower() for v in violations)


def test_a_relationship_term_outside_the_vocabulary_is_a_violation():
    violations = check([action(1)], [], [relationship(relationship="sort_of")])
    assert any("vocabulary" in v.lower() for v in violations)


# --- invariant 5: observation uniqueness ------------------------------------

def test_a_duplicate_action_and_report_pair_is_a_violation():
    violations = check([action(1)], [observation(1), observation(1)], [])
    assert any("unique" in v.lower() for v in violations)


def test_the_same_action_observed_by_two_reports_is_fine():
    assert check([action(1)],
                 [observation(1, report="year-one"),
                  observation(1, report="year-two")], []) == []


# --- invariant 6: deadline comparability ------------------------------------

def test_a_precision_outside_the_shared_enumeration_is_a_violation():
    violations = check([action(1, original_deadline_precision="epoch")], [], [])
    assert any("precision" in v.lower() for v in violations)


# --- invariant 7: confidence closure ----------------------------------------

def test_an_unknown_confidence_value_is_a_violation():
    violations = check([action(1, original_deadline_confidence="guessed")], [], [])
    assert any("confidence" in v.lower() for v in violations)


def test_a_confidence_without_a_deadline_is_a_violation():
    violations = check([action(1, original_deadline_start=None,
                               original_deadline_confidence="stated")], [], [])
    assert any("confidence" in v.lower() for v in violations)


def test_a_deadline_without_a_confidence_is_a_violation():
    violations = check([action(1, original_deadline_confidence=None)], [], [])
    assert any("confidence" in v.lower() for v in violations)


def test_a_null_deadline_with_a_null_confidence_is_fine():
    assert check([action(1, original_deadline_start=None,
                         original_deadline_end=None,
                         original_deadline_precision=None,
                         original_deadline_confidence=None)], [], []) == []


# --- publication ------------------------------------------------------------

def test_a_violation_aborts_publication_and_writes_nothing(tmp_path, monkeypatch):
    written = []
    monkeypatch.setattr(transform, "stamp_if_changed",
                        lambda *a, **k: written.append(a) or True)
    with pytest.raises(transform.InvariantViolation):
        transform.publish_all([action(1)], [observation(99)], [],
                              {}, VOCABULARIES["status"],
                              VOCABULARIES["relationship"],
                              output_dir=tmp_path, ttl_path=tmp_path / "d.ttl")
    assert written == []
    assert list(tmp_path.iterdir()) == []


def test_csv_rows_carry_every_declared_field_in_order():
    rows = transform.build_action_rows([action(1)])
    assert list(rows[0]) == transform.ACTION_FIELDS
    rows = transform.build_observation_rows([observation(1)])
    assert list(rows[0]) == transform.OBSERVATION_FIELDS
    rows = transform.build_relationship_rows([relationship()])
    assert list(rows[0]) == transform.RELATIONSHIP_FIELDS


def test_a_null_is_rendered_as_an_empty_csv_cell_not_the_string_none():
    payload = transform.render_csv(
        transform.RELATIONSHIP_FIELDS,
        transform.build_relationship_rows([relationship(to_action_id=None)]))
    row = next(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    assert row["to_action_id"] == ""


def test_the_jsonld_graph_types_every_record():
    data = transform.transform_to_jsonld([action(1)], [observation(1)],
                                         [relationship()])
    assert {node["@type"] for node in data["@graph"]} == {
        "act:Action", "act:ActionStatusObservation", "act:ActionRelationship"}
    assert "act" in data["@context"]


def test_an_action_uri_is_path_safe_and_carries_no_hash():
    data = transform.transform_to_jsonld([action(48)], [], [])
    assert data["@graph"][0]["@id"].endswith(f"/action/{PLAN}/48")
    assert "#" not in data["@graph"][0]["@id"]


def test_an_observation_links_to_its_actions_uri():
    data = transform.transform_to_jsonld([action(1)], [observation(1)], [])
    action_node = next(n for n in data["@graph"] if n["@type"] == "act:Action")
    obs_node = next(n for n in data["@graph"]
                    if n["@type"] == "act:ActionStatusObservation")
    assert obs_node["action"] == action_node["@id"]


def test_output_lands_in_both_the_versioned_and_latest_directories():
    assert transform.OUTPUT_DIR == "public/v1.0.0/public-body-actions"
    assert transform.LATEST_DIR == "public/latest/public-body-actions"


def test_stamp_if_changed_is_called_once_with_every_payload_path(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(transform, "stamp_if_changed",
                        lambda ttl, paths, generated: calls.append(paths) or False)
    ttl = tmp_path / "d.ttl"
    transform.publish_all([action(1)], [observation(1)], [relationship()],
                          {}, VOCABULARIES["status"], VOCABULARIES["relationship"],
                          output_dir=tmp_path, ttl_path=ttl)
    assert len(calls) == 1
    assert {p.name for p in calls[0]} == {
        "actions.csv", "action-status-observations.csv",
        "action-relationships.csv", "public-body-actions.jsonld"}
