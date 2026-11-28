"""Tests for the one-off handoff migration."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.migrate_transport_raci_handoff import main, near_duplicate_variants
from src.lib.transport_raci import Variant, load_master, validate
from src.lib.transport_raci.model import PUBLIC_TEXT_HEADER

REPO = Path(__file__).resolve().parent.parent
HANDOFF = REPO / "docs" / "handoff-l4-raci"
MASTER = REPO / "reference" / "transport-raci"
# Committed inputs and hand-written notes that the migration does not write.
NOT_WRITTEN = {"public_text.csv", "migration_notes.md", "skill_mismatches.md",
               "benchmark.md"}

FIXTURE = Path(__file__).parent / "fixtures" / "transport_raci" / "handoff"
REGISTER = FIXTURE / "register.md"
ASSIGNMENTS = FIXTURE / "assignments.csv"
SOURCES = FIXTURE / "sources.csv"
RESOLUTIONS = FIXTURE / "resolutions.csv"


def migrate(out: Path, resolutions: Path = RESOLUTIONS,
            public_text: Path | None = None,
            register: Path = REGISTER) -> int:
    argv = [
        "--register", str(register),
        "--assignments", str(ASSIGNMENTS),
        "--sources", str(SOURCES),
        "--out", str(out),
        "--resolutions", str(resolutions),
        "--no-count-check",
    ]
    if public_text is not None:
        argv += ["--public-text", str(public_text)]
    return main(argv)


def write_public_text(path: Path, entries: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PUBLIC_TEXT_HEADER, lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            writer.writerow({"reviewed_by": "Test", "date": "2026-11-28",
                             **entry})
    return path


NOTE_ENTRY = {
    "table": "assignments", "key": "T-01.S2~test-variant-one",
    "field": "note", "original": "See F9", "public_text": "Not confirmed.",
}


def roles(master, assignment_id: str) -> list[tuple[str, str, str]]:
    return [
        (role.role, role.party_id, role.qualifier)
        for role in master.assignment_roles
        if role.assignment_id == assignment_id
    ]


def test_migration_maps_exact_values(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert migrate(out) == 0
    master = load_master(out)
    assert validate(master) == []
    assert [assignment.assignment_id for assignment in master.assignments] == [
        "T-01.S1", "T-01.S2~test-variant-one"]
    assert [variant.variant_id for variant in master.variants] == [
        "test-variant-one"]
    assert master.assignments[1].evidence_id == "source"
    assert master.assignments[0].evidence_id == "statute"
    assert sorted(roles(master, "T-01.S1")) == [
        ("A", "LA-CE", ""),
        ("C", "AT", "SRTS"),
        ("C", "DoE", ""),
        ("I", "TP", ""),
        ("R", "DA", "contractor"),
        ("R", "LA-CE", ""),
    ]
    assert len(master.assignment_sources) == 3
    errors = json.loads((out / "migration_errors.json").read_text())
    assert all(error["value"] != "DoE, AT (SRTS)" for error in errors)


def test_not_assessed_line_produces_nothing(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert migrate(out) == 0
    master = load_master(out)
    assert all("ignored" not in assignment.assignment_id
               for assignment in master.assignments)


def test_unmappable_party_is_logged_and_left_out(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert migrate(out) == 0
    master = load_master(out)
    assert all(role.party_id != "mystery bodies"
               for role in master.assignment_roles)
    errors = json.loads((out / "migration_errors.json").read_text())
    assert any(error["value"] == "mystery bodies" for error in errors)


def test_internal_note_is_flagged(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert migrate(out) == 0
    master = load_master(out)
    assignment = next(
        item for item in master.assignments
        if item.assignment_id == "T-01.S2~test-variant-one")
    assert assignment.public_note == ""
    errors = json.loads((out / "migration_errors.json").read_text())
    assert any("needs_public_note" in error["reason"] for error in errors)


def test_stale_ruling_fails(tmp_path: Path) -> None:
    resolutions = tmp_path / "resolutions.csv"
    with RESOLUTIONS.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.append({"error_key": "NOPE|-|C|Nobody", "ruling": "DoE",
                 "ruled_by": "Test", "date": "2026-11-28"})
    with resolutions.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["error_key", "ruling", "ruled_by", "date"],
            lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        migrate(out, resolutions)
    assert not (out / "assignments.csv").exists()


def test_migration_is_byte_identical(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    assert migrate(first) == 0
    assert migrate(second) == 0
    names = sorted(path.name for path in first.iterdir())
    assert names == sorted(path.name for path in second.iterdir())
    for name in names:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_public_text_entry_supplies_the_public_note(tmp_path: Path) -> None:
    public_text = write_public_text(tmp_path / "public_text.csv", [NOTE_ENTRY])
    out = tmp_path / "out"
    assert migrate(out, public_text=public_text) == 0
    master = load_master(out)
    assignment = next(
        item for item in master.assignments
        if item.assignment_id == "T-01.S2~test-variant-one")
    assert assignment.note == "See F9"
    assert assignment.public_note == "Not confirmed."
    errors = json.loads((out / "migration_errors.json").read_text())
    assert not [error for error in errors
                if "needs_public" in error["reason"]]


def test_note_without_internal_reference_is_published_unchanged(
        tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert migrate(out) == 0
    master = load_master(out)
    plain = next(item for item in master.assignments
                 if item.assignment_id == "T-01.S1")
    assert plain.public_note == plain.note == "Plain note"


@pytest.mark.parametrize("change", [
    {"original": "See F10"},                      # source text has changed
    {"key": "T-01.S9"},                           # no such assignment
    {"key": "T-01.S1", "original": "Plain note"},  # source has no reference
])
def test_stale_public_text_fails(tmp_path: Path, change) -> None:
    public_text = write_public_text(
        tmp_path / "public_text.csv", [{**NOTE_ENTRY, **change}])
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        migrate(out, public_text=public_text)
    assert not (out / "assignments.csv").exists()


def test_missing_public_text_for_prose_is_logged(tmp_path: Path) -> None:
    register = tmp_path / "register.md"
    register.write_text(
        REGISTER.read_text(encoding="utf-8").replace(
            "| A test activity. |", "| A test activity (Decision 3). |"),
        encoding="utf-8")
    out = tmp_path / "out"
    assert migrate(out, register=register) == 0
    master = load_master(out)
    activity = master.activities_by_id()["T-01"]
    assert activity.definition == "A test activity (Decision 3)."
    assert activity.public_definition == ""
    assert activity.public_name == activity.name
    errors = json.loads((out / "migration_errors.json").read_text())
    assert any(error["row_id"] == "T-01"
               and error["column"] == "activities.definition"
               and "needs_public_text" in error["reason"] for error in errors)


def test_public_text_entry_supplies_public_prose(tmp_path: Path) -> None:
    register = tmp_path / "register.md"
    register.write_text(
        REGISTER.read_text(encoding="utf-8").replace(
            "| A test activity. |", "| A test activity (Decision 3). |"),
        encoding="utf-8")
    public_text = write_public_text(tmp_path / "public_text.csv", [{
        "table": "activities", "key": "T-01", "field": "definition",
        "original": "A test activity (Decision 3).",
        "public_text": "A test activity.",
    }])
    out = tmp_path / "out"
    assert migrate(out, register=register, public_text=public_text) == 0
    activity = load_master(out).activities_by_id()["T-01"]
    assert activity.definition == "A test activity (Decision 3)."
    assert activity.public_definition == "A test activity."


def test_near_duplicate_variants_are_detected() -> None:
    labels = [
        "NTA-delivered (BusConnects, GDA)", "Royal Canal Greenway",
        "NTA-delivered (BusConnects)", "s.38 route", "s.38 trial",
        "Royal Canal Greenway (Waterways Ireland land)", "LA scheme",
        "LA scheme, NTA-funded (e.g. SRTS, Active Travel)",
    ]
    variants = [Variant(label, label, "") for label in labels]
    assert near_duplicate_variants(variants) == [
        ("NTA-delivered (BusConnects)", "NTA-delivered (BusConnects, GDA)"),
        ("Royal Canal Greenway",
         "Royal Canal Greenway (Waterways Ireland land)"),
    ]
    assert near_duplicate_variants(list(reversed(variants))) == \
        near_duplicate_variants(variants)


@pytest.mark.skipif(not HANDOFF.is_dir(),
                    reason="the handoff is gitignored and absent in CI")
def test_rerun_reproduces_the_committed_master(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main([
        "--register", str(HANDOFF / "L4_Activity_Register_v0.4.md"),
        "--assignments", str(HANDOFF / "L4_RACI_Assignments_v0.1.csv"),
        "--sources", str(HANDOFF / "L4_Sources.csv"),
        "--out", str(out),
        "--resolutions", str(MASTER / "migration_resolutions.csv"),
        "--public-text", str(MASTER / "public_text.csv"),
    ]) == 0
    written = {path.name for path in out.iterdir()}
    committed = {path.name for path in MASTER.iterdir() if path.is_file()}
    assert committed - NOT_WRITTEN == written
    for name in sorted(written):
        assert (out / name).read_bytes() == (MASTER / name).read_bytes(), name


def test_version_marker_needs_public_text(tmp_path: Path) -> None:
    register = tmp_path / "register.md"
    register.write_text(
        REGISTER.read_text(encoding="utf-8").replace(
            "| Department of Education | DoE |",
            "| Department of Education (v0.4) | DoE |"),
        encoding="utf-8")
    out = tmp_path / "out"
    assert migrate(out, register=register) == 0
    party = load_master(out).parties_by_id()["DoE"]
    assert party.name == "Department of Education (v0.4)"
    assert party.public_name == ""
    errors = json.loads((out / "migration_errors.json").read_text())
    assert any(error["row_id"] == "DoE" and error["column"] == "parties.name"
               and "needs_public_text" in error["reason"] for error in errors)
