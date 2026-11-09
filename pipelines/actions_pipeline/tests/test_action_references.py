import pytest

from action_references import (
    InvalidReference,
    InvalidEditionSlug,
    edition_year,
    parent_reference,
    parse_reference,
)


def test_a_plain_code_is_its_own_identity_and_printed_form():
    ref = parse_reference("EL/23/1")
    assert (ref.number, ref.printed, ref.flags) == ("EL/23/1", "EL/23/1", [])
    assert ref.year == 2023


def test_a_sub_action_segment_is_kept():
    ref = parse_reference("EL/23/6/A")
    assert ref.number == "EL/23/6/A"


def test_a_letter_attached_to_the_number_is_kept_as_printed():
    assert parse_reference("EL/23/10A").number == "EL/23/10A"


def test_a_bare_number_is_an_ordinal_with_no_year():
    ref = parse_reference("12")
    assert (ref.number, ref.printed, ref.flags, ref.year) == ("12", "12", [], None)


def test_the_taskforce_flag_is_stripped_with_or_without_a_space():
    a = parse_reference("TR/23/46(TF)")
    b = parse_reference("TR/24/4 (TF)")
    assert (a.number, a.printed, a.flags) == ("TR/23/46", "TR/23/46(TF)", ["taskforce"])
    assert (b.number, b.printed, b.flags) == ("TR/24/4", "TR/24/4 (TF)", ["taskforce"])


def test_non_reportable_and_duplicate_flags():
    assert parse_reference("RE/23/2*").flags == ["non_reportable"]
    dup = parse_reference("EL/23/1**")
    assert (dup.number, dup.flags) == ("EL/23/1", ["duplicate"])


def test_flags_combine_in_either_order_and_report_in_a_fixed_order():
    a = parse_reference("TR/23/26**(TF)")
    b = parse_reference("TR/23/2*(TF)")
    c = parse_reference("TR/23/2(TF)*")
    assert (a.number, a.flags) == ("TR/23/26", ["duplicate", "taskforce"])
    assert (b.number, b.flags) == ("TR/23/2", ["non_reportable", "taskforce"])
    assert (c.number, c.flags) == ("TR/23/2", ["non_reportable", "taskforce"])


def test_the_same_action_printed_with_and_without_a_flag_has_one_identity():
    assert parse_reference("TR/23/46").number == parse_reference("TR/23/46(TF)").number


def test_a_reference_wrapped_across_lines_is_read_whole():
    ref = parse_reference("EN/23/\n1*")
    assert (ref.number, ref.printed, ref.flags) == ("EN/23/1", "EN/23/1*", ["non_reportable"])
    assert parse_reference("BE/23/33/ \nA").number == "BE/23/33/A"


def test_non_breaking_and_doubled_spaces_are_normalised():
    assert parse_reference("LU/25/1\xa0\xa0").number == "LU/25/1"
    assert parse_reference("BE/23/33/A(TF)").number == "BE/23/33/A"


def test_an_unrecognised_parenthesised_suffix_is_not_stripped():
    with pytest.raises(InvalidReference) as e:
        parse_reference("EL/23/4(X)")
    assert e.value.error_type == "InvalidActionReference"
    assert "EL/23/4(X)" in str(e.value)


def test_a_stray_character_is_rejected():
    for raw in ("EL/23/1#", "EL/23/1 b", "EL-23-1", "EL/23//1", "EL/23/1/"):
        with pytest.raises(InvalidReference) as e:
            parse_reference(raw)
        assert e.value.error_type == "InvalidActionReference", raw


def test_an_empty_or_unrecognised_shape_is_unresolved_not_invalid():
    for raw in ("", "   ", "-", "Note", "Ongoing"):
        with pytest.raises(InvalidReference) as e:
            parse_reference(raw)
        assert e.value.error_type == "UnresolvedActionNumber", raw


def test_the_parent_of_a_sub_action():
    assert parent_reference("EL/23/6/A") == "EL/23/6"
    assert parent_reference("EL/23/10A") == "EL/23/10"
    assert parent_reference("EL/23/6") is None
    assert parent_reference("12") is None


def test_edition_year_comes_from_the_plan_slug():
    assert edition_year("climate-action-plan-2023-annex-of-actions") == 2023
    assert edition_year("climate-action-plan-2025-annex-of-actions") == 2025


@pytest.mark.parametrize("slug", [
    "no-year-here", "sustainable-mobility-policy-action-plan-2022-2025",
    "climate-action-plan-2023", "climate-action-plan-2023-annex-of-actions-v2",
    "climate-action-plan-1999-annex-of-actions", ""])
def test_a_slug_that_does_not_name_its_edition_is_fatal(slug):
    with pytest.raises(InvalidEditionSlug):
        edition_year(slug)
