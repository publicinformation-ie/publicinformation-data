from steps.extract_relationships.process import (
    build_edges,
    extract_references,
    is_continuity_phrase,
    edition_edges,
    section_edges,
    structure_edges,
)

PLAN = "sustainable-mobility-policy-action-plan-2022-2025"


def action(number, text="Do a thing", page=9):
    return {"action_id": f"{PLAN}#{number}", "plan_slug": PLAN,
            "action_number": number, "action_text": text, "source_page": page}


def node(title, start_page, end_page):
    return {"title": title, "start_page": start_page, "end_page": end_page,
            "level": 1, "slug": "x", "order": 100, "parent": None,
            "number": None, "start_y": 0.0, "confidence": 1.0}


# --- parenthetical references ----------------------------------------------

def test_a_bare_plan_action_reference_parses():
    refs = extract_references("Improve junction safety (RSS action 8)")
    assert refs == [{"relationship": "references", "to_plan_hint": "RSS",
                     "to_action_number": "8",
                     "evidence": "(RSS action 8)"}]


def test_a_cap_action_reference_parses():
    assert extract_references("Do a thing (CAP action 260)")[0]["to_plan_hint"] == "CAP"


def test_a_complements_prefix_selects_the_complements_term():
    refs = extract_references("Do a thing (Complements CAP action 233, RSS action 5)")
    assert [(r["relationship"], r["to_plan_hint"], r["to_action_number"]) for r in refs] == [
        ("complements", "CAP", "233"), ("complements", "RSS", "5")]


def test_a_plural_and_joined_number_list_parses_into_one_edge_each():
    refs = extract_references("Do a thing (Complements CAP actions 233 and 241)")
    assert [r["to_action_number"] for r in refs] == ["233", "241"]
    assert all(r["to_plan_hint"] == "CAP" for r in refs)


def test_a_policy_objective_reference_keeps_its_dotted_number():
    refs = extract_references("Do a thing (HfA Policy Objective 21.1)")
    assert refs[0]["to_plan_hint"] == "HfA"
    assert refs[0]["to_action_number"] == "21.1"


def test_text_with_no_parenthetical_yields_nothing():
    assert extract_references("Do a thing by Q4 2024") == []


def test_an_unrelated_parenthetical_yields_nothing():
    assert extract_references("Do a thing (subject to funding)") == []


def test_extracted_edges_never_carry_a_lineage_term():
    refs = extract_references(
        "Do a thing (Complements CAP action 1) and more (RSS action 2)")
    assert {r["relationship"] for r in refs} == {"complements", "references"}


# --- section-level groupings ------------------------------------------------

def test_a_complementary_actions_heading_yields_plan_level_edges():
    edges = section_edges(
        [action(19, page=30), action(20, page=31), action(1, page=9)],
        [node("Complementary Actions in Road Safety Strategy 2021-2030", 30, 34),
         node("Core Actions", 8, 29)],
        PLAN)
    assert {e["from_action_id"] for e in edges} == {f"{PLAN}#19", f"{PLAN}#20"}
    assert all(e["relationship"] == "complements" for e in edges)
    assert all(e["to_plan_hint"] == "Road Safety Strategy 2021-2030" for e in edges)


def test_a_plan_level_edge_has_a_null_action_number():
    """The heading names a plan, not a numbered action. Publishing a null is
    what distinguishes it from a resolvable action-level edge; inventing a
    number would be worse than either."""
    edges = section_edges([action(19, page=30)],
                          [node("Complementary Action in Climate Action Plan 2021", 30, 31)],
                          PLAN)
    assert edges[0]["to_action_number"] is None
    assert edges[0]["to_action_id"] is None
    assert edges[0]["to_plan_hint"] == "Climate Action Plan 2021"


def test_a_core_actions_heading_yields_no_edges():
    assert section_edges([action(1, page=9)], [node("Core Actions", 8, 29)], PLAN) == []


# --- declared candidates ----------------------------------------------------

def test_a_narrative_continuity_phrase_is_detected():
    assert is_continuity_phrase("Action 48, which incorporated various outputs")
    assert is_continuity_phrase("This action has been carried forward to the new plan")


def test_ordinary_progress_prose_is_not_a_continuity_phrase():
    assert not is_continuity_phrase("Work is underway and expected to complete in 2025")


# --- assembly and resolution ------------------------------------------------

def test_a_target_plan_in_the_corpus_resolves_to_an_action_id():
    actions = [action(19), {"action_id": "plan-b#8", "plan_slug": "plan-b",
                            "action_number": 8, "action_text": "", "source_page": 1}]
    edges, errors = build_edges(
        [{"action_id": f"{PLAN}#19", "plan_slug": PLAN,
          "action_text": "Do a thing (RSS action 8)", "source_page": 9}],
        actions, [], [], PLAN, hint_slugs={"RSS": "plan-b"}, curated=[])
    assert edges[0]["to_action_id"] == "plan-b#8"
    assert edges[0]["to_plan_hint"] == "RSS"


def test_an_external_target_is_published_with_a_null_id_and_is_not_an_error():
    edges, errors = build_edges(
        [{"action_id": f"{PLAN}#19", "plan_slug": PLAN,
          "action_text": "Do a thing (CAP action 233)", "source_page": 9}],
        [action(19)], [], [], PLAN, hint_slugs={}, curated=[])
    assert edges[0]["to_action_id"] is None
    assert edges[0]["to_plan_hint"] == "CAP"
    assert edges[0]["to_action_number"] == "233"
    assert errors == []


def test_a_continuity_phrase_in_progress_text_is_logged_never_published():
    edges, errors = build_edges(
        [], [action(48)],
        [{"action_id": f"{PLAN}#48", "report_slug": "year-one",
          "progress_text": "Action 48, which incorporated various outputs"}],
        [], PLAN, hint_slugs={}, curated=[])
    assert edges == []
    assert [e["error_type"] for e in errors] == ["RelationshipCandidate"]


def test_a_parenthetical_in_progress_text_is_published_and_credited_to_the_report():
    """Reports cross-reference other plans in the same parenthetical forms the
    plan does. The edge is real; the difference is who asserted it."""
    edges, errors = build_edges(
        [], [action(19)],
        [{"action_id": f"{PLAN}#19", "report_slug": "year-one",
          "progress_text": "Delivered jointly (Complements CAP action 233)"}],
        [], PLAN, hint_slugs={}, curated=[])
    assert len(edges) == 1
    assert edges[0]["asserted_in"] == "year-one"
    assert edges[0]["relationship"] == "complements"
    assert errors == []


def test_curated_edges_are_merged_in_and_keep_their_method():
    curated = [{"from_action_id": f"{PLAN}#1", "to_action_id": "plan-b#7",
                "to_plan_hint": "plan-b", "to_action_number": "7",
                "relationship": "carried_forward_to", "family": "lineage",
                "method": "curated", "asserted_in": "action_relationships.yml",
                "evidence": "Reviewed 2026-08-29."}]
    edges, _ = build_edges([], [action(1)], [], [], PLAN, hint_slugs={},
                           curated=curated)
    assert edges == curated


def test_every_edge_carries_the_family_matching_its_term():
    from relationships import VOCABULARY
    edges, _ = build_edges(
        [{"action_id": f"{PLAN}#19", "plan_slug": PLAN,
          "action_text": "Do a thing (Complements CAP action 233)", "source_page": 9}],
        [action(19)], [], [], PLAN, hint_slugs={}, curated=[])
    assert all(e["family"] == VOCABULARY[e["relationship"]] for e in edges)


# --- structure: sub-actions are part_of their parent -----------------------

CAP23 = "climate-action-plan-2023-annex-of-actions"
CAP24 = "climate-action-plan-2024-annex-of-actions"
CAP25 = "climate-action-plan-2025-annex-of-actions"


def cap(slug, number, printed=None):
    return {"action_id": f"{slug}#{number}", "plan_slug": slug,
            "action_number": number,
            "action_reference_printed": printed or number,
            "action_flags": [], "action_text": "", "source_page": 5}


def test_a_sub_action_is_part_of_a_published_parent():
    edges = structure_edges([cap(CAP23, "EL/23/6"), cap(CAP23, "EL/23/6/A")])
    assert edges == [{
        "from_action_id": f"{CAP23}#EL/23/6/A",
        "to_action_id": f"{CAP23}#EL/23/6",
        "to_plan_hint": CAP23,
        "to_action_number": "EL/23/6",
        "relationship": "part_of",
        "family": "structure",
        "method": "extracted",
        "asserted_in": CAP23,
        "evidence": "EL/23/6/A is a sub-action of EL/23/6",
    }]


def test_a_letter_attached_to_the_number_is_part_of_the_number():
    edges = structure_edges([cap(CAP23, "EL/23/10"), cap(CAP23, "EL/23/10A"),
                             cap(CAP23, "EL/23/10B")])
    assert [(e["from_action_id"], e["to_action_id"]) for e in edges] == [
        (f"{CAP23}#EL/23/10A", f"{CAP23}#EL/23/10"),
        (f"{CAP23}#EL/23/10B", f"{CAP23}#EL/23/10")]


def test_a_sub_action_without_a_published_parent_gets_no_edge():
    assert structure_edges([cap(CAP23, "EL/23/6/A")]) == []


def test_a_parent_in_another_edition_does_not_count():
    assert structure_edges([cap(CAP23, "EL/23/6"), cap(CAP24, "EL/23/6/A")]) == []


def test_ordinal_actions_have_no_structure():
    assert structure_edges([action("12"), action("13")]) == []


# --- lineage: the same reference printed by two editions --------------------

def test_the_same_reference_in_two_editions_is_carried_forward():
    edges = edition_edges([cap(CAP23, "LU/25/1"), cap(CAP25, "LU/25/1")])
    assert edges == [{
        "from_action_id": f"{CAP23}#LU/25/1",
        "to_action_id": f"{CAP25}#LU/25/1",
        "to_plan_hint": CAP25,
        "to_action_number": "LU/25/1",
        "relationship": "carried_forward_to",
        "family": "lineage",
        "method": "extracted",
        "asserted_in": CAP25,
        "evidence": f"{CAP23} and {CAP25} both print LU/25/1 as their own action",
    }]


def test_three_editions_chain_earlier_to_later():
    edges = edition_edges([cap(CAP25, "XX/25/1"), cap(CAP23, "XX/25/1"),
                           cap(CAP24, "XX/25/1")])
    assert [(e["from_action_id"], e["to_action_id"]) for e in edges] == [
        (f"{CAP23}#XX/25/1", f"{CAP24}#XX/25/1"),
        (f"{CAP24}#XX/25/1", f"{CAP25}#XX/25/1")]


def test_distinct_references_and_ordinals_are_not_linked():
    assert edition_edges([cap(CAP23, "EL/23/1"), cap(CAP25, "EL/25/1"),
                          action("1"), {**action("1"), "action_id": "plan-b#1",
                                        "plan_slug": "plan-b"}]) == []


# --- CAP hints stay unresolved once CAP editions are present ---------------

def test_cap_hinted_relationships_keep_a_null_target_when_cap_editions_exist():
    from steps.extract_relationships.process import PLAN_HINT_SLUGS
    assert "CAP" not in PLAN_HINT_SLUGS
    actions = [action(19), cap(CAP23, "EL/23/1"), cap(CAP23, "268")]
    edges, errors = build_edges(
        [{"action_id": f"{PLAN}#19", "plan_slug": PLAN,
          "action_text": "Do a thing (Complements CAP action 268)", "source_page": 9}],
        actions, [], [], PLAN, hint_slugs=PLAN_HINT_SLUGS, curated=[])
    assert [(e["to_plan_hint"], e["to_action_id"]) for e in edges] == [("CAP", None)]
