"""Typed access to the committed transport RACI master tables.

The master lives under ``reference/transport-raci/``. Every table is a CSV with
a fixed header; :func:`load_master` reads them all and fails closed on a
missing table, an unexpected header or a malformed boolean. It performs no
validation of the data itself: :mod:`src.lib.transport_raci.validate` owns the
rules.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

MASTER_DIR = Path(__file__).resolve().parents[3] / "reference" / "transport-raci"

STAGES_FILE = "stages.csv"
GROUPINGS_FILE = "groupings.csv"
ACTIVITIES_FILE = "activities.csv"
ACTIVITY_GROUPINGS_FILE = "activity_groupings.csv"
ACTIVITY_COFOG_FILE = "activity_cofog.csv"
ACTIVITY_STAGES_FILE = "activity_stages.csv"
PARTIES_FILE = "parties.csv"
VARIANTS_FILE = "variants.csv"
EVIDENCE_LEVELS_FILE = "evidence_levels.csv"
BOUNDARY_RULES_FILE = "boundary_rules.csv"
SOURCES_FILE = "sources.csv"
JURISDICTIONS_FILE = "jurisdictions.csv"
ASSIGNMENTS_FILE = "assignments.csv"
ASSIGNMENT_ROLES_FILE = "assignment_roles.csv"
ASSIGNMENT_SOURCES_FILE = "assignment_sources.csv"
MIGRATION_RESOLUTIONS_FILE = "migration_resolutions.csv"
CORRECTIONS_FILE = "corrections.csv"
REVIEW_DECISIONS_FILE = "review_decisions.csv"
# Committed input read by the migration. Its rows are merged into sources.csv,
# after the handoff's sources, so it is not a master table of its own.
ADDED_SOURCES_FILE = "added_sources.csv"

TABLE_FILES = {
    "stages": STAGES_FILE,
    "groupings": GROUPINGS_FILE,
    "activities": ACTIVITIES_FILE,
    "activity_groupings": ACTIVITY_GROUPINGS_FILE,
    "activity_cofog": ACTIVITY_COFOG_FILE,
    "activity_stages": ACTIVITY_STAGES_FILE,
    "parties": PARTIES_FILE,
    "variants": VARIANTS_FILE,
    "evidence_levels": EVIDENCE_LEVELS_FILE,
    "boundary_rules": BOUNDARY_RULES_FILE,
    "sources": SOURCES_FILE,
    "jurisdictions": JURISDICTIONS_FILE,
    "assignments": ASSIGNMENTS_FILE,
    "assignment_roles": ASSIGNMENT_ROLES_FILE,
    "assignment_sources": ASSIGNMENT_SOURCES_FILE,
    "migration_resolutions": MIGRATION_RESOLUTIONS_FILE,
    "corrections": CORRECTIONS_FILE,
    "review_decisions": REVIEW_DECISIONS_FILE,
}

TABLE_FIELDS: dict[str, list[str]] = {
    "stages": ["stage_id", "name", "definition", "sort_order", "public_name",
               "public_definition"],
    "groupings": ["grouping_id", "name", "cofog_class", "cofog_status", "status"],
    "activities": ["activity_id", "name", "definition", "status", "register_note",
                   "public_name", "public_definition"],
    "activity_groupings": ["activity_id", "grouping_id", "is_primary"],
    "activity_cofog": ["activity_id", "cofog_code", "status"],
    "activity_stages": ["activity_id", "stage_id"],
    "parties": ["party_id", "name", "plain_label", "kind", "public_body_uri",
                "parent_party_id", "description", "public_name",
                "public_description"],
    "variants": ["variant_id", "label", "description"],
    "evidence_levels": ["evidence_id", "label", "plain_label", "definition"],
    "boundary_rules": ["rule_id", "rule", "source_decision"],
    "sources": ["source_id", "citation", "urls", "batch"],
    "jurisdictions": ["public_body_uri", "name", "assessed_from", "scope_note"],
    "assignments": ["assignment_id", "activity_id", "stage_id", "variant_id",
                    "applies_to", "evidence_id", "note", "public_note",
                    "scenario_refs"],
    "assignment_roles": ["assignment_id", "role", "party_id", "qualifier",
                         "evidence_id"],
    "assignment_sources": ["assignment_id", "source_id"],
    "migration_resolutions": ["error_key", "ruling", "ruled_by", "date",
                              "evidence_id", "source_ids", "rationale"],
    "corrections": ["table", "key", "field", "original", "corrected",
                    "evidence_id", "source_ids", "rationale", "ruled_by",
                    "date"],
    # A decision on a logged ambiguity that is not a role: a proposed variant
    # merge, or an ambiguous grouping. "keep" records that it was reviewed and
    # left as it is, so it leaves the open review list.
    "review_decisions": ["error_key", "decision", "rationale", "ruled_by",
                         "date"],
}

# What a correction may change, per table. A role line is keyed by
# ``assignment_id|party_id`` and must match exactly one line.
CORRECTABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "activities": ("name", "definition"),
    "stages": ("name", "definition"),
    "parties": ("name", "description"),
    "sources": ("citation", "urls"),
    "assignments": ("note",),
    "assignment_roles": ("role",),
}


def split_ids(value: str) -> list[str]:
    """Split a ``"; "``-separated list of IDs, dropping empty items."""
    return [part.strip() for part in value.split(";") if part.strip()]

BOOLEAN_FIELDS = {("activity_groupings", "is_primary")}

# Internal references that must never reach a published file: finding numbers,
# decision numbers, scenario references from the unpublished test report, and
# register version/history markers such as "(v0.4)", "v0.4:" or "in v0.3".
# The version pattern does not match a versioned path segment such as
# "/v0.1.0/", which is a published dataset URL, not a register marker.
_VERSION_MARKER = r"(?<![/\w.])v\d+\.\d+(?!\w|\.\d)"
_LEAK_TOKENS = (
    r"\bF\d+\b|Decision \d+|\bScenarios?\s+\d+|" + _VERSION_MARKER)
# Every published file is scanned with LEAK_REF. The bare word "scenario" is
# allowed there (the methodology says the method was tested against 14
# scenarios) but it marks master prose for review, so INTERNAL_REF adds it.
LEAK_REF = re.compile(_LEAK_TOKENS, re.IGNORECASE)
INTERNAL_REF = re.compile(_LEAK_TOKENS + r"|\bscenarios?\b", re.IGNORECASE)

# Prose that is published through a reviewed public copy. For each table the
# pairs are (source field, public field). The public field equals the source
# field unless the source cites an internal reference; then it comes from a
# reviewed entry in ``public_text.csv``.
PUBLIC_TEXT_FIELDS: dict[str, list[tuple[str, str]]] = {
    "assignments": [("note", "public_note")],
    "activities": [("name", "public_name"), ("definition", "public_definition")],
    "stages": [("name", "public_name"), ("definition", "public_definition")],
    "parties": [("name", "public_name"), ("description", "public_description")],
}
PUBLIC_TEXT_KEYS = {
    "assignments": "assignment_id",
    "activities": "activity_id",
    "stages": "stage_id",
    "parties": "party_id",
}
PUBLIC_TEXT_FILE = "public_text.csv"
PUBLIC_TEXT_HEADER = [
    "table", "key", "field", "original", "public_text", "reviewed_by", "date"]


@dataclass(frozen=True)
class Stage:
    stage_id: str
    name: str
    definition: str
    sort_order: int
    public_name: str
    public_definition: str


@dataclass(frozen=True)
class Grouping:
    grouping_id: str
    name: str
    cofog_class: str
    cofog_status: str
    status: str


@dataclass(frozen=True)
class Activity:
    activity_id: str
    name: str
    definition: str
    status: str
    register_note: str
    public_name: str
    public_definition: str


@dataclass(frozen=True)
class ActivityGrouping:
    activity_id: str
    grouping_id: str
    is_primary: bool


@dataclass(frozen=True)
class ActivityCofog:
    activity_id: str
    cofog_code: str
    status: str


@dataclass(frozen=True)
class ActivityStage:
    activity_id: str
    stage_id: str


@dataclass(frozen=True)
class Party:
    party_id: str
    name: str
    plain_label: str
    kind: str
    public_body_uri: str
    parent_party_id: str
    description: str
    public_name: str
    public_description: str


@dataclass(frozen=True)
class Variant:
    variant_id: str
    label: str
    description: str


@dataclass(frozen=True)
class EvidenceLevel:
    evidence_id: str
    label: str
    plain_label: str
    definition: str


@dataclass(frozen=True)
class BoundaryRule:
    rule_id: str
    rule: str
    source_decision: str


@dataclass(frozen=True)
class Source:
    source_id: str
    citation: str
    urls: str
    batch: str


@dataclass(frozen=True)
class Jurisdiction:
    public_body_uri: str
    name: str
    assessed_from: str
    scope_note: str


@dataclass(frozen=True)
class Assignment:
    assignment_id: str
    activity_id: str
    stage_id: str
    variant_id: str
    applies_to: str
    evidence_id: str
    note: str
    public_note: str
    scenario_refs: str


@dataclass(frozen=True)
class AssignmentRole:
    assignment_id: str
    role: str
    party_id: str
    qualifier: str
    # Blank: the role takes its assignment's evidence. Set: a ruling or
    # correction supplied the role, with this evidence.
    evidence_id: str = ""


@dataclass(frozen=True)
class AssignmentSource:
    assignment_id: str
    source_id: str


@dataclass(frozen=True)
class MigrationResolution:
    error_key: str
    ruling: str
    ruled_by: str
    date: str
    # Blank: the ruled roles take the line's evidence.
    evidence_id: str = ""
    source_ids: str = ""
    rationale: str = ""


@dataclass(frozen=True)
class ReviewDecision:
    error_key: str
    decision: str
    rationale: str
    ruled_by: str
    date: str


@dataclass(frozen=True)
class Correction:
    table: str
    key: str
    field: str
    original: str
    corrected: str
    evidence_id: str
    source_ids: str
    rationale: str
    ruled_by: str
    date: str


@dataclass(frozen=True)
class Master:
    stages: list[Stage] = field(default_factory=list)
    groupings: list[Grouping] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    activity_groupings: list[ActivityGrouping] = field(default_factory=list)
    activity_cofog: list[ActivityCofog] = field(default_factory=list)
    activity_stages: list[ActivityStage] = field(default_factory=list)
    parties: list[Party] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)
    evidence_levels: list[EvidenceLevel] = field(default_factory=list)
    boundary_rules: list[BoundaryRule] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    jurisdictions: list[Jurisdiction] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    assignment_roles: list[AssignmentRole] = field(default_factory=list)
    assignment_sources: list[AssignmentSource] = field(default_factory=list)
    migration_resolutions: list[MigrationResolution] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    review_decisions: list[ReviewDecision] = field(default_factory=list)

    def activities_by_id(self) -> dict[str, Activity]:
        return {activity.activity_id: activity for activity in self.activities}

    def parties_by_id(self) -> dict[str, Party]:
        return {party.party_id: party for party in self.parties}

    def evidence_by_id(self) -> dict[str, EvidenceLevel]:
        return {level.evidence_id: level for level in self.evidence_levels}

    def sources_by_id(self) -> dict[str, Source]:
        return {source.source_id: source for source in self.sources}


def _read_table(path: Path, table: str) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"master table {table!r} is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = TABLE_FIELDS[table]
        if reader.fieldnames != expected:
            raise ValueError(
                f"{path.name}: expected header {expected!r}, found {reader.fieldnames!r}")
        rows = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"{path.name} line {line_number}: more cells than header columns")
            rows.append({key: (value or "").strip() for key, value in row.items()})
        return rows


def _boolean(value: str, *, table: str, field_name: str, key: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(
        f"{table}: {field_name} for {key!r} must be 'true' or 'false', found {value!r}")


def _integer(value: str, *, table: str, field_name: str, key: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError(
            f"{table}: {field_name} for {key!r} must be an integer, found {value!r}"
        ) from None


def load_master(directory: Path | str | None = None) -> Master:
    """Read every master table into typed records.

    Raises ``ValueError`` for a missing table, a wrong header or a malformed
    boolean/integer. It never validates cross-table rules.
    """
    root = Path(directory) if directory is not None else MASTER_DIR

    def rows(table: str) -> list[dict[str, str]]:
        return _read_table(root / TABLE_FILES[table], table)

    stages = [
        Stage(row["stage_id"], row["name"], row["definition"],
              _integer(row["sort_order"], table="stages", field_name="sort_order",
                       key=row["stage_id"]),
              row["public_name"], row["public_definition"])
        for row in rows("stages")
    ]
    groupings = [
        Grouping(**{key: row[key] for key in TABLE_FIELDS["groupings"]})
        for row in rows("groupings")
    ]
    activities = [
        Activity(**{key: row[key] for key in TABLE_FIELDS["activities"]})
        for row in rows("activities")
    ]
    activity_groupings = [
        ActivityGrouping(
            row["activity_id"], row["grouping_id"],
            _boolean(row["is_primary"], table="activity_groupings",
                     field_name="is_primary",
                     key=f"{row['activity_id']}/{row['grouping_id']}"),
        )
        for row in rows("activity_groupings")
    ]
    activity_cofog = [
        ActivityCofog(**{key: row[key] for key in TABLE_FIELDS["activity_cofog"]})
        for row in rows("activity_cofog")
    ]
    activity_stages = [
        ActivityStage(**{key: row[key] for key in TABLE_FIELDS["activity_stages"]})
        for row in rows("activity_stages")
    ]
    parties = [
        Party(**{key: row[key] for key in TABLE_FIELDS["parties"]})
        for row in rows("parties")
    ]
    variants = [
        Variant(**{key: row[key] for key in TABLE_FIELDS["variants"]})
        for row in rows("variants")
    ]
    evidence_levels = [
        EvidenceLevel(**{key: row[key] for key in TABLE_FIELDS["evidence_levels"]})
        for row in rows("evidence_levels")
    ]
    boundary_rules = [
        BoundaryRule(**{key: row[key] for key in TABLE_FIELDS["boundary_rules"]})
        for row in rows("boundary_rules")
    ]
    sources = [
        Source(**{key: row[key] for key in TABLE_FIELDS["sources"]})
        for row in rows("sources")
    ]
    jurisdictions = [
        Jurisdiction(**{key: row[key] for key in TABLE_FIELDS["jurisdictions"]})
        for row in rows("jurisdictions")
    ]
    assignments = [
        Assignment(**{key: row[key] for key in TABLE_FIELDS["assignments"]})
        for row in rows("assignments")
    ]
    assignment_roles = [
        AssignmentRole(**{key: row[key] for key in TABLE_FIELDS["assignment_roles"]})
        for row in rows("assignment_roles")
    ]
    assignment_sources = [
        AssignmentSource(**{key: row[key] for key in TABLE_FIELDS["assignment_sources"]})
        for row in rows("assignment_sources")
    ]
    migration_resolutions = [
        MigrationResolution(**{
            key: row[key] for key in TABLE_FIELDS["migration_resolutions"]})
        for row in rows("migration_resolutions")
    ]

    corrections = [
        Correction(**{key: row[key] for key in TABLE_FIELDS["corrections"]})
        for row in rows("corrections")
    ]
    review_decisions = [
        ReviewDecision(**{
            key: row[key] for key in TABLE_FIELDS["review_decisions"]})
        for row in rows("review_decisions")
    ]

    return Master(
        stages=stages,
        groupings=groupings,
        activities=activities,
        activity_groupings=activity_groupings,
        activity_cofog=activity_cofog,
        activity_stages=activity_stages,
        parties=parties,
        variants=variants,
        evidence_levels=evidence_levels,
        boundary_rules=boundary_rules,
        sources=sources,
        jurisdictions=jurisdictions,
        assignments=assignments,
        assignment_roles=assignment_roles,
        assignment_sources=assignment_sources,
        migration_resolutions=migration_resolutions,
        corrections=corrections,
        review_decisions=review_decisions,
    )
