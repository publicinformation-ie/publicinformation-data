import json
from pathlib import Path

import pytest

from steps.extract_spc_items.extraction import (
    DECISION_TYPES,
    ExtractionFailed,
    apply_overrides,
    build_prompt,
    extract_meeting,
    load_overrides,
    load_taxonomy,
    run,
    validate_response,
)
from steps.resolve_attendees.resolving import load_register

PIPELINE = Path(__file__).resolve().parents[1]
COFOG, SUBDOMAINS = load_taxonomy(PIPELINE)
REGISTER = load_register(PIPELINE / "reference" / "people.json")

QUOTE = ("It was agreed to circulate the DoT & TII Policy on Roadside Memorials "
         "to the members.")


def _meeting():
    return {
        "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
        "committee_id": "meath/transportation-urban-regeneration",
        "committee_name": "Transportation & Urban Regeneration Strategic Policy Committee",
        "public_body_id": 1511,
        "meeting_date": "2026-02-19",
        "source_url": "https://www.meath.ie/x.pdf",
        "source_sha256": "a" * 64,
        "markdown": "# Minutes\n",
        "initials": {"AS": "Amanda Smith", "SD": "Sean Drew"},
        "items": [
            {
                "item_key": "item-1-0",
                "number": "1.0",
                "title": "Minutes of Previous Meeting 11th September 2025",
                "text": "Minutes of Previous Meeting 11th September 2025 Proposed by; "
                        "Cllr Amanda Smith (AS) Seconded by: Cllr Mike Bray (MB)",
                "is_minutes_approval": True,
            },
            {
                "item_key": "item-2-0",
                "number": "2.0",
                "title": "Matters Arising from Minutes",
                "text": QUOTE + " Proposed by: Cllr Amanda Smith (AS) "
                        "Seconded by: Cllr Sean Drew (SD).",
                "is_minutes_approval": False,
            },
        ],
    }


def _response(topics=None, decisions=None, item_key="item-2-0"):
    return {"items": [{
        "item_key": item_key,
        "topics": topics or {
            "cofog": ["04.5.1"],
            "subdomains": ["infra/regional-local-roads"],
            "procedural": False,
        },
        "decisions": decisions if decisions is not None else [{
            "decision_text": QUOTE,
            "decision_type": "agreed",
            "proposer": "AS",
            "seconder": "SD",
        }],
    }]}


def test_prompt_excludes_minutes_approval_and_includes_closed_lists():
    system, user = build_prompt(_meeting(), COFOG, SUBDOMAINS)
    assert "verbatim" in system
    assert "04.5.1" in user
    assert "infra/regional-local-roads" in user
    for decision_type in DECISION_TYPES:
        assert decision_type in user
    payload = json.loads(user)
    assert [item["item_key"] for item in payload["items"]] == ["item-2-0"]
    assert payload["initials"] == {"AS": "Amanda Smith", "SD": "Sean Drew"}


def test_the_result_carries_the_whole_meeting_through():
    """export_spc_meetings reads this step's output, so the meeting must survive."""
    result, _ = validate_response(_meeting(), _response(), COFOG, SUBDOMAINS, REGISTER)
    assert result["markdown"] == "# Minutes\n"
    assert [item["item_key"] for item in result["items"]] == ["item-1-0", "item-2-0"]
    assert result["committee_name"] == _meeting()["committee_name"]


def test_a_failed_meeting_still_carries_its_minutes():
    from steps.extract_spc_items.extraction import run
    import json as json_module

    results, errors = run({"results": [_meeting()]}, Path("/tmp/does-not-exist"),
                          REGISTER, COFOG, SUBDOMAINS,
                          api_fn=lambda system, user, session: json_module.dumps(
                              {"items": [{"item_key": "item-2-0", "topics": {"cofog": []}}]}))
    assert results[0]["extraction_failed"] is True
    assert results[0]["markdown"] == "# Minutes\n"
    assert results[0]["items"]
    assert [e["error_type"] for e in errors] == ["ExtractionFailed"]


def test_valid_response_produces_topics_and_decisions():
    result, errors = validate_response(
        _meeting(), _response(), COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    assert result["extraction_failed"] is False
    approval = next(t for t in result["item_topics"] if t["number"] == "1.0")
    assert approval == {"item_key": "item-1-0", "number": "1.0",
                        "cofog": ["01.1.1"], "subdomains": [], "procedural": True}
    decision = result["decisions"][0]
    assert "decision_id" not in decision  # assigned from the registry afterwards
    assert decision["proposer"] == "meath/amanda-smith"
    assert decision["seconder"] == "meath/sean-drew"


def test_schema_failure_fails_the_whole_meeting_closed():
    broken = {"items": [{"item_key": "item-2-0", "topics": {"cofog": []}}]}
    with pytest.raises(ExtractionFailed):
        validate_response(_meeting(), broken, COFOG, SUBDOMAINS, REGISTER)
    results, errors = run({"results": [_meeting()]}, Path("/tmp/does-not-exist"),
                          REGISTER, COFOG, SUBDOMAINS,
                          api_fn=lambda system, user, session: json.dumps(broken))
    assert results[0]["extraction_failed"] is True
    assert results[0]["decisions"] == [] and results[0]["item_topics"] == []
    assert [e["error_type"] for e in errors] == ["ExtractionFailed"]


def test_unknown_cofog_code_withholds_only_the_item_topics():
    result, errors = validate_response(
        _meeting(), _response(topics={"cofog": ["04.5.9"], "subdomains": [],
                                      "procedural": False}),
        COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["UnknownCofogCode"]
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["withheld"] is True and item["cofog"] is None
    assert len(result["decisions"]) == 1


def test_subdomain_without_a_transport_code_is_an_error():
    result, errors = validate_response(
        _meeting(), _response(topics={"cofog": ["06.4.0"],
                                      "subdomains": ["infra/regional-local-roads"],
                                      "procedural": False}),
        COFOG, SUBDOMAINS, REGISTER)
    assert "SubdomainWithoutTransport" in [e["error_type"] for e in errors]
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["withheld"] is True


def test_a_procedural_item_must_use_the_procedural_code():
    result, errors = validate_response(
        _meeting(), _response(topics={"cofog": ["04.5.1"],
                                      "subdomains": ["infra/regional-local-roads"],
                                      "procedural": True}),
        COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["ProceduralNotProceduralCode"]
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["withheld"] is True and item["cofog"] is None


def test_a_procedural_item_with_01_1_1_is_accepted():
    result, errors = validate_response(
        _meeting(), _response(topics={"cofog": ["01.1.1"], "subdomains": [],
                                      "procedural": True}),
        COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["procedural"] is True and item["cofog"] == ["01.1.1"]


def test_a_division_code_is_not_a_class_or_group():
    result, errors = validate_response(
        _meeting(), _response(topics={"cofog": ["04"], "subdomains": [],
                                      "procedural": False}),
        COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["CofogLevelNotClassOrGroup"]
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["withheld"] is True


def test_a_transport_group_needs_several_subdomains():
    result, errors = validate_response(
        _meeting(), _response(topics={
            "cofog": ["04.5"],
            "subdomains": ["infra/regional-local-roads"],
            "procedural": False,
        }), COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["CofogGroupNotSpanned"]
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["withheld"] is True


def test_a_transport_group_spanning_several_modes_is_accepted():
    result, errors = validate_response(
        _meeting(), _response(topics={
            "cofog": ["04.5"],
            "subdomains": ["infra/regional-local-roads", "infra/active-travel"],
            "procedural": False,
        }), COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["cofog"] == ["04.5"] and item["withheld"] is False


def test_a_non_transport_group_needs_two_child_classes():
    meeting = _meeting()
    meeting["items"][1]["text"] += (" It covers tourism and a "
                                    "multi-purpose development project.")
    result, errors = validate_response(
        meeting, _response(topics={
            "cofog": ["04.7", "04.7.3", "04.7.4"], "subdomains": [],
            "procedural": False,
        }), COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["cofog"] == ["04.7", "04.7.3", "04.7.4"]

    result, errors = validate_response(
        meeting, _response(topics={
            "cofog": ["04.7", "04.7.4"], "subdomains": [],
            "procedural": False,
        }), COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["CofogGroupNotSpanned"]
    item = next(t for t in result["item_topics"] if t["number"] == "2.0")
    assert item["withheld"] is True


def _manual(**fields):
    return {"source_method": "manual", "overridden": True, **fields}


def test_a_manual_topic_override_replaces_a_withheld_model_topic():
    result, _ = validate_response(
        _meeting(), _response(topics={"cofog": ["04.5.1"],
                                      "subdomains": ["infra/regional-local-roads"],
                                      "procedural": True}),
        COFOG, SUBDOMAINS, REGISTER)
    assert next(t for t in result["item_topics"] if t["item_key"] == "item-2-0")["withheld"]
    apply_overrides(result, [_manual(
        meeting_id=result["meeting_id"],
        item_topics=[{"item_key": "item-2-0", "cofog": ["01.1.1"],
                      "subdomains": [], "procedural": True}],
    )], COFOG, SUBDOMAINS)
    topic = next(t for t in result["item_topics"] if t["item_key"] == "item-2-0")
    assert topic == {"item_key": "item-2-0", "number": "2.0",
                     "cofog": ["01.1.1"], "subdomains": [],
                     "procedural": True, "withheld": False}


def test_an_override_for_an_unknown_item_fails_closed():
    with pytest.raises(ExtractionFailed, match="item-9-9"):
        apply_overrides(
            {"meeting_id": "meath/test/2026-01-01", "item_topics": [],
             "decisions": []},
            [_manual(meeting_id="meath/test/2026-01-01",
                     item_topics=[{"item_key": "item-9-9", "cofog": ["01.1.1"],
                                   "subdomains": [], "procedural": True}])],
            COFOG, SUBDOMAINS)


def test_load_overrides_rejects_a_non_manual_entry(tmp_path):
    path = tmp_path / "override.json"
    path.write_text('[{"meeting_id": "meath/test/2026-01-01"}]')
    with pytest.raises(ValueError, match="manual"):
        load_overrides(path)


def test_the_committed_override_file_loads():
    overrides = load_overrides(PIPELINE / "steps/extract_spc_items/override.json")
    assert overrides
    assert {entry["meeting_id"] for entry in overrides} == {
        "meath/transportation-urban-regeneration/2025-05-27",
    }


def test_paraphrased_decision_is_dropped():
    result, errors = validate_response(
        _meeting(), _response(decisions=[{
            "decision_text": "The committee decided to share the policy.",
            "decision_type": "agreed", "proposer": None, "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["DecisionNotInSource"]
    assert result["decisions"] == []


def test_unknown_decision_type_is_dropped():
    result, errors = validate_response(
        _meeting(), _response(decisions=[{
            "decision_text": QUOTE, "decision_type": "noted",
            "proposer": None, "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["UnknownDecisionType"]
    assert result["decisions"] == []


def test_unresolved_initials_yield_a_null_field_and_an_error():
    result, errors = validate_response(
        _meeting(), _response(decisions=[{
            "decision_text": QUOTE, "decision_type": "agreed",
            "proposer": "ZZ", "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["UnresolvedDecisionPerson"]
    assert result["decisions"][0]["proposer"] is None
    assert result["decisions"][0]["proposer_unresolved"] is True
    assert result["decisions"][0]["seconder_unresolved"] is False


def test_a_matching_echoed_meeting_id_is_accepted():
    response = _response()
    response["meeting_id"] = _meeting()["meeting_id"]
    result, errors = validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    assert len(result["decisions"]) == 1


def test_a_mismatched_echoed_meeting_id_fails_closed():
    response = _response()
    response["meeting_id"] = "meath/transportation-urban-regeneration/2026-05-21"
    with pytest.raises(ExtractionFailed, match="echoes meeting_id"):
        validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)


def test_echoed_context_in_a_meeting_object_is_accepted_when_it_agrees():
    response = _response()
    response["meeting"] = {
        "meeting_id": _meeting()["meeting_id"],
        "date": _meeting()["meeting_date"],
        "committee": _meeting()["committee_name"],
    }
    result, errors = validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    assert len(result["decisions"]) == 1


def test_a_wrong_echoed_date_fails_closed():
    response = _response()
    response["meeting"] = {"date": "2026-05-21"}
    with pytest.raises(ExtractionFailed, match="echoes date"):
        validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)


def test_a_wrong_echoed_committee_fails_closed():
    response = _response()
    response["committee"] = "Housing Strategic Policy Committee"
    with pytest.raises(ExtractionFailed, match="echoes committee"):
        validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)


def test_an_unknown_top_level_key_is_still_a_schema_failure():
    response = _response()
    response["notes"] = "anything"
    with pytest.raises(ExtractionFailed, match="Additional properties"):
        validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)


def test_minutes_approval_decision_is_discarded_and_counted():
    approval = ("It was agreed that the minutes of the previous meeting be approved.")
    meeting = _meeting()
    meeting["items"][1]["text"] = QUOTE + " " + approval
    result, errors = validate_response(
        meeting, _response(decisions=[{
            "decision_text": approval,
            "decision_type": "adopted", "proposer": None, "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    assert result["decisions"] == []
    assert result["minutes_approval_discarded"] == 1


def test_a_compound_decision_that_also_approves_minutes_is_kept():
    compound = ("It was agreed to approve the minutes of the previous meeting "
                "and to defer the footpath programme.")
    meeting = _meeting()
    meeting["items"][1]["text"] = compound
    result, errors = validate_response(
        meeting, _response(decisions=[{
            "decision_text": compound,
            "decision_type": "agreed", "proposer": None, "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    assert len(result["decisions"]) == 1
    assert result["minutes_approval_discarded"] == 0


def test_a_blank_decision_text_is_rejected():
    result, errors = validate_response(
        _meeting(), _response(decisions=[{
            "decision_text": "   ", "decision_type": "agreed",
            "proposer": None, "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert [e["error_type"] for e in errors] == ["DecisionTooShort"]
    assert result["decisions"] == []


def test_a_duplicated_decision_text_is_rejected():
    decision = {"decision_text": QUOTE, "decision_type": "agreed",
                "proposer": None, "seconder": None}
    result, errors = validate_response(
        _meeting(), _response(decisions=[decision, dict(decision)]),
        COFOG, SUBDOMAINS, REGISTER)
    assert "DuplicateDecision" in [e["error_type"] for e in errors]
    assert len(result["decisions"]) == 1


def test_a_duplicate_item_key_fails_the_whole_meeting():
    response = _response()
    response["items"].append(dict(response["items"][0]))
    with pytest.raises(ExtractionFailed, match="twice"):
        validate_response(_meeting(), response, COFOG, SUBDOMAINS, REGISTER)


def test_an_unknown_item_key_fails_the_whole_meeting():
    with pytest.raises(ExtractionFailed, match="not in the meeting"):
        validate_response(_meeting(), _response(item_key="item-9-9"),
                          COFOG, SUBDOMAINS, REGISTER)


def test_a_proposer_not_printed_in_the_item_is_withheld():
    result, errors = validate_response(
        _meeting(), _response(decisions=[{
            "decision_text": QUOTE, "decision_type": "agreed",
            "proposer": "Cllr Niamh Nobody", "seconder": None,
        }]), COFOG, SUBDOMAINS, REGISTER)
    assert "UnresolvedDecisionPerson" in [e["error_type"] for e in errors]
    decision = result["decisions"][0]
    assert decision["proposer"] is None and decision["proposer_unresolved"] is True


def test_a_proposer_absent_from_the_meeting_is_withheld():
    meeting = _meeting()
    meeting["attendance_published"] = True
    meeting["attendance"] = [{
        "person_id": "meath/sean-drew", "status": "present",
    }]
    result, errors = validate_response(
        meeting, _response(), COFOG, SUBDOMAINS, REGISTER)
    assert "UnresolvedDecisionPerson" in [e["error_type"] for e in errors]
    decision = result["decisions"][0]
    assert decision["proposer"] is None and decision["proposer_unresolved"] is True
    assert decision["seconder"] == "meath/sean-drew"


def test_presence_is_not_checked_when_attendance_is_withheld():
    meeting = _meeting()
    meeting["attendance_published"] = False
    meeting["attendance"] = []
    result, errors = validate_response(
        meeting, _response(), COFOG, SUBDOMAINS, REGISTER)
    assert errors == []
    assert result["decisions"][0]["proposer"] == "meath/amanda-smith"


def test_model_override_varies_the_cache_key_and_the_call(tmp_path, monkeypatch):
    captured = []

    def fake_extract_json(system, user, api_fn=None, model=None, effort=None):
        captured.append(model)
        return _response()

    monkeypatch.setattr(
        "steps.extract_spc_items.extraction.llm_extract.extract_json",
        fake_extract_json,
    )

    first, _ = extract_meeting(_meeting(), tmp_path, REGISTER, COFOG, SUBDOMAINS,
                              model="model-a")
    second, _ = extract_meeting(_meeting(), tmp_path, REGISTER, COFOG, SUBDOMAINS,
                                model="model-b")
    third, _ = extract_meeting(_meeting(), tmp_path, REGISTER, COFOG, SUBDOMAINS,
                               model="model-a")

    # One call per distinct model; the third read model-a's cached response.
    assert captured == ["model-a", "model-b"]
    assert first["model"] == "model-a"
    assert second["model"] == "model-b"
    assert third["decisions"] == first["decisions"]


def test_a_second_unchanged_run_makes_no_model_call(tmp_path):
    calls = []

    def api(system, user, session):
        calls.append(1)
        return json.dumps(_response())

    first, errors = extract_meeting(_meeting(), tmp_path, REGISTER, COFOG,
                                    SUBDOMAINS, api_fn=api)
    second, errors2 = extract_meeting(_meeting(), tmp_path, REGISTER, COFOG,
                                      SUBDOMAINS, api_fn=api)
    assert len(calls) == 1
    assert first["decisions"] == second["decisions"]
    assert errors == errors2 == []


def test_changing_the_prompt_text_invalidates_the_cache(tmp_path):
    calls = []

    def api(system, user, session):
        calls.append(user)
        return json.dumps(_response())

    meeting = _meeting()
    extract_meeting(meeting, tmp_path, REGISTER, COFOG, SUBDOMAINS, api_fn=api)
    changed = _meeting()
    changed["items"][1]["text"] = QUOTE + " Extra detail."
    extract_meeting(changed, tmp_path, REGISTER, COFOG, SUBDOMAINS, api_fn=api)
    assert len(calls) == 2


def test_a_response_that_fails_the_schema_is_not_cached(tmp_path):
    def api(system, user, session):
        return json.dumps({"items": [{"item_key": "item-2-0"}]})

    with pytest.raises(ExtractionFailed):
        extract_meeting(_meeting(), tmp_path, REGISTER, COFOG, SUBDOMAINS,
                        api_fn=api)
    assert list((tmp_path / "llm").glob("*.json")) == []
