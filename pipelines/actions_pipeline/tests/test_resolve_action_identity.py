from steps.resolve_action_identity.process import (
    build_actions,
    build_observations,
    column_value,
    mint_action_id,
    resolve_deadline,
    resolve_original_deadline,
    strip_leading_ordinal,
)

PLAN_SLUG = "sustainable-mobility-policy-action-plan-2022-2025"


def plan_record(actions, slug=PLAN_SLUG):
    return {"doc_slug": slug, "doc_title": "SMP Action Plan 2022-2025",
            "source_url": "https://example.ie/plan.pdf", "public_body_id": 1213,
            "actions": actions}


def plan_action(action, raw_date="", columns=None, ref="p009-t01-r01", page=9):
    return {"action_id": ref, "action": action, "raw_date": raw_date,
            "year": None, "quarter": None, "month": None, "day": None,
            "precision": None, "start": None, "end": None,
            "source_page": page, "source_table": 0, "columns": columns or {}}


def report_record(observations, slug="year-one", reports_on=PLAN_SLUG):
    return {"doc_slug": slug, "doc_title": "Year One", "reports_on": reports_on,
            "as_of": "2023-10-20", "report_format": "A",
            "observations": observations}


def observation(number, **overrides):
    obs = {"action_number": number, "action_text": "Do a thing",
           "proposed_output": "A thing", "reported_deadline_raw": "Q4 2024",
           "reported_deadline_start": "2024-10-01", "reported_deadline_end": "2024-12-31",
           "reported_deadline_precision": "quarter", "progress_text": "Underway",
           "status": "Delayed", "asi": "Improve", "source_page": 12,
           "source_ref": "p012-t01-r01"}
    obs.update(overrides)
    return obs


# --- identity ---------------------------------------------------------------

def test_the_key_is_namespaced_by_plan_slug():
    assert mint_action_id(PLAN_SLUG, 48) == f"{PLAN_SLUG}#48"


def test_two_plans_may_each_have_an_action_48_without_collision():
    assert mint_action_id("plan-a", 48) != mint_action_id("plan-b", 48)


def test_a_zero_padded_number_normalises_to_an_integer():
    actions, _ = build_actions([plan_record([plan_action("07. Do a thing")])], {})
    assert actions[0]["action_number"] == 7
    assert actions[0]["action_id"] == f"{PLAN_SLUG}#7"


def test_leading_ordinal_and_bel_artifacts_are_stripped():
    number, text = strip_leading_ordinal("1. \x07Develop and publish an annual review")
    assert number == 1
    assert text == "Develop and publish an annual review"


def test_raw_action_text_is_kept_and_clean_text_is_repaired():
    actions, _ = build_actions(
        [plan_record([plan_action("1. Improve staf.f support")])], {})
    assert actions[0]["action_text"] == "Improve staf.f support"
    assert actions[0]["action_text_clean"] == "Improve staff support"


def test_a_close_paren_ordinal_is_also_stripped():
    assert strip_leading_ordinal("12) Do a thing") == (12, "Do a thing")


def test_an_action_with_no_leading_ordinal_yields_no_number():
    assert strip_leading_ordinal("Develop a thing") == (None, "Develop a thing")


def test_an_action_with_no_number_is_skipped_and_logged():
    errors = []
    actions, errors = build_actions([plan_record([plan_action("Develop a thing")])], {})
    assert actions == []


# --- original deadline ------------------------------------------------------

def test_a_single_stated_date_is_transcribed_and_marked_stated():
    parsed, confidence = resolve_original_deadline("", "Q4 2024")
    assert confidence == "stated"
    assert parsed["precision"] == "quarter"
    assert parsed["start"] == "2024-10-01"


def test_a_single_year_inside_narrative_text_is_still_stated():
    parsed, confidence = resolve_original_deadline(
        "", "Publish the review by 2024. Output: a published review.")
    assert confidence == "stated"
    assert parsed["year"] == 2024


def test_a_multi_milestone_cell_resolves_to_its_latest_milestone():
    parsed, confidence = resolve_original_deadline(
        "", "2024: Draft published. 2025: Final published.")
    assert confidence == "interpreted"
    assert parsed["year"] == 2025


def test_the_incidental_year_guard_rejects_a_contract_name_range():
    """Action 3's real cell. A naive 'latest year wins' yields 2030 — from the
    title of a contract, not a deadline."""
    parsed, confidence = resolve_original_deadline(
        "", "2024: Existing IMMAC reviewed. 2025: IMMAC 2025-2030 agreed.")
    assert confidence == "interpreted"
    assert parsed["year"] == 2025


def test_an_en_dashed_range_is_rejected_too():
    parsed, _ = resolve_original_deadline("", "2024: X. 2025: RSS 2025–2030 agreed.")
    assert parsed["year"] == 2025


def test_a_cell_whose_only_years_are_all_in_ranges_yields_nothing():
    assert resolve_original_deadline("", "Deliver IMMAC 2025-2030") == (None, None)


def test_an_open_ended_cell_parses_with_a_stated_open_ended_precision():
    for cell, precision in (("Ongoing", "ongoing"), ("Annual campaigns", "annual")):
        result = resolve_deadline("", cell)
        assert result.parsed["precision"] == precision
        assert result.parsed["start"] is None
        assert result.confidence == "stated"


def test_as_soon_as_practicable_is_still_not_a_deadline():
    assert resolve_original_deadline("", "As soon as practicable") == (None, None)


def test_unlabelled_years_in_a_multi_year_cell_are_not_guessed_at():
    """Two candidate years, neither introduced as a milestone: refuse rather
    than pick the later one."""
    assert resolve_original_deadline(
        "", "Building on the 2021 review and the 2022 consultation") == (None, None)


def test_a_real_deadline_column_wins_over_the_timeline_cell():
    parsed, confidence = resolve_original_deadline("2029", "2024: X. 2025: Y.")
    assert confidence == "stated"
    assert parsed["year"] == 2029


# --- deadline label and milestones ------------------------------------------

def test_an_unlabelled_final_milestone_is_the_deadline():
    result = resolve_deadline(
        "", "2023: 41 additional carriages placed into passenger service. "
            "2025 95 DART+ carriages delivered.")
    assert (result.parsed["year"], result.label, result.confidence) == (
        2025, "2025", "interpreted")


def test_incidental_years_without_a_milestone_label_are_refused():
    result = resolve_deadline(
        "", "Building on the 2021 review and the 2022 consultation")
    assert result.parsed is None
    assert result.label == ""


def test_the_label_is_short_and_the_milestones_keep_the_prose():
    cell = ("2022: Report developed. 2023: First report published and annual "
            "reports published thereafet r.")
    result = resolve_deadline("", cell)
    assert result.label == "2023"
    assert result.milestones == cell


def test_milestones_are_repaired_but_the_deadline_raw_is_not():
    actions, _ = build_actions([plan_record([plan_action(
        "1. Do a thing",
        columns={"TIMELINE & OUTPUT":
                 "2022: Report developed. 2023: Report published thereafet r."})])], {})
    assert "thereafet r" in actions[0]["original_deadline_raw"]
    assert actions[0]["original_deadline_milestones"].endswith("thereafter.")


def test_a_bare_date_has_no_separate_milestones():
    result = resolve_deadline("", "Q4 2024")
    assert result.label == "Q4 2024"
    assert result.milestones == ""


def test_an_annual_prefix_does_not_hide_a_dated_milestone():
    result = resolve_deadline(
        "", "Annual: Train 5,000 pupils. 2022: Programme commenced.")
    assert result.parsed["year"] == 2022
    assert result.label == "2022"


def test_a_deadline_column_wins_and_interim_milestones_are_kept():
    actions, _ = build_actions([plan_record([plan_action(
        "1. Do a thing", raw_date="2029",
        columns={"INTERIM MILESTONES": "Q2 2026 - Preferred model agreed."})])], {})
    assert actions[0]["original_deadline_label"] == "2029"
    assert actions[0]["original_deadline_milestones"] == (
        "Q2 2026 - Preferred model agreed.")
    assert actions[0]["original_deadline_raw"] == "2029"


def test_an_annual_cell_gets_an_annual_label_and_no_start():
    result = resolve_deadline("", "Annual campaigns")
    assert result.parsed["precision"] == "annual"
    assert result.label == "Annual"
    assert result.confidence == "stated"
    assert result.parsed["start"] is None


def test_a_contract_name_range_is_still_not_a_deadline():
    result = resolve_deadline(
        "", "2024: Existing IMMAC reviewed. 2025: IMMAC 2025-2030 agreed.")
    assert result.parsed["year"] == 2025


def test_the_raw_timeline_cell_is_preserved_in_every_case():
    for cell in ("Q4 2024", "2024: X. 2025: Y.", "Annual campaigns"):
        actions, _ = build_actions(
            [plan_record([plan_action("1. Do a thing",
                                      columns={"TIMELINE & OUTPUT": cell})])], {})
        assert actions[0]["original_timeline_raw"] == cell


def test_bel_artifacts_are_stripped_from_the_published_timeline_raw():
    """`original_deadline_raw`/`original_timeline_raw` are published verbatim
    to consumers, so the `\\x07` bullet artifact that pollutes plan cells must
    not leak into the CSV alongside the action text it's already stripped
    from."""
    actions, _ = build_actions(
        [plan_record([plan_action("1. Do a thing",
                                  columns={"TIMELINE & OUTPUT": "\x07Q4 2024"})])], {})
    assert "\x07" not in actions[0]["original_deadline_raw"]
    assert "\x07" not in actions[0]["original_timeline_raw"]
    assert actions[0]["original_timeline_raw"] == "Q4 2024"


def test_an_unparseable_timeline_logs_a_date_parse_error():
    _, errors = build_actions(
        [plan_record([plan_action("1. Do a thing",
                                  columns={"TIMELINE & OUTPUT": "As soon as practicable"})])], {})
    assert [e["error_type"] for e in errors] == ["DateParseError"]


def test_confidence_is_null_exactly_when_no_deadline_resolved():
    actions, _ = build_actions(
        [plan_record([plan_action("1. Do a thing",
                                  columns={"TIMELINE & OUTPUT": "As soon as practicable"})])], {})
    assert actions[0]["original_deadline_start"] is None
    assert actions[0]["original_deadline_confidence"] is None

    actions, _ = build_actions(
        [plan_record([plan_action("1. Do a thing",
                                  columns={"TIMELINE & OUTPUT": "Ongoing"})])], {})
    assert actions[0]["original_deadline_start"] is None
    assert actions[0]["original_deadline_confidence"] == "stated"


# --- columns ----------------------------------------------------------------

def test_column_lookup_is_case_insensitive():
    """extract_actions keys `columns` with normalize_text, not
    normalize_header, so the keys keep their source casing (`LEAD`, `OWNER`)."""
    assert column_value({"LEAD": "DoT"}, ("owner", "lead")) == "DoT"
    assert column_value({"Owner": "DoT"}, ("owner", "lead")) == "DoT"
    assert column_value({}, ("owner", "lead")) == ""


def test_lead_support_and_timeline_are_read_from_the_plans_columns():
    actions, _ = build_actions([plan_record([plan_action(
        "1. Do a thing",
        columns={"OWNER": "DoT", "SUPPORT": "NTA", "TIMELINE & OUTPUT": "Q4 2024"})])], {})
    assert actions[0]["lead"] == "DoT"
    assert actions[0]["support"] == "NTA"
    assert actions[0]["original_timeline_raw"] == "Q4 2024"


def test_the_positional_reference_is_kept_as_source_ref_not_identity():
    actions, _ = build_actions(
        [plan_record([plan_action("1. Do a thing", ref="p009-t01-r01")])], {})
    assert actions[0]["source_ref"] == "p009-t01-r01"
    assert actions[0]["action_id"] == f"{PLAN_SLUG}#1"


# --- joining observations ---------------------------------------------------

def test_an_observation_joins_to_its_plan_via_reports_on():
    actions, _ = build_actions([plan_record([plan_action("1. Do a thing")])], {})
    observations, errors = build_observations([report_record([observation(1)])], actions)
    assert observations[0]["action_id"] == f"{PLAN_SLUG}#1"
    assert observations[0]["report_slug"] == "year-one"
    assert observations[0]["as_of"] == "2023-10-20"
    assert errors == []


def test_progress_text_is_repaired_in_a_clean_column():
    actions, _ = build_actions([plan_record([plan_action("1. Do a thing")])], {})
    observations, _ = build_observations(
        [report_record([observation(1, progress_text="Signed of flater in Q3.")])],
        actions)
    assert observations[0]["progress_text"] == "Signed of flater in Q3."
    assert observations[0]["progress_text_clean"] == "Signed off later in Q3."


def test_an_unresolvable_action_number_is_skipped_not_attached_to_a_neighbour():
    actions, _ = build_actions([plan_record([plan_action("1. Do a thing")])], {})
    observations, errors = build_observations([report_record([observation(2)])], actions)
    assert observations == []
    assert [e["error_type"] for e in errors] == ["UnresolvedActionNumber"]


def test_an_observation_whose_reports_on_names_no_known_plan_is_skipped():
    actions, _ = build_actions([plan_record([plan_action("1. Do a thing")])], {})
    observations, errors = build_observations(
        [report_record([observation(1)], reports_on="no-such-plan")], actions)
    assert observations == []
    assert [e["error_type"] for e in errors] == ["UnresolvedActionNumber"]


def test_a_plan_with_no_reports_yields_actions_and_zero_observations():
    """The 2026-2030 plan. Not a gap: it is the correct representation of a
    plan whose first progress report does not yet exist."""
    actions, _ = build_actions(
        [plan_record([plan_action("1. Do a thing")], slug="smp-2026-2030")], {})
    observations, errors = build_observations([], actions)
    assert len(actions) == 1 and observations == [] and errors == []


def test_divergence_at_the_first_report_is_informational_not_an_error():
    actions, _ = build_actions([plan_record([plan_action(
        "1. Do a thing", columns={"TIMELINE & OUTPUT": "Q4 2024"})])], {})
    observations, errors = build_observations(
        [report_record([observation(1, reported_deadline_start="2025-10-01",
                                    reported_deadline_end="2025-12-31")])], actions)
    assert len(observations) == 1
    assert [e["error_type"] for e in errors] == ["DeadlineDivergedAtFirstReport"]


def test_only_the_earliest_report_can_raise_the_divergence_marker():
    actions, _ = build_actions([plan_record([plan_action(
        "1. Do a thing", columns={"TIMELINE & OUTPUT": "Q4 2024"})])], {})
    late = report_record([observation(1, reported_deadline_start="2025-10-01")],
                         slug="year-two")
    late["as_of"] = "2024-08-27"
    early = report_record([observation(1, reported_deadline_start="2024-10-01")])
    observations, errors = build_observations([late, early], actions)
    assert len(observations) == 2
    assert errors == []
