import json
from pathlib import Path

import pytest

from steps.resolve_attendees.resolving import (
    build_alias_index,
    build_initials_index,
    load_register,
    load_roster,
    normalise_name,
    resolve_initials,
    resolve_meeting,
    run,
)

PIPELINE = Path(__file__).resolve().parents[1]
REGISTER = PIPELINE / "reference" / "people.json"
ROSTER = PIPELINE / "reference" / "councillors.json"


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
            council = person["person_id"].split("/")[0]
            assert person["person_id"].startswith(f"{council}/person/")
            assert person["councillor_id"] is None


def test_every_councillor_id_exists_in_the_councillor_reference_or_the_roster(register):
    csv_path = (PIPELINE / "../minutes_pipeline/reference/councillors.csv").resolve()
    if not csv_path.exists():
        pytest.skip("the councillor reference is not present")
    known = {
        line.split(",")[0] for line in csv_path.read_text(encoding="utf-8").splitlines()[1:]
        if line
    }
    known |= {entry["councillor_id"] for entry in load_roster(ROSTER, csv_path)}
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


# ---------------------------------------------------------------------------
# SPC councillor roster, new statuses and the Kildare / Westmeath register
# ---------------------------------------------------------------------------

def _roster_entry(**overrides):
    entry = {"councillor_id": "kildare/kevin-duffy", "name": "Kevin Duffy",
             "public_body_id": 1456, "source_url": "https://kildarecoco.ie/x"}
    entry.update(overrides)
    return entry


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _reference(tmp_path, rows):
    path = tmp_path / "councillors.csv"
    path.write_text(
        "councillor_id,canonical_name,public_body_id\n" + "".join(
            f"{i},{n},{b}\n" for i, n, b in rows), encoding="utf-8")
    return path


def test_the_committed_roster_covers_only_councils_the_reference_does_not():
    reference = (PIPELINE / "../minutes_pipeline/reference/councillors.csv").resolve()
    roster = load_roster(ROSTER, reference)           # raises on any inconsistency
    assert {e["councillor_id"].split("/")[0] for e in roster} == {"kildare", "westmeath"}
    assert all(e["source_url"].startswith("http") for e in roster)


def test_a_roster_councillor_id_is_accepted_by_the_register(tmp_path):
    roster = _write(tmp_path, "councillors.json", [_roster_entry()])
    people = _write(tmp_path, "people.json", [_person(
        person_id="kildare/kevin-duffy", councillor_id="kildare/kevin-duffy",
        canonical_name="Kevin Duffy", public_body_id=1456, aliases=["Kevin Duffy"])])
    reference = _reference(tmp_path, [("meath/other", "Other", 1511)])
    register = load_register(people, councillor_reference=reference, roster=roster)
    assert register[0]["person_id"] == "kildare/kevin-duffy"


def test_a_councillor_in_neither_file_stops_the_run_naming_the_entry(tmp_path):
    roster = _write(tmp_path, "councillors.json", [_roster_entry()])
    people = _write(tmp_path, "people.json", [_person(
        person_id="kildare/nobody", councillor_id="kildare/nobody",
        canonical_name="Nobody", public_body_id=1456, aliases=["Nobody"])])
    reference = _reference(tmp_path, [("meath/other", "Other", 1511)])
    with pytest.raises(ValueError, match="kildare/nobody"):
        load_register(people, councillor_reference=reference, roster=roster)


def test_a_roster_entry_for_a_council_the_reference_covers_fails(tmp_path):
    roster = _write(tmp_path, "councillors.json", [_roster_entry(
        councillor_id="meath/jane-doe", name="Jane Doe", public_body_id=1511)])
    reference = _reference(tmp_path, [("meath/other", "Other", 1511)])
    with pytest.raises(ValueError, match="meath/jane-doe.*covered by the councillor reference"):
        load_roster(roster, reference)


def test_a_shared_id_with_a_different_name_or_body_fails(tmp_path):
    roster = _write(tmp_path, "councillors.json", [_roster_entry()])
    # Kildare later enters the reference (so it is no longer an uncovered council)
    # with a different name for the same ID.
    reference = _reference(tmp_path, [("kildare/kevin-duffy", "Kevin Duffie", 1456)])
    with pytest.raises(ValueError, match="kildare/kevin-duffy"):
        load_roster(roster, reference)


def test_roster_entries_need_a_well_formed_id_and_a_source(tmp_path):
    for bad in (_roster_entry(councillor_id="Kevin Duffy"), _roster_entry(source_url=""),
                _roster_entry(public_body_id="1456")):
        with pytest.raises(ValueError):
            load_roster(_write(tmp_path, "councillors.json", [bad]), None)
    with pytest.raises(ValueError, match="duplicate"):
        load_roster(_write(tmp_path, "d.json", [_roster_entry(), _roster_entry()]), None)


def test_a_non_councillor_person_id_must_be_council_person_slug(tmp_path):
    bad = _person(kind="official", councillor_id=None, person_id="kildare/jo-bloggs")
    with pytest.raises(ValueError, match="<council_slug>/person/<name-slug>"):
        load_register(_write(tmp_path, "people.json", [bad]))


def _kildare_meeting(entries):
    return {
        "meeting_id": "kildare/transport-mobility-open-spaces/2025-12-11",
        "public_body_id": 1456, "source_url": "https://kildarecoco.ie/x.pdf",
        "initials": {}, "attendance": entries,
    }


def test_not_present_is_status_absent_not_apologies(register):
    index = build_alias_index(register)
    result, errors = resolve_meeting(_kildare_meeting([
        _entry("Ger Dunne", category="absent", title="Councillor"),
        _entry("Peter Melrose", category="apologies", title="Councillor"),
        _entry("Bill Clear", category="guests", title="Councillor"),
    ]), index)
    assert errors == []
    rows = {r["person_id"]: r for r in result["attendance"]}
    assert (rows["kildare/ger-dunne"]["category"], rows["kildare/ger-dunne"]["status"]) == ("absent", "absent")
    assert rows["kildare/peter-melrose"]["status"] == "apologies"
    assert (rows["kildare/bill-clear"]["category"], rows["kildare/bill-clear"]["status"]) == ("guests", "present")


def test_meath_absent_mapping_is_unchanged(register):
    """Meath's 'Absent' row stays category apologies, status apologies."""
    result, _ = resolve_meeting(_meeting([_entry("Mike Bray", category="apologies")]),
                                build_alias_index(register))
    assert result["attendance"][0]["status"] == "apologies"


def test_online_marker_in_any_letter_case_is_remote(register):
    result, _ = resolve_meeting(_kildare_meeting([
        _entry("Paul Ward", title="Cllr", markers=["remote"])]), build_alias_index(register))
    assert result["attendance"][0]["mode"] == "remote"


def test_ocr_misreads_resolve_through_register_aliases_only(register):
    index = build_alias_index(register)
    assert index[normalise_name("Pau! Ward")] == "kildare/paul-ward"
    assert index[normalise_name("Noel Connelly")] == "kildare/noel-connolly"
    assert index[normalise_name("Cilr. Frankie Keena")] == "westmeath/frankie-keena"
    assert index[normalise_name("Liam McDaniels")] == "westmeath/liam-mcdaniel"
    assert normalise_name("Tracey O’Dwyer") == normalise_name("Tracey O'Dwyer")


def test_a_name_in_no_register_withholds_that_meetings_attendance(register):
    result, errors = resolve_meeting(_kildare_meeting([
        _entry("Joseph Knox", title="Mr")]), build_alias_index(register))
    assert [e["error_type"] for e in errors] == ["UnresolvedAttendee"]
    assert result["attendance_published"] is False


def test_new_council_meetings_resolve_except_the_one_unregistered_name(register, fetched_new_meetings):
    """All eleven Kildare and Westmeath meetings resolve against the committed register.

    Joseph Knox (Kildare, 6 Feb 2025) is deliberately not registered: the sources
    do not say whether he is a sectoral representative or a guest, so that
    meeting's attendance is withheld for review instead of being guessed.
    """
    from steps.parse_meeting_header.header import run as parse_headers

    parsed, parse_errors = parse_headers({"results": fetched_new_meetings})
    assert parse_errors == []
    results, errors = run({"results": parsed}, register)
    withheld = {r["meeting_id"]: r["withheld_reasons"] for r in results
                if not r["attendance_published"]}
    assert withheld == {
        "kildare/transport-mobility-open-spaces/2025-02-06":
            ["UnresolvedAttendee: 'Joseph Knox' matches no registered person"],
    }
    published = [r for r in results if r["attendance_published"]]
    assert len(published) == 10
    statuses = {row["status"] for r in published for row in r["attendance"]}
    assert statuses == {"present", "apologies", "absent"}
