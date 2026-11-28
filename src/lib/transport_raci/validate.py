"""Validation rules for the transport RACI master.

Every rule reports a :class:`ValidationError` naming the table and key. The
validator never stops at the first error and never repairs data: a caller that
sees errors must write nothing.

COFOG codes and public-body URIs are passed in, or read from the published
COFOG vocabulary and ``public-bodies`` dataset by :func:`load_cofog_codes` and
:func:`load_body_uris`. Tests pass explicit sets so a fixture does not depend
on the size of the published vocabulary.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .model import (
    CORRECTABLE_FIELDS,
    INTERNAL_REF,
    PUBLIC_TEXT_FIELDS,
    Master,
    split_ids,
)

REPO = Path(__file__).resolve().parents[3]
COFOG_PATH = REPO / "public" / "vocabularies" / "cofog-1999.json"
PUBLIC_BODIES_PATH = (
    REPO / "public" / "latest" / "public-bodies" / "public-bodies.csv")

BOUNDARY_RULE_14 = re.compile(r"\bB14\b")
ROLES = ("R", "A", "C", "I")
KINDS = {"body", "organ", "category"}
ACTIVITY_STATUSES = {"active", "retired", "placeholder"}
GROUPING_STATUSES = {"active", "retired"}
COFOG_STATUSES = {"confirmed", "candidate"}


@dataclass(frozen=True)
class ValidationError:
    table: str
    key: str
    message: str

    def __str__(self) -> str:
        return f"{self.table}[{self.key}]: {self.message}"


class _Errors:
    def __init__(self) -> None:
        self.items: list[ValidationError] = []

    def add(self, table: str, key: str, message: str) -> None:
        self.items.append(ValidationError(table, key, message))

    def unique(self, table: str, entries: list[tuple[str, object]]) -> None:
        seen: set[str] = set()
        for key, _ in entries:
            if key in seen:
                self.add(table, key, "duplicate key")
            seen.add(key)


def load_cofog_codes(path: Path | str = COFOG_PATH) -> set[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {concept["code"] for concept in payload["concepts"]}


def load_body_uris(path: Path | str = PUBLIC_BODIES_PATH) -> set[str]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return {row["id"] for row in csv.DictReader(handle)}


def _key(*parts: object) -> str:
    return "|".join(str(part) for part in parts)


def validate(
    master: Master,
    *,
    cofog_codes: set[str] | None = None,
    body_uris: set[str] | None = None,
) -> list[ValidationError]:
    """Return every validation error; an empty list means the master is sound."""
    if cofog_codes is None:
        cofog_codes = load_cofog_codes()
    if body_uris is None:
        body_uris = load_body_uris()
    errors = _Errors()

    # Unique keys.
    errors.unique("stages", [(s.stage_id, s) for s in master.stages])
    errors.unique("groupings", [(g.grouping_id, g) for g in master.groupings])
    errors.unique("activities", [(a.activity_id, a) for a in master.activities])
    errors.unique("activity_groupings", [
        (_key(link.activity_id, link.grouping_id), link)
        for link in master.activity_groupings])
    errors.unique("activity_cofog", [
        (_key(link.activity_id, link.cofog_code), link)
        for link in master.activity_cofog])
    errors.unique("activity_stages", [
        (_key(link.activity_id, link.stage_id), link)
        for link in master.activity_stages])
    errors.unique("parties", [(p.party_id, p) for p in master.parties])
    errors.unique("variants", [(v.variant_id, v) for v in master.variants])
    errors.unique("evidence_levels", [
        (e.evidence_id, e) for e in master.evidence_levels])
    errors.unique("boundary_rules", [
        (r.rule_id, r) for r in master.boundary_rules])
    errors.unique("sources", [(s.source_id, s) for s in master.sources])
    errors.unique("jurisdictions", [
        (j.public_body_uri, j) for j in master.jurisdictions])
    errors.unique("assignments", [
        (a.assignment_id, a) for a in master.assignments])
    errors.unique("assignment_roles", [
        (_key(r.assignment_id, r.role, r.party_id, r.qualifier), r)
        for r in master.assignment_roles])
    errors.unique("assignment_sources", [
        (_key(s.assignment_id, s.source_id), s)
        for s in master.assignment_sources])
    errors.unique("migration_resolutions", [
        (r.error_key, r) for r in master.migration_resolutions])
    errors.unique("corrections", [
        (_key(c.table, c.key, c.field), c) for c in master.corrections])

    # Value vocabularies.
    for grouping in master.groupings:
        if grouping.status not in GROUPING_STATUSES:
            errors.add("groupings", grouping.grouping_id,
                       f"unknown status {grouping.status!r}")
        if grouping.cofog_class and grouping.cofog_status not in COFOG_STATUSES:
            errors.add("groupings", grouping.grouping_id,
                       f"unknown COFOG status {grouping.cofog_status!r}")
        if not grouping.cofog_class and grouping.cofog_status:
            errors.add("groupings", grouping.grouping_id,
                       "carries a COFOG status without a COFOG code")
    for activity in master.activities:
        if activity.status not in ACTIVITY_STATUSES:
            errors.add("activities", activity.activity_id,
                       f"unknown status {activity.status!r}")
    for party in master.parties:
        if party.kind not in KINDS:
            errors.add("parties", party.party_id,
                       f"unknown kind {party.kind!r}")
    for link in master.activity_cofog:
        if link.status not in COFOG_STATUSES:
            errors.add("activity_cofog",
                       _key(link.activity_id, link.cofog_code),
                       f"unknown COFOG status {link.status!r}")
    for role in master.assignment_roles:
        if role.role not in ROLES:
            errors.add("assignment_roles",
                       _key(role.assignment_id, role.role, role.party_id),
                       f"role must be one of {', '.join(ROLES)}")

    # Indexes. Duplicates keep their first entry; the duplicate is reported above.
    groupings = {}
    for grouping in master.groupings:
        groupings.setdefault(grouping.grouping_id, grouping)
    activities = {}
    for activity in master.activities:
        activities.setdefault(activity.activity_id, activity)
    stages = {}
    for stage in master.stages:
        stages.setdefault(stage.stage_id, stage)
    parties = {}
    for party in master.parties:
        parties.setdefault(party.party_id, party)
    variants = {}
    for variant in master.variants:
        variants.setdefault(variant.variant_id, variant)
    evidence = {}
    for level in master.evidence_levels:
        evidence.setdefault(level.evidence_id, level)
    sources = {source.source_id for source in master.sources}
    jurisdictions = {
        jurisdiction.public_body_uri for jurisdiction in master.jurisdictions}
    assignments = {}
    for assignment in master.assignments:
        assignments.setdefault(assignment.assignment_id, assignment)
    stage_links = {
        (link.activity_id, link.stage_id) for link in master.activity_stages}

    # COFOG codes resolve; no label or hierarchy is copied into the master.
    for grouping in master.groupings:
        if grouping.cofog_class and grouping.cofog_class not in cofog_codes:
            errors.add("groupings", grouping.grouping_id,
                       f"COFOG code {grouping.cofog_class!r} is not in the "
                       "published COFOG vocabulary")
    for link in master.activity_cofog:
        if link.cofog_code not in cofog_codes:
            errors.add("activity_cofog",
                       _key(link.activity_id, link.cofog_code),
                       f"COFOG code {link.cofog_code!r} is not in the published "
                       "COFOG vocabulary")

    # Foreign keys in the axis tables.
    for link in master.activity_groupings:
        if link.activity_id not in activities:
            errors.add("activity_groupings",
                       _key(link.activity_id, link.grouping_id),
                       "unknown activity")
        if link.grouping_id not in groupings:
            errors.add("activity_groupings",
                       _key(link.activity_id, link.grouping_id),
                       "unknown grouping")
    for link in master.activity_cofog:
        if link.activity_id not in activities:
            errors.add("activity_cofog", _key(link.activity_id, link.cofog_code),
                       "unknown activity")
    for link in master.activity_stages:
        if link.activity_id not in activities:
            errors.add("activity_stages", _key(link.activity_id, link.stage_id),
                       "unknown activity")
        if link.stage_id not in stages:
            errors.add("activity_stages", _key(link.activity_id, link.stage_id),
                       "unknown stage")

    # Parties link to public bodies, or carry an empty URI when no entry exists.
    for party in master.parties:
        if party.kind == "body" and party.public_body_uri:
            if party.public_body_uri not in body_uris:
                errors.add("parties", party.party_id,
                           f"public-body URI {party.public_body_uri!r} is not in "
                           "the public-bodies dataset")
        if party.parent_party_id and party.parent_party_id not in parties:
            errors.add("parties", party.party_id,
                       f"unknown parent party {party.parent_party_id!r}")

    # Jurisdictions are public bodies.
    for jurisdiction in master.jurisdictions:
        if jurisdiction.public_body_uri not in body_uris:
            errors.add("jurisdictions", jurisdiction.public_body_uri,
                       "URI is not in the public-bodies dataset")

    # Activity grouping rule: exactly one primary grouping for an active activity.
    by_activity: dict[str, list[bool]] = {}
    for link in master.activity_groupings:
        by_activity.setdefault(link.activity_id, []).append(link.is_primary)
    for activity in master.activities:
        primaries = sum(1 for value in by_activity.get(activity.activity_id, [])
                        if value)
        if activity.status == "active":
            if not by_activity.get(activity.activity_id):
                errors.add("activities", activity.activity_id,
                           "active activity has no grouping")
            elif primaries != 1:
                errors.add("activities", activity.activity_id,
                           f"active activity has {primaries} primary groupings, "
                           "expected exactly one")
        elif primaries > 1:
            errors.add("activities", activity.activity_id,
                       f"activity has {primaries} primary groupings, expected at most one")

    # Retired and placeholder activities have no stages and no assignments.
    retired = {activity.activity_id for activity in master.activities
               if activity.status != "active"}
    for link in master.activity_stages:
        if link.activity_id in retired:
            errors.add("activity_stages", _key(link.activity_id, link.stage_id),
                       "retired or placeholder activity must have no stages")

    # The sparse matrix resolves every reference.
    combinations: dict[str, str] = {}
    for assignment in master.assignments:
        key = assignment.assignment_id
        if assignment.activity_id not in activities:
            errors.add("assignments", key, "unknown activity")
        if assignment.stage_id not in stages:
            errors.add("assignments", key, "unknown stage")
        if (assignment.activity_id, assignment.stage_id) not in stage_links:
            errors.add("assignments", key,
                       f"{assignment.activity_id}.{assignment.stage_id} is not an "
                       "activity-stage link")
        if assignment.activity_id in retired:
            errors.add("assignments", key,
                       "retired or placeholder activity must have no assignments")
        if assignment.variant_id and assignment.variant_id not in variants:
            errors.add("assignments", key,
                       f"unknown variant {assignment.variant_id!r}")
        if assignment.applies_to not in jurisdictions:
            errors.add("assignments", key,
                       f"unknown jurisdiction {assignment.applies_to!r}")
        if assignment.evidence_id not in evidence:
            errors.add("assignments", key,
                       f"unknown evidence level {assignment.evidence_id!r}")
        combination = _key(assignment.activity_id, assignment.stage_id,
                           assignment.variant_id, assignment.applies_to)
        if combination in combinations:
            errors.add("assignments", key,
                       "duplicate (activity, stage, variant, jurisdiction) "
                       f"combination already used by {combinations[combination]}")
        else:
            combinations[combination] = key

    # Role lines resolve, and accountability rules hold.
    roles_by_assignment: dict[str, list] = {}
    for role in master.assignment_roles:
        key = _key(role.assignment_id, role.role, role.party_id)
        if role.assignment_id not in assignments:
            errors.add("assignment_roles", key, "unknown assignment")
            continue
        if role.party_id not in parties:
            errors.add("assignment_roles", key,
                       f"unknown party {role.party_id!r}")
        roles_by_assignment.setdefault(role.assignment_id, []).append(role)

    for assignment in master.assignments:
        lines = roles_by_assignment.get(assignment.assignment_id, [])
        accountable = [line for line in lines if line.role == "A"]
        consulted = [line for line in lines if line.role == "C"]
        if len(accountable) > 1:
            errors.add("assignments", assignment.assignment_id,
                       f"has {len(accountable)} Accountable parties, expected at most one")
        if not accountable:
            if (assignment.evidence_id != "unverified"
                    or not assignment.note.strip()):
                errors.add("assignments", assignment.assignment_id,
                           "has no Accountable party; only an unverified "
                           "assignment with a note may omit it")
        accountable_parties = {line.party_id for line in accountable}
        consulted_parties = {line.party_id for line in consulted}
        both = sorted(accountable_parties & consulted_parties)
        if both:
            errors.add("assignments", assignment.assignment_id,
                       f"party {', '.join(both)} is both Accountable and Consulted")
        for line in accountable:
            party = parties.get(line.party_id)
            if party is None:
                continue  # reported above
            if party.kind != "category":
                continue
            if line.party_id == "TP" and BOUNDARY_RULE_14.search(assignment.note):
                continue
            errors.add("assignment_roles",
                       _key(assignment.assignment_id, "A", line.party_id),
                       "a category party cannot be Accountable except TP under B14")

    # Public copies of prose. A source text without an internal reference is
    # published unchanged; a public copy never carries an internal reference.
    # An empty public copy of a flagged text is allowed here (the migration
    # logs it for review) and blocked by the generator's leak check.
    public_records: list[tuple[str, str, object]] = [
        *(("assignments", item.assignment_id, item) for item in master.assignments),
        *(("activities", item.activity_id, item) for item in master.activities),
        *(("stages", item.stage_id, item) for item in master.stages),
        *(("parties", item.party_id, item) for item in master.parties),
    ]
    for table, key, record in public_records:
        for source_field, public_field in PUBLIC_TEXT_FIELDS[table]:
            source = getattr(record, source_field)
            public = getattr(record, public_field)
            if not INTERNAL_REF.search(source):
                if public != source:
                    errors.add(table, key,
                               f"{public_field} differs from {source_field}, "
                               "which cites no internal reference")
            elif INTERNAL_REF.search(public):
                errors.add(table, key,
                           f"{public_field} cites an internal reference")

    for link in master.assignment_sources:
        key = _key(link.assignment_id, link.source_id)
        if link.assignment_id not in assignments:
            errors.add("assignment_sources", key, "unknown assignment")
        if link.source_id not in sources:
            errors.add("assignment_sources", key,
                       f"unknown source {link.source_id!r}")

    _validate_evidence_inputs(master, errors, evidence, sources, assignments)
    return errors.items


def _validate_evidence_inputs(
    master: Master,
    errors: _Errors,
    evidence: dict,
    sources: set[str],
    assignments: dict,
) -> None:
    """Per-role evidence, rulings with evidence and corrections.

    A ruling or correction that sets evidence must cite sources and give a
    rationale; a rationale never cites an internal reference. A correction's
    ``corrected`` value must equal what the master now holds, so a hand edit
    to a corrected field is detected.
    """
    sources_by_assignment: dict[str, int] = {}
    for link in master.assignment_sources:
        sources_by_assignment[link.assignment_id] = (
            sources_by_assignment.get(link.assignment_id, 0) + 1)
    for role in master.assignment_roles:
        key = _key(role.assignment_id, role.role, role.party_id)
        if role.evidence_id and role.evidence_id not in evidence:
            errors.add("assignment_roles", key,
                       f"unknown evidence level {role.evidence_id!r}")
        if (role.evidence_id and role.assignment_id in assignments
                and not sources_by_assignment.get(role.assignment_id)):
            errors.add("assignment_roles", key,
                       "role has its own evidence but its assignment cites "
                       "no source")

    for resolution in master.migration_resolutions:
        _check_basis(
            errors, "migration_resolutions", resolution.error_key,
            resolution.evidence_id, resolution.source_ids,
            resolution.rationale, evidence, sources)

    by_table: dict[str, dict[str, object]] = {
        "activities": {a.activity_id: a for a in master.activities},
        "stages": {s.stage_id: s for s in master.stages},
        "parties": {p.party_id: p for p in master.parties},
        "sources": {s.source_id: s for s in master.sources},
        "assignments": {a.assignment_id: a for a in master.assignments},
    }
    for correction in master.corrections:
        key = _key(correction.table, correction.key, correction.field)
        fields = CORRECTABLE_FIELDS.get(correction.table)
        if fields is None or correction.field not in fields:
            errors.add("corrections", key,
                       "table or field cannot be corrected")
            continue
        _check_basis(
            errors, "corrections", key, correction.evidence_id,
            correction.source_ids, correction.rationale, evidence, sources)
        if not correction.rationale.strip():
            errors.add("corrections", key, "rationale is required")
        if not correction.ruled_by.strip() or not correction.date.strip():
            errors.add("corrections", key, "ruled_by and date are required")
        if correction.table == "assignment_roles":
            if not correction.evidence_id:
                errors.add("corrections", key,
                           "a role correction must set evidence_id")
            assignment_id, _, party_id = correction.key.partition("|")
            lines = [line for line in master.assignment_roles
                     if line.assignment_id == assignment_id
                     and line.party_id == party_id]
            if len(lines) != 1:
                errors.add("corrections", key,
                           f"matches {len(lines)} role lines, expected one")
            elif (lines[0].role != correction.corrected
                  or lines[0].evidence_id != correction.evidence_id):
                errors.add("corrections", key,
                           "the master role line does not carry the "
                           "corrected role and evidence")
            continue
        record = by_table[correction.table].get(correction.key)
        if record is None:
            errors.add("corrections", key, "no such record")
        elif getattr(record, correction.field) != correction.corrected:
            errors.add("corrections", key,
                       "the master does not hold the corrected value")


def _check_basis(
    errors: _Errors, table: str, key: str, evidence_id: str, source_ids: str,
    rationale: str, evidence: dict, sources: set[str],
) -> None:
    cited = split_ids(source_ids)
    if evidence_id and evidence_id not in evidence:
        errors.add(table, key, f"unknown evidence level {evidence_id!r}")
    if bool(evidence_id) != bool(cited):
        errors.add(table, key,
                   "evidence_id and source_ids must be set together")
    if evidence_id and not rationale.strip():
        errors.add(table, key, "evidence needs a rationale")
    for source_id in cited:
        if source_id not in sources:
            errors.add(table, key, f"unknown source {source_id!r}")
    if INTERNAL_REF.search(rationale):
        errors.add(table, key, "rationale cites an internal reference")
