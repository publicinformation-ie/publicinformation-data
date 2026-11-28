"""Pin the committed transport RACI master.

These tests never read ``docs/handoff-l4-raci/``: the handoff is gitignored, so
CI must be able to check the master on its own.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from src.lib.transport_raci import generate_rows, load_master, validate
from src.lib.transport_raci.model import (
    INTERNAL_REF,
    PUBLIC_TEXT_FIELDS,
    PUBLIC_TEXT_HEADER,
)

REPO = Path(__file__).resolve().parent.parent
MASTER = REPO / "reference" / "transport-raci"
ERRORS = MASTER / "migration_errors.json"
LATEST = REPO / "public" / "latest" / "transport-raci"
HANDOFF = REPO / "docs" / "handoff-l4-raci"

# Lines excluded by recorded rulings. The release gate publishes every migrated
# line, with unresolved roles omitted; a deliberate change to these numbers is a
# reviewed edit to the master.
EXCLUDED_ASSESSED_LINES = 0


def variant_slug(label: str) -> str:
    slug = label.lower().replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def test_committed_master_validates() -> None:
    master = load_master(MASTER)
    assert validate(master) == []


def test_row_counts_are_pinned() -> None:
    rows = generate_rows(load_master(MASTER))
    assert len(rows) == 613
    assert sum(1 for row in rows if row.coverage == "assessed") == 184
    assert rows[0].row_id == "RT-01.S1"


def test_assessed_line_count_is_pinned() -> None:
    master = load_master(MASTER)
    assert len(master.assignments) == 224 - EXCLUDED_ASSESSED_LINES


def published_roles() -> dict[tuple[str, str], list[str]]:
    """Published party IDs keyed by (assignment_id, role)."""
    result: dict[tuple[str, str], list[str]] = {}
    with (LATEST / "assignment-roles.csv").open(
            encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            result.setdefault((row["assignment_id"], row["role"]), []).append(
                row["party"].rsplit("#", 1)[1])
    return result


def role_errors() -> list[dict[str, str]]:
    errors = json.loads(ERRORS.read_text(encoding="utf-8"))
    return [error for error in errors if error["column"] in {"R", "A", "C", "I"}]


def assignment_id_for(row_id: str, variant: str) -> str:
    return f"{row_id}~{variant_slug(variant)}" if variant != "-" else row_id


def test_every_unresolved_role_is_left_out_and_listed() -> None:
    master = load_master(MASTER)
    unresolved = role_errors()
    assert unresolved, "the review list should record unresolved roles"
    published = published_roles()
    master_roles: dict[tuple[str, str], list[str]] = {}
    for line in master.assignment_roles:
        master_roles.setdefault((line.assignment_id, line.role), []).append(
            line.party_id)
    party_ids = {party.party_id for party in master.parties}
    readme = (LATEST / "README.md").read_text(encoding="utf-8")
    assignment_ids = {item.assignment_id for item in master.assignments}
    for error in unresolved:
        row_id, variant, role, token = error["error_key"].split("|", 3)
        assignment_id = assignment_id_for(row_id, variant)
        assert assignment_id in assignment_ids, error["error_key"]
        assert token not in party_ids, error["error_key"]
        key = (assignment_id, role)
        # Published lines are exactly the master's resolved lines.
        assert sorted(published.get(key, [])) == sorted(
            master_roles.get(key, [])), error["error_key"]
        shown = "" if variant == "-" else f" ({variant})"
        assert (f"- `{row_id}`{shown}, role {role}: role not yet published: "
                f"awaiting review (recorded value `{token}`).") in readme


@pytest.mark.skipif(not HANDOFF.is_dir(),
                    reason="the handoff is gitignored and absent in CI")
def test_published_role_counts_equal_resolved_handoff_tokens() -> None:
    unresolved = {error["error_key"] for error in role_errors()}
    with (MASTER / "migration_resolutions.csv").open(
            encoding="utf-8", newline="") as handle:
        rulings = {row["error_key"]: row["ruling"]
                   for row in csv.DictReader(handle)}
    published = published_roles()
    with (HANDOFF / "L4_RACI_Assignments_v0.1.csv").open(
            encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle)
                if row["Evidence"].strip() != "Not assessed"]
    checked = 0
    for row in rows:
        variant = row["Variant"].strip() or "-"
        assignment_id = assignment_id_for(row["Row ID"].strip(), variant)
        for role in ("R", "A", "C", "I"):
            expected = 0
            for token in [t.strip() for t in row[role].split(";") if t.strip()]:
                key = f"{row['Row ID'].strip()}|{variant}|{role}|{token}"
                if key in unresolved:
                    continue
                if key in rulings:
                    expected += len([t for t in rulings[key].split(";")
                                     if t.strip()])
                else:
                    expected += 1
            assert len(published.get((assignment_id, role), [])) == expected, (
                assignment_id, role)
            checked += 1
    assert checked == 224 * 4


def test_rulings_are_applied() -> None:
    published = published_roles()
    assert published[("X-02.S14~speed-limits", "A")] == ["AGS"]
    assert published[("X-02.S14~speed-limits", "R")] == ["AGS"]
    assert {"RSA", "AGS"} <= set(published[("RT-24.S13a", "C")])
    keys = {error["error_key"] for error in role_errors()}
    assert "RT-37.S13b|s.75 closure order (works or events)|C|GS" in keys
    assert "X-02.S14|Speed limits|A|GS" not in keys
    assert "X-02.S14|Speed limits|R|GS" not in keys
    assert sum(1 for error in role_errors() if error["value"] == "GS") == 35


def test_public_copies_equal_sources_without_internal_references() -> None:
    master = load_master(MASTER)
    records = {
        "assignments": master.assignments, "activities": master.activities,
        "stages": master.stages, "parties": master.parties,
    }
    for table, items in records.items():
        for item in items:
            for source_field, public_field in PUBLIC_TEXT_FIELDS[table]:
                source = getattr(item, source_field)
                public = getattr(item, public_field)
                if INTERNAL_REF.search(source):
                    assert public and not INTERNAL_REF.search(public)
                else:
                    assert public == source, (table, item, public_field)


def test_every_public_text_entry_is_for_a_flagged_source() -> None:
    master = load_master(MASTER)
    records = {
        "assignments": {a.assignment_id: a for a in master.assignments},
        "activities": master.activities_by_id(),
        "stages": {s.stage_id: s for s in master.stages},
        "parties": master.parties_by_id(),
    }
    with (MASTER / "public_text.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == PUBLIC_TEXT_HEADER
        entries = list(reader)
    assert entries
    for entry in entries:
        record = records[entry["table"]][entry["key"]]
        assert getattr(record, entry["field"]) == entry["original"]
        assert INTERNAL_REF.search(entry["original"])
        public_field = dict(PUBLIC_TEXT_FIELDS[entry["table"]])[entry["field"]]
        assert getattr(record, public_field) == entry["public_text"]


def test_no_public_text_review_items_remain() -> None:
    errors = json.loads(ERRORS.read_text(encoding="utf-8"))
    assert not [error for error in errors
                if "needs_public" in error["reason"]]
