"""Tests for the transport RACI loader, validator and row generation."""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

from src.lib.transport_raci import (
    ASSESSED,
    NOT_ASSESSED,
    generate_rows,
    load_master,
    validate,
)

FIXTURE = Path(__file__).parent / "fixtures" / "transport_raci" / "master"
COFOG = {"04.5.1", "03.1.0"}
BODIES = {
    "https://data.publicinformation.ie/body/meath-county-council",
    "https://data.publicinformation.ie/body/national-transport-authority-nta",
}
MEATH = "https://data.publicinformation.ie/body/meath-county-council"


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_loader_reads_every_table() -> None:
    master = load_master(FIXTURE)
    assert [stage.stage_id for stage in master.stages] == ["S1", "S2"]
    assert [activity.activity_id for activity in master.activities] == [
        "A-01", "A-02"]
    assert master.activity_groupings[0].is_primary is True
    assert master.parties_by_id()["NTA"].kind == "body"
    assert master.evidence_by_id()["unverified"].plain_label == "not yet confirmed"
    assert len(master.assignments) == 3
    assert len(master.assignment_roles) == 6


def test_fixture_master_passes() -> None:
    master = load_master(FIXTURE)
    assert validate(master, cofog_codes=COFOG, body_uris=BODIES) == []


def test_rows_come_from_activity_stages() -> None:
    rows = generate_rows(load_master(FIXTURE))
    assert [row.row_id for row in rows] == ["A-01.S1", "A-01.S2"]
    assert [row.coverage for row in rows] == [ASSESSED, ASSESSED]
    assert [row.assessed_lines for row in rows] == [1, 2]


def test_retired_activity_produces_no_rows() -> None:
    rows = generate_rows(load_master(FIXTURE))
    assert all(not row.row_id.startswith("A-02") for row in rows)


def test_unassessed_row_is_not_assessed(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "master")
    for table in ("assignments.csv", "assignment_roles.csv"):
        path = tmp_path / "master" / table
        header, rows = read_rows(path)
        rows = [row for row in rows
                if not row["assignment_id"].startswith("A-01.S2")]
        write_rows(path, header, rows)
    generated = generate_rows(load_master(tmp_path / "master"))
    by_id = {row.row_id: row for row in generated}
    assert by_id["A-01.S2"].coverage == NOT_ASSESSED
    assert by_id["A-01.S2"].assessed_lines == 0


def _mutate(tmp_path: Path, table: str, change) -> Path:
    shutil.copytree(FIXTURE, tmp_path / "master")
    path = tmp_path / "master" / table
    header, rows = read_rows(path)
    rows = change(rows)
    write_rows(path, header, rows)
    return tmp_path / "master"


def test_duplicate_key_fails(tmp_path: Path) -> None:
    def change(rows):
        return rows + [{**rows[0], "name": "Duplicate"}]

    root = _mutate(tmp_path, "activities.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "activities" and e.key == "A-01" for e in errors)


def test_unknown_foreign_key_fails(tmp_path: Path) -> None:
    def change(rows):
        return rows + [{"activity_id": "A-01", "stage_id": "S9"}]

    root = _mutate(tmp_path, "activity_stages.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "activity_stages" and "S9" in e.key for e in errors)


def test_unknown_cofog_code_fails(tmp_path: Path) -> None:
    def change(rows):
        return [{**rows[0], "cofog_class": "04.5.9"}]

    root = _mutate(tmp_path, "groupings.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "groupings" and e.key == "RT1" for e in errors)


def test_unknown_body_uri_fails(tmp_path: Path) -> None:
    def change(rows):
        return [{**row, "public_body_uri": "https://example.org/body/unknown"}
                if row["party_id"] == "NTA" else row for row in rows]

    root = _mutate(tmp_path, "parties.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "parties" and e.key == "NTA" for e in errors)


def test_assignment_on_missing_stage_link_fails(tmp_path: Path) -> None:
    def change(rows):
        return rows + [{"activity_id": "A-01", "stage_id": "S3"}]

    root = _mutate(tmp_path, "activity_stages.csv", change)
    path = root / "stages.csv"
    header, rows = read_rows(path)
    write_rows(path, header, rows + [{
        "stage_id": "S3", "name": "Third", "definition": "Third stage.",
        "sort_order": "3", "public_name": "Third",
        "public_definition": "Third stage."}])
    path = root / "assignments.csv"
    header, rows = read_rows(path)
    write_rows(path, header, rows + [{
        "assignment_id": "A-01.S3", "activity_id": "A-01", "stage_id": "S3",
        "variant_id": "", "applies_to": MEATH, "evidence_id": "statute",
        "note": "", "public_note": "", "scenario_refs": ""}])
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S3" for e in errors)


def test_duplicate_combination_fails(tmp_path: Path) -> None:
    def change(rows):
        return rows + [dict(rows[0], assignment_id="A-01.S1-copy")]

    root = _mutate(tmp_path, "assignments.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S1-copy"
               for e in errors)


def test_two_accountable_parties_fail(tmp_path: Path) -> None:
    def change(rows):
        return rows + [{"assignment_id": "A-01.S1", "role": "A",
                        "party_id": "NTA", "qualifier": ""}]

    root = _mutate(tmp_path, "assignment_roles.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S1" for e in errors)


def test_zero_accountable_with_statute_fails(tmp_path: Path) -> None:
    def change(rows):
        return [row for row in rows
                if not (row["assignment_id"] == "A-01.S1" and row["role"] == "A")]

    root = _mutate(tmp_path, "assignment_roles.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S1" for e in errors)


def test_part_both_accountable_and_consulted_fails(tmp_path: Path) -> None:
    def change(rows):
        return rows + [{"assignment_id": "A-01.S1", "role": "C",
                        "party_id": "LA-CE", "qualifier": ""}]

    root = _mutate(tmp_path, "assignment_roles.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S1" for e in errors)


def test_category_accountable_fails(tmp_path: Path) -> None:
    def change(rows):
        result = []
        for row in rows:
            if row["assignment_id"] == "A-01.S1" and row["role"] == "A":
                continue
            result.append(row)
        return result + [{"assignment_id": "A-01.S1", "role": "A",
                          "party_id": "DA", "qualifier": ""}]

    root = _mutate(tmp_path, "assignment_roles.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignment_roles" and "DA" in e.key for e in errors)


def test_no_primary_grouping_fails(tmp_path: Path) -> None:
    def change(rows):
        return [{**row, "is_primary": "false"} for row in rows]

    root = _mutate(tmp_path, "activity_groupings.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "activities" and e.key == "A-01" for e in errors)


def test_retired_activity_with_stage_fails(tmp_path: Path) -> None:
    def change(rows):
        return rows + [{"activity_id": "A-02", "stage_id": "S1"}]

    root = _mutate(tmp_path, "activity_stages.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "activity_stages" and "A-02" in e.key for e in errors)


def test_validator_returns_every_error(tmp_path: Path) -> None:
    def change(rows):
        rows = [{**row, "cofog_class": "99.9.9"} for row in rows]
        return rows + [{**rows[0], "grouping_id": "RT9", "name": "Duplicate"}]

    root = _mutate(tmp_path, "groupings.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert len(errors) >= 3


def test_zero_accountable_unverified_without_note_fails(tmp_path: Path) -> None:
    # A-01.S2 is unverified with no roles; it passes only because it has a note.
    def change(rows):
        return [{**row, "note": "", "public_note": ""}
                if row["assignment_id"] == "A-01.S2" else row for row in rows]

    root = _mutate(tmp_path, "assignments.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S2"
               and "no Accountable party" in e.message for e in errors)


def test_third_party_accountable_under_b14_passes() -> None:
    master = load_master(FIXTURE)
    assert ("A", "TP") in {
        (role.role, role.party_id) for role in master.assignment_roles
        if role.assignment_id == "A-01.S2~v-developer"}
    errors = validate(master, cofog_codes=COFOG, body_uris=BODIES)
    assert not [e for e in errors if "TP" in e.key]


def test_public_note_must_equal_a_note_without_internal_reference(
        tmp_path: Path) -> None:
    def change(rows):
        return [{**row, "public_note": "A different claim."}
                if row["assignment_id"] == "A-01.S2" else row for row in rows]

    root = _mutate(tmp_path, "assignments.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "assignments" and e.key == "A-01.S2"
               and "public_note differs" in e.message for e in errors)


def test_public_prose_must_equal_source_without_internal_reference(
        tmp_path: Path) -> None:
    def change(rows):
        return [{**row, "public_definition": "Rewritten."}
                if row["activity_id"] == "A-01" else row for row in rows]

    root = _mutate(tmp_path, "activities.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "activities" and e.key == "A-01"
               and "public_definition differs" in e.message for e in errors)


def test_public_copy_may_not_cite_an_internal_reference(tmp_path: Path) -> None:
    def change(rows):
        return [{**row, "description": "Executive functions (Decision 3).",
                 "public_description": "Executive functions (F9)."}
                if row["party_id"] == "LA-CE" else row for row in rows]

    root = _mutate(tmp_path, "parties.csv", change)
    errors = validate(load_master(root), cofog_codes=COFOG, body_uris=BODIES)
    assert any(e.table == "parties" and e.key == "LA-CE"
               and "cites an internal reference" in e.message for e in errors)
