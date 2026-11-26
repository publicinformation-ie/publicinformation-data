import json
from pathlib import Path

import pytest

from steps.resolve_attendees.resolving import (
    build_alias_index,
    build_initials_index,
    load_register,
    normalise_name,
    resolve_initials,
    resolve_meeting,
    run,
)

PIPELINE = Path(__file__).resolve().parents[1]
REGISTER = PIPELINE / "reference" / "people.json"


@pytest.fixture(scope="module")
def register():
    return load_register(REGISTER)


def test_normalisation_collapses_spacing_apostrophes_and_titles():
    assert normalise_name("Cllr Mike Bray") == "mike bray"
    assert normalise_name("Caroline O’ Reilly") == normalise_name("Caroline O'Reilly")
    assert normalise_name("Paula Mc Caul") == normalise_name("Paula McCaul")
    assert normalise_name("  John   McGrath ") == "john mcgrath"


def test_register_aliases_are_unique_across_people(register):
    index = build_alias_index(register)  # raises on a collision
    assert index[normalise_name("Nicholas Whyatt")] == "meath/person/nicholas-wyatt"
    assert index[normalise_name("Mike Bray")] == "meath/michael-bray"


def test_register_has_valid_kinds_and_person_id_shapes(register):
    kinds = {"councillor", "sectoral_representative", "official", "guest"}
    ids = [p["person_id"] for p in register]
    assert len(ids) == len(set(ids))
    for person in register:
        assert person["kind"] in kinds
        if person["kind"] == "councillor":
            assert person["person_id"] == person["councillor_id"]
        else:
            assert person["person_id"].startswith("meath/person/")
            assert person["councillor_id"] is None


def test_every_councillor_id_exists_in_the_councillor_reference(register):
    csv_path = (PIPELINE / "../minutes_pipeline/reference/councillors.csv").resolve()
    if not csv_path.exists():
        pytest.skip("the councillor reference is not present")
    known = {
        line.split(",")[0] for line in csv_path.read_text(encoding="utf-8").splitlines()[1:]
        if line
    }
    councillors = [p for p in register if p["kind"] == "councillor"]
    assert councillors
    for person in councillors:
        assert person["councillor_id"] in known


def _person(**overrides):
    person = {
        "person_id": "meath/michael-bray",
        "canonical_name": "Mike Bray",
        "kind": "councillor",
        "councillor_id": "meath/michael-bray",
        "public_body_id": 1511,
        "aliases": ["Mike Bray"],
        "initials": ["MB"],
    }
    person.update(overrides)
    return person


def test_load_register_rejects_an_unknown_kind(tmp_path):
    path = tmp_path / "people.json"
    path.write_text(json.dumps([_person(kind="minister")]), encoding="utf-8")
    with pytest.raises(ValueError, match="kind"):
        load_register(path)


def test_load_register_rejects_a_councillor_without_a_councillor_id(tmp_path):
    path = tmp_path / "people.json"
    path.write_text(json.dumps([_person(councillor_id=None)]), encoding="utf-8")
    with pytest.raises(ValueError, match="councillor_id"):
        load_register(path)


def test_load_register_rejects_aliases_that_are_not_a_list(tmp_path):
    path = tmp_path / "people.json"
    path.write_text(json.dumps([_person(aliases="Mike Bray")]), encoding="utf-8")
    with pytest.raises(ValueError, match="aliases"):
        load_register(path)


def test_load_register_rejects_a_councillor_absent_from_the_reference(tmp_path):
    path = tmp_path / "people.json"
    path.write_text(json.dumps([_person()]), encoding="utf-8")
    reference = tmp_path / "councillors.csv"
    reference.write_text("councillor_id,canonical_name\nmeath/other,Cllr Other\n",
                         encoding="utf-8")
    with pytest.raises(ValueError, match="unknown councillor"):
        load_register(path, councillor_reference=reference)


def _meeting(entries, initials=None):
    return {
        "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
        "public_body_id": 1511,
        "source_url": "https://www.meath.ie/x.pdf",
        "initials": initials or {},
        "attendance": entries,
    }


def _entry(name, category="councillors", markers=None, title="Cllr", role=""):
    return {
        "category": category,
        "printed_name": name,
        "title": title,
        "initials": None,
        "role": role,
        "markers": markers or [],
        "raw": name,
    }


def test_unknown_guest_withholds_that_meetings_attendance_only(register):
    alias_index = build_alias_index(register)
    good, good_errors = resolve_meeting(_meeting([_entry("Mike Bray")]), alias_index)
    bad, bad_errors = resolve_meeting(
        _meeting([_entry("Mike Bray"), _entry("Niamh Nobody", title="Ms.")]), alias_index
    )
    assert good["attendance_published"] is True
    assert good_errors == []
    assert bad["attendance_published"] is False
    assert bad["attendance"] == []
    assert bad["printed_attendance"][1]["printed_name"] == "Niamh Nobody"
    assert [e["error_type"] for e in bad_errors] == ["UnresolvedAttendee"]


def test_contradictory_status_withholds_attendance(register):
    alias_index = build_alias_index(register)
    result, errors = resolve_meeting(_meeting([
        _entry("Mike Bray", "councillors"),
        _entry("Mike Bray", "apologies"),
    ]), alias_index)
    assert result["attendance_published"] is False
    assert [e["error_type"] for e in errors] == ["ContradictoryAttendance"]


def test_status_and_mode_are_recorded(register):
    alias_index = build_alias_index(register)
    result, errors = resolve_meeting(_meeting([
        _entry("Mike Bray", markers=["remote"]),
        _entry("Sean Drew", "apologies"),
        _entry("Dave Anderson", "sectoral_representatives", markers=["in_person"], title="Mr.",
               role="PPN Rep"),
    ]), alias_index)
    assert errors == []
    rows = {row["person_id"]: row for row in result["attendance"]}
    assert rows["meath/michael-bray"]["status"] == "present"
    assert rows["meath/michael-bray"]["mode"] == "remote"
    assert rows["meath/sean-drew"]["status"] == "apologies"
    assert rows["meath/sean-drew"]["mode"] == "not_stated"
    assert rows["meath/person/dave-anderson"]["mode"] == "in_person"
    assert rows["meath/person/dave-anderson"]["role"] == "PPN Rep"


def test_a_person_printed_in_two_blocks_gets_one_row(register):
    alias_index = build_alias_index(register)
    result, errors = resolve_meeting(_meeting([
        _entry("Caroline Corrigan", "officials", title=None, role="Senior Engineer"),
        _entry("Caroline Corrigan", "presenters", title=None,
               role="Senior Engineer – Footpath Extension Programme"),
    ]), alias_index)
    assert errors == []
    assert len(result["attendance"]) == 1
    row = result["attendance"][0]
    assert row["category"] == "officials"
    assert row["presented"] is True
    assert row["role"] == ("Senior Engineer; "
                           "Senior Engineer – Footpath Extension Programme")


def test_presenter_only_keeps_the_presenters_category(register):
    alias_index = build_alias_index(register)
    result, errors = resolve_meeting(_meeting([
        _entry("Audrey Norris", "presenters", title=None, role="Road Safety Officer"),
    ]), alias_index)
    assert errors == []
    assert result["attendance"][0]["category"] == "presenters"
    assert result["attendance"][0]["presented"] is True


def test_conflicting_modes_across_blocks_withhold_attendance(register):
    alias_index = build_alias_index(register)
    result, errors = resolve_meeting(_meeting([
        _entry("Caroline Corrigan", "officials", markers=["remote"], title=None),
        _entry("Caroline Corrigan", "presenters", markers=["in_person"], title=None),
    ]), alias_index)
    assert result["attendance_published"] is False
    assert [e["error_type"] for e in errors] == ["ContradictoryMode"]


def test_initials_prefer_the_meeting_map_then_the_register(register):
    alias_index = build_alias_index(register)
    initials_index = build_initials_index(register)
    person, error = resolve_initials("SD", {"SD": "Sean Drew"}, alias_index, initials_index)
    assert (person, error) == ("meath/sean-drew", None)
    person, error = resolve_initials("PM", {}, alias_index, initials_index)
    assert (person, error) == ("meath/paddy-meade", None)
    person, error = resolve_initials("ZZ", {}, alias_index, initials_index)
    assert person is None and "no registered person" in error


def test_printed_initials_that_do_not_resolve_error_instead_of_guessing(register):
    # The meeting prints SD for a new person, but the register's SD is Sean
    # Drew. Falling through to the register would attribute the wrong person's
    # attendance and decisions.
    alias_index = build_alias_index(register)
    initials_index = build_initials_index(register)
    person, error = resolve_initials(
        "SD", {"SD": "Someone New"}, alias_index, initials_index)
    assert person is None
    assert "Someone New" in error
    assert "no registered person" in error


def test_all_six_real_meetings_resolve_with_zero_errors(register, parsed_meetings):
    results, errors = run({"results": parsed_meetings}, register)
    assert errors == []
    assert len(results) == 6
    assert all(r["attendance_published"] for r in results)
    for result in results:
        assert {row["person_id"] for row in result["attendance"]}
