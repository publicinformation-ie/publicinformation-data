#!/usr/bin/env python3
"""Migrate the L4 RACI handoff into the committed master tables.

Usage:
    uv run python scripts/migrate_transport_raci_handoff.py \
        --register docs/handoff-l4-raci/L4_Activity_Register_v0.4.md \
        --assignments docs/handoff-l4-raci/L4_RACI_Assignments_v0.1.csv \
        --sources docs/handoff-l4-raci/L4_Sources.csv \
        --out reference/transport-raci/

The migration is deterministic. It reads the register's Sections 3, 4, 5 and 6
and the assignments CSV, writes every table it can map by an exact rule, and
logs every value it cannot map to ``migration_errors.json``. It never guesses:
an unmappable party token is left out of the master until a human ruling in
``migration_resolutions.csv`` supplies a replacement. Prose that cites an
internal reference is published only through a reviewed entry in
``public_text.csv``; the original text stays in the master. Re-running with
both committed inputs reproduces every output byte for byte.

The handoff lives in ``docs/`` and is gitignored. This script is kept for
traceability but is not part of the regular build; after migration the master
tables are the source of truth.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.lib.transport_raci.model import (  # noqa: E402
    Activity,
    ActivityCofog,
    ActivityGrouping,
    ActivityStage,
    Assignment,
    AssignmentRole,
    AssignmentSource,
    BoundaryRule,
    INTERNAL_REF,
    PUBLIC_TEXT_FIELDS,
    PUBLIC_TEXT_FILE,
    PUBLIC_TEXT_HEADER,
    PUBLIC_TEXT_KEYS,
    EvidenceLevel,
    Grouping,
    Jurisdiction,
    Master,
    MigrationResolution,
    Party,
    Source,
    Stage,
    TABLE_FIELDS,
    TABLE_FILES,
    Variant,
)
from src.lib.transport_raci.rows import generate_rows  # noqa: E402
from src.lib.transport_raci.validate import validate  # noqa: E402

MEATH_URI = "https://data.publicinformation.ie/body/meath-county-council"
MEATH_NAME = "Meath County Council"
ASSESSED_FROM = "2026-11-19"
MEATH_SCOPE = (
    "Assignments have been analysed for Meath County Council only. They may "
    "differ for other councils. Meath is in the Greater Dublin Area.")

STAGE_ID = re.compile(r"\bS\d+(?:[A-Za-z])?\b")
COFOG_CODE = re.compile(r"\b\d{2}(?:\.\d+){0,2}\b")
VARIANT_DESCRIPTION = "A variant recorded on an assignment."

def find_cofog_code(value: str) -> str:
    matches = COFOG_CODE.findall(value)
    return max(matches, key=len) if matches else ""


EVIDENCE_LEVELS = [
    EvidenceLevel(
        "statute", "Statute", "set by law",
        "The role is set by statute."),
    EvidenceLevel(
        "source", "Source", "stated in official guidance or observed practice",
        "The role is stated in official guidance or observed in practice."),
    EvidenceLevel(
        "default-s149-4", "Default (s.149(4))",
        "assumed by default (an executive function because it is not reserved "
        "to elected members)",
        "The role is assumed from the s.149(4) Local Government Act 2001 "
        "default for executive functions."),
    EvidenceLevel(
        "unverified", "UNVERIFIED", "not yet confirmed",
        "The role is recorded but has not been confirmed."),
]

EVIDENCE_MAP = {
    "Statute": "statute",
    "Source": "source",
    "Default (s.149(4))": "default-s149-4",
    "UNVERIFIED": "unverified",
}

# kind, plain label, public-bodies URI, parent party
PARTY_META: dict[str, tuple[str, str, str, str]] = {
    "DoT": ("body", "the Department of Transport",
            "https://data.publicinformation.ie/body/department-of-transport", ""),
    "NTA": ("body", "the National Transport Authority",
            "https://data.publicinformation.ie/body/national-transport-authority-nta", ""),
    "TII": ("body", "Transport Infrastructure Ireland",
            "https://data.publicinformation.ie/body/transport-infrastructure-ireland", ""),
    "DHLGH": ("body", "the Department of Housing, Local Government and Heritage",
              "https://data.publicinformation.ie/body/"
              "department-of-housing-local-government-and-heritage", ""),
    "DoE": ("body", "the Department of Education",
            "https://data.publicinformation.ie/body/department-of-education-and-youth", ""),
    "DRCD": ("body", "the Department of Rural and Community Development",
             "https://data.publicinformation.ie/body/"
             "department-of-rural-and-community-development-and-the-gaeltacht", ""),
    "ACP": ("body", "An Coimisiún Pleanála, the national planning body",
            "https://data.publicinformation.ie/body/an-coimisiun-pleanala", ""),
    # Organ labels name "the council"; the generator substitutes the council
    # named by each assignment's jurisdiction.
    "LA-M": ("organ", "the elected members of the council", "", ""),
    "LA-CE": ("organ",
              "the Chief Executive and executive of the council", "", ""),
    "RMO": ("body", "the Road Management Office", "", ""),
    "WI": ("body", "Waterways Ireland",
           "https://data.publicinformation.ie/body/waterways-ireland", ""),
    "OPS": ("category", "public transport operators", "", ""),
    "DA": ("category", "delivery agents", "", ""),
    "AT": ("category", "An Taisce", "", ""),
    "SCH": ("category", "schools and boards of management", "", ""),
    "PP": ("category", "programme partners", "", ""),
    "TP": ("category", "third parties", "", ""),
}

# Public copies are filled in by ``apply_public_text``.
EXTRA_PARTIES = [
    Party("AGS", "An Garda Síochána", "the Gardaí",
          "body", "https://data.publicinformation.ie/body/an-garda-siochana",
          "", "The national police service.", "", ""),
    Party("RSA", "Road Safety Authority", "the Road Safety Authority",
          "body", "https://data.publicinformation.ie/body/road-safety-authority",
          "", "The national road safety body.", "", ""),
    Party("prescribed-bodies", "Prescribed bodies", "prescribed bodies",
          "category", "", "",
          "Statutory consultees under the Part 8 regulations.", "", ""),
]

def section(text: str, number: int) -> list[str]:
    """Return the lines of one numbered top-level section."""
    lines = text.splitlines()
    start = next(
        index for index, line in enumerate(lines)
        if line.startswith(f"## {number}."))
    result = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        result.append(line)
    return result


def table(lines: list[str]) -> list[list[str]]:
    """Parse the first markdown table in ``lines`` into cells, minus its header."""
    tables = all_tables(lines)
    if not tables:
        raise ValueError("no markdown table found")
    return tables[0]


def all_tables(lines: list[str]) -> list[list[list[str]]]:
    """Parse every markdown table in ``lines``, dropping headers and separators."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if current:
                tables.append(current[1:])
                current = []
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        current.append(cells)
    if current:
        tables.append(current[1:])
    return [rows for rows in tables if rows]


def split_outside_parentheses(value: str, separator: str) -> list[str]:
    parts, current, depth = [], [], 0
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == separator and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def parse_groupings(text: str) -> list[Grouping]:
    groupings: list[Grouping] = []
    for line in section(text, 3):
        match = re.match(r"^\*\*(?P<prefix>[^*]+):\*\*\s*(?P<entries>.+)$", line)
        if not match:
            continue
        prefix = match.group("prefix").strip()
        base_code = find_cofog_code(prefix)
        cross_cutting = prefix.lower().startswith("outside")
        for entry in split_outside_parentheses(match.group("entries"), ";"):
            entry_match = re.match(
                r"^(?P<id>[A-Z]{1,2}\d+)\s+(?P<rest>.+)$", entry)
            if not entry_match:
                raise ValueError(f"unparseable grouping entry: {entry!r}")
            grouping_id = entry_match.group("id")
            rest = entry_match.group("rest").strip()
            annotation = ""
            name_match = re.match(r"^(?P<name>.*?)\s*\((?P<ann>[^()]*)\)$", rest)
            if name_match:
                rest = name_match.group("name").strip()
                annotation = name_match.group("ann")
            if cross_cutting:
                cofog_class = find_cofog_code(annotation)
                cofog_status = (
                    "candidate" if "candidate" in annotation.lower()
                    else "confirmed") if cofog_class else ""
            else:
                cofog_class = base_code
                cofog_status = "confirmed" if cofog_class else ""
            status = "retired" if "retired" in annotation.lower() else "active"
            groupings.append(Grouping(
                grouping_id, rest, cofog_class, cofog_status, status))
    return groupings


def parse_stages(text: str) -> list[Stage]:
    stages = []
    for order, cells in enumerate(table(section(text, 4)), start=1):
        stage_id, name, definition = cells[:3]
        stages.append(Stage(stage_id, name, definition, order, "", ""))
    return stages


def parse_activities(
    text: str,
) -> tuple[list[Activity], list[ActivityGrouping], list[ActivityStage],
           list[tuple[str, str, str]]]:
    activities: list[Activity] = []
    links: list[ActivityGrouping] = []
    stage_links: list[ActivityStage] = []
    grouping_notes: list[tuple[str, str, str]] = []
    for cells in table(section(text, 6)):
        activity_id, cofog_cell, grouping_cell, name, definition, stages, note = \
            cells[:7]
        lowered = f"{note} {stages}".lower()
        if "placeholder" in lowered:
            status = "placeholder"
        elif "retired" in lowered:
            status = "retired"
        else:
            status = "active"
        activities.append(Activity(
            activity_id, name, definition, status, note, "", ""))
        grouping_tokens = [token.strip()
                           for token in grouping_cell.split(" / ")
                           if token.strip()]
        resolved: list[str] = []
        for token in grouping_tokens:
            if re.fullmatch(r"[A-Z]{1,2}\d+-[A-Z]{1,2}\d+", token):
                grouping_notes.append((
                    activity_id, "Grouping", grouping_cell))
                continue
            match = re.match(r"^([A-Z]{1,2}\d+)\b", token)
            if match:
                resolved.append(match.group(1))
            else:
                grouping_notes.append((
                    activity_id, "Grouping", grouping_cell))
        for index, grouping_id in enumerate(resolved):
            links.append(ActivityGrouping(
                activity_id, grouping_id, index == 0))
        if status == "active" and ":" in stages:
            stage_part = stages.split(":", 1)[1]
            for stage_id in STAGE_ID.findall(stage_part):
                stage_links.append(ActivityStage(activity_id, stage_id))
    return activities, links, stage_links, grouping_notes


def parse_activity_cofog(
    activities: list[Activity],
    links: list[ActivityGrouping],
    groupings: list[Grouping],
) -> list[ActivityCofog]:
    grouping_by_id = {grouping.grouping_id: grouping for grouping in groupings}
    links_by_activity: dict[str, list[ActivityGrouping]] = {}
    for link in links:
        links_by_activity.setdefault(link.activity_id, []).append(link)
    rows: list[ActivityCofog] = []
    for activity in activities:
        activity_links = links_by_activity.get(activity.activity_id, [])
        if not activity_links:
            continue
        primary = next(
            (link for link in activity_links if link.is_primary), None)
        primary_grouping = (
            grouping_by_id.get(primary.grouping_id) if primary else None)
        if (len(activity_links) == 1 and primary_grouping
                and primary_grouping.cofog_status == "confirmed"):
            continue
        seen: set[str] = set()
        for link in activity_links:
            grouping = grouping_by_id.get(link.grouping_id)
            if grouping is None or not grouping.cofog_class:
                continue
            if grouping.cofog_class in seen:
                continue
            seen.add(grouping.cofog_class)
            rows.append(ActivityCofog(
                activity.activity_id, grouping.cofog_class,
                grouping.cofog_status))
    return rows


def parse_parties(text: str) -> list[Party]:
    parties: list[Party] = []
    for cells in table(section(text, 5)):
        name, party_id, why = cells[:3]
        if party_id == "GS":
            continue
        meta = PARTY_META.get(party_id)
        if meta is None:
            raise ValueError(f"register party {party_id!r} has no mapping")
        kind, plain_label, uri, parent = meta
        parties.append(Party(
            party_id, name, plain_label, kind, uri, parent, why, "", ""))
    parties.extend(EXTRA_PARTIES)
    return parties


def parse_boundary_rules(text: str) -> list[BoundaryRule]:
    rules = []
    for rows in all_tables(section(text, 4)):
        for cells in rows:
            if not cells or not cells[0].startswith("B"):
                continue
            rule_id, rule, source_decision = cells[:3]
            rules.append(BoundaryRule(rule_id, rule, source_decision))
    return rules


def parse_sources(path: Path) -> list[Source]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            Source(row["Source ID"].strip(), row["Citation"].strip(),
                   row["URLs"].strip(), row["Batch"].strip())
            for row in csv.DictReader(handle)
        ]


def variant_slug(label: str) -> str:
    slug = label.lower().replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def split_party_cell(cell: str) -> list[str]:
    return [token.strip() for token in cell.split(";") if token.strip()]


def parse_party_token(
    token: str, party_ids: set[str]
) -> list[tuple[str, str]] | None:
    """Return (party_id, qualifier) pairs, or None when the token is unmappable."""
    if token in party_ids:
        return [(token, "")]
    match = re.match(r"^(?P<id>[^()]+?)\s*\((?P<qualifier>[^()]*)\)$", token)
    if match and match.group("id").strip() in party_ids:
        return [(match.group("id").strip(), match.group("qualifier").strip())]
    return None


def read_public_text(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    """Read the reviewed public copies, keyed by (table, key, field)."""
    entries: dict[tuple[str, str, str], dict[str, str]] = {}
    if not path.exists():
        return entries
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != PUBLIC_TEXT_HEADER:
            raise ValueError(
                f"{path.name}: unexpected header {reader.fieldnames!r}")
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"{path.name} line {line_number}: more cells than header")
            entry = {key: (value or "") for key, value in row.items()}
            index = (entry["table"], entry["key"], entry["field"])
            if index in entries:
                raise ValueError(
                    f"{path.name} line {line_number}: duplicate entry {index!r}")
            if not entry["public_text"].strip():
                raise ValueError(
                    f"{path.name} line {line_number}: empty public_text")
            entries[index] = entry
    return entries


class PublicText:
    """Resolve the public copy of each prose field, tracking what is used.

    A field whose source text cites no internal reference is published as is.
    A field that does cite one takes the reviewed entry for that exact
    (table, key, field); without one, ``needs`` records it and the public copy
    stays empty. An entry is stale when its ``original`` no longer equals the
    source text, when it names a field that cites no internal reference, or
    when nothing asks for it.
    """

    def __init__(self, entries: dict[tuple[str, str, str], dict[str, str]]):
        self.entries = entries
        self.used: set[tuple[str, str, str]] = set()
        self.stale: list[str] = []
        self.needs: list[tuple[str, str, str, str]] = []

    def resolve(self, table: str, key: str, field: str, source: str) -> str:
        index = (table, key, field)
        entry = self.entries.get(index)
        if entry is not None:
            self.used.add(index)
        if not INTERNAL_REF.search(source):
            if entry is not None:
                self.stale.append(
                    f"{table}|{key}|{field}: source cites no internal "
                    "reference, so no public_text entry is allowed")
            return source
        if entry is None:
            self.needs.append((table, key, field, source))
            return ""
        if entry["original"] != source:
            self.stale.append(
                f"{table}|{key}|{field}: original no longer matches the "
                "source text")
            return ""
        if INTERNAL_REF.search(entry["public_text"]):
            self.stale.append(
                f"{table}|{key}|{field}: public_text cites an internal "
                "reference")
            return ""
        return entry["public_text"]

    def unused(self) -> list[str]:
        return [f"{table}|{key}|{field}: no such record or field"
                for table, key, field in sorted(set(self.entries) - self.used)]


def apply_public_text(public_text: PublicText, table: str, records: list):
    key_field = PUBLIC_TEXT_KEYS[table]
    result = []
    for record in records:
        key = getattr(record, key_field)
        changes = {
            public_field: public_text.resolve(
                table, key, source_field, getattr(record, source_field))
            for source_field, public_field in PUBLIC_TEXT_FIELDS[table]
        }
        result.append(replace(record, **changes))
    return result


def near_duplicate_variants(variants: list[Variant]) -> list[tuple[str, str]]:
    """Pairs of variant labels with the same stem before the first " (".

    For example "NTA-delivered (BusConnects)" and "NTA-delivered (BusConnects,
    GDA)", or "Royal Canal Greenway" and "Royal Canal Greenway (Waterways
    Ireland land)". Pairs are sorted, and each pair's labels are sorted.
    """
    by_stem: dict[str, list[str]] = {}
    for variant in variants:
        stem = variant.label.split(" (", 1)[0].strip().casefold()
        by_stem.setdefault(stem, []).append(variant.label)
    pairs: list[tuple[str, str]] = []
    for labels in by_stem.values():
        ordered = sorted(set(labels))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                pairs.append((left, right))
    return sorted(pairs)


def run(args: argparse.Namespace) -> int:
    register = args.register.read_text(encoding="utf-8")
    groupings = parse_groupings(register)
    stages = parse_stages(register)
    activities, activity_groupings, activity_stages, grouping_notes = \
        parse_activities(register)
    activity_cofog = parse_activity_cofog(
        activities, activity_groupings, groupings)
    parties = parse_parties(register)
    boundary_rules = parse_boundary_rules(register)
    sources = parse_sources(args.sources)
    parties_by_id = {party.party_id: party for party in parties}
    source_ids = {source.source_id for source in sources}

    resolutions_path = (
        args.resolutions if args.resolutions is not None
        else args.out / "migration_resolutions.csv")
    resolutions: dict[str, MigrationResolution] = {}
    if resolutions_path.exists():
        with resolutions_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != TABLE_FIELDS["migration_resolutions"]:
                raise ValueError(
                    f"{resolutions_path.name}: unexpected header "
                    f"{reader.fieldnames!r}")
            for row in reader:
                resolutions[row["error_key"].strip()] = MigrationResolution(
                    row["error_key"].strip(), row["ruling"].strip(),
                    row["ruled_by"].strip(), row["date"].strip())

    public_text_path = (
        args.public_text if args.public_text is not None
        else args.out / PUBLIC_TEXT_FILE)
    public_text = PublicText(read_public_text(public_text_path))
    stages = apply_public_text(public_text, "stages", stages)
    activities = apply_public_text(public_text, "activities", activities)
    parties = apply_public_text(public_text, "parties", parties)
    parties_by_id = {party.party_id: party for party in parties}

    errors: dict[str, dict[str, str]] = {}
    encountered: set[str] = set()

    def log(row_id: str, column: str, value: str, reason: str,
            variant: str = "-") -> str:
        key = f"{row_id}|{variant}|{column}|{value}"
        encountered.add(key)
        errors.setdefault(key, {
            "error_key": key, "row_id": row_id, "column": column,
            "value": value, "reason": reason})
        return key

    for activity_id, column, value in grouping_notes:
        log(activity_id, column, value,
            "grouping range or unresolved grouping; first clean grouping used")

    for table_name, key, field_name, source in public_text.needs:
        log(key, f"{table_name}.{field_name}", source,
            "needs_public_text: text cites an internal reference")

    variants: dict[str, Variant] = {}
    assignments: list[Assignment] = []
    roles: list[AssignmentRole] = []
    assignment_sources: list[AssignmentSource] = []

    with args.assignments.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        row_id = row["Row ID"].strip()
        if row["Evidence"].strip() == "Not assessed":
            continue
        variant_label = row["Variant"].strip()
        variant_id = variant_slug(variant_label) if variant_label else ""
        if variant_id and variant_id not in variants:
            variants[variant_id] = Variant(
                variant_id, variant_label, VARIANT_DESCRIPTION)
        assignment_id = (
            f"{row_id}~{variant_id}" if variant_id else row_id)
        evidence = EVIDENCE_MAP.get(row["Evidence"].strip())
        if evidence is None:
            log(row_id, "Evidence", row["Evidence"].strip(),
                "evidence label has no exact mapping", variant_label or "-")
            continue
        note = row["Note"].strip()
        needs_before = len(public_text.needs)
        public_note = public_text.resolve(
            "assignments", assignment_id, "note", note)
        if len(public_text.needs) > needs_before:
            public_text.needs.pop()
            log(row_id, "Note", note,
                "needs_public_note: note cites an internal reference",
                variant_label or "-")
        assignments.append(Assignment(
            assignment_id, row["Activity ID"].strip(), row["Stage"].strip(),
            variant_id, MEATH_URI, evidence, note, public_note,
            row["Scenario"].strip()))

        for role in ("R", "A", "C", "I"):
            for token in split_party_cell(row[role]):
                parsed = parse_party_token(token, set(parties_by_id))
                if parsed is None:
                    key = log(row_id, role, token,
                              "party token does not resolve to a known party",
                              variant_label or "-")
                    resolution = resolutions.get(key)
                    if resolution is None:
                        continue
                    errors.pop(key, None)
                    parsed = []
                    for replacement in split_party_cell(resolution.ruling):
                        replacement_parsed = parse_party_token(
                            replacement, set(parties_by_id))
                        if replacement_parsed is None:
                            raise ValueError(
                                f"resolution {key!r} names unknown party "
                                f"{replacement!r}")
                        parsed.extend(replacement_parsed)
                for party_id, qualifier in parsed:
                    roles.append(AssignmentRole(
                        assignment_id, role, party_id, qualifier))

        cited = [value.strip()
                 for value in row["Sources"].split(",") if value.strip()]
        for source_id in cited:
            if source_id not in source_ids:
                log(row_id, "Sources", source_id, "unknown source ID",
                    variant_label or "-")
                continue
            assignment_sources.append(AssignmentSource(
                assignment_id, source_id))

    variants_sorted = list(variants.values())
    for left, right in near_duplicate_variants(variants_sorted):
        log("", "Variant", f"{left} | {right}",
            "possible duplicate variants; not merged")

    stale = sorted(set(resolutions) - encountered)
    stale_text = public_text.stale + public_text.unused()
    if stale or stale_text:
        for key in stale:
            print(f"stale ruling: {key}", file=sys.stderr)
        for item in stale_text:
            print(f"stale public_text: {item}", file=sys.stderr)
        raise SystemExit(1)

    jurisdictions = [Jurisdiction(
        MEATH_URI, MEATH_NAME, ASSESSED_FROM, MEATH_SCOPE)]

    master = Master(
        stages=stages,
        groupings=groupings,
        activities=activities,
        activity_groupings=activity_groupings,
        activity_cofog=activity_cofog,
        activity_stages=activity_stages,
        parties=parties,
        variants=variants_sorted,
        evidence_levels=EVIDENCE_LEVELS,
        boundary_rules=boundary_rules,
        sources=sources,
        jurisdictions=jurisdictions,
        assignments=assignments,
        assignment_roles=roles,
        assignment_sources=assignment_sources,
        migration_resolutions=list(resolutions.values()),
    )

    validation_errors = validate(master)
    if validation_errors:
        for error in validation_errors:
            print(f"validation: {error}", file=sys.stderr)
        return 1

    # Cross-check the generated row set against Section 7 of the register.
    section_seven = {
        cells[0] for cells in table(section(register, 7))
    }
    generated = {row.row_id for row in generate_rows(master)}
    if section_seven != generated:
        print(
            "row set mismatch with register Section 7: "
            f"missing {sorted(section_seven - generated)!r}, "
            f"extra {sorted(generated - section_seven)!r}", file=sys.stderr)
        return 1
    assessed_rows = {row.row_id for row in generate_rows(master)
                     if row.coverage == "assessed"}
    if not args.no_count_check:
        if len(generated) != 613 or len(assessed_rows) != 184:
            print(
                f"row counts: {len(generated)} generated, "
                f"{len(assessed_rows)} assessed (expected 613 and 184)",
                file=sys.stderr)
            return 1
        if len(assignments) != 224:
            print(f"assessed lines: {len(assignments)} (expected 224)",
                  file=sys.stderr)
            return 1

    args.out.mkdir(parents=True, exist_ok=True)
    write_master(args.out, master)
    error_list = sorted(errors.values(),
                        key=lambda item: (
                            item["row_id"], item["column"], item["value"]))
    (args.out / "migration_errors.json").write_text(
        json.dumps(error_list, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    write_table(
        args.out / TABLE_FILES["migration_resolutions"],
        TABLE_FIELDS["migration_resolutions"],
        [[resolution.error_key, resolution.ruling, resolution.ruled_by,
          resolution.date]
         for resolution in master.migration_resolutions])
    print(
        f"Wrote {len(generated)} rows ({len(assessed_rows)} assessed), "
        f"{len(assignments)} assignments, {len(errors)} logged errors to "
        f"{args.out}")
    return 0


def write_table(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_master(out: Path, master: Master) -> None:
    write_table(out / TABLE_FILES["stages"], TABLE_FIELDS["stages"], [
        [stage.stage_id, stage.name, stage.definition, stage.sort_order,
         stage.public_name, stage.public_definition]
        for stage in master.stages])
    write_table(out / TABLE_FILES["groupings"], TABLE_FIELDS["groupings"], [
        [grouping.grouping_id, grouping.name, grouping.cofog_class,
         grouping.cofog_status, grouping.status]
        for grouping in master.groupings])
    write_table(out / TABLE_FILES["activities"], TABLE_FIELDS["activities"], [
        [activity.activity_id, activity.name, activity.definition,
         activity.status, activity.register_note, activity.public_name,
         activity.public_definition]
        for activity in master.activities])
    write_table(out / TABLE_FILES["activity_groupings"],
                TABLE_FIELDS["activity_groupings"], [
                    [link.activity_id, link.grouping_id,
                     "true" if link.is_primary else "false"]
                    for link in master.activity_groupings])
    write_table(out / TABLE_FILES["activity_cofog"],
                TABLE_FIELDS["activity_cofog"], [
                    [link.activity_id, link.cofog_code, link.status]
                    for link in master.activity_cofog])
    write_table(out / TABLE_FILES["activity_stages"],
                TABLE_FIELDS["activity_stages"], [
                    [link.activity_id, link.stage_id]
                    for link in master.activity_stages])
    write_table(out / TABLE_FILES["parties"], TABLE_FIELDS["parties"], [
        [party.party_id, party.name, party.plain_label, party.kind,
         party.public_body_uri, party.parent_party_id, party.description,
         party.public_name, party.public_description]
        for party in master.parties])
    write_table(out / TABLE_FILES["variants"], TABLE_FIELDS["variants"], [
        [variant.variant_id, variant.label, variant.description]
        for variant in master.variants])
    write_table(out / TABLE_FILES["evidence_levels"],
                TABLE_FIELDS["evidence_levels"], [
                    [level.evidence_id, level.label, level.plain_label,
                     level.definition]
                    for level in master.evidence_levels])
    write_table(out / TABLE_FILES["boundary_rules"],
                TABLE_FIELDS["boundary_rules"], [
                    [rule.rule_id, rule.rule, rule.source_decision]
                    for rule in master.boundary_rules])
    write_table(out / TABLE_FILES["sources"], TABLE_FIELDS["sources"], [
        [source.source_id, source.citation, source.urls, source.batch]
        for source in master.sources])
    write_table(out / TABLE_FILES["jurisdictions"],
                TABLE_FIELDS["jurisdictions"], [
                    [jurisdiction.public_body_uri, jurisdiction.name,
                     jurisdiction.assessed_from, jurisdiction.scope_note]
                    for jurisdiction in master.jurisdictions])
    write_table(out / TABLE_FILES["assignments"], TABLE_FIELDS["assignments"], [
        [assignment.assignment_id, assignment.activity_id, assignment.stage_id,
         assignment.variant_id, assignment.applies_to, assignment.evidence_id,
         assignment.note, assignment.public_note, assignment.scenario_refs]
        for assignment in master.assignments])
    write_table(out / TABLE_FILES["assignment_roles"],
                TABLE_FIELDS["assignment_roles"], [
                    [role.assignment_id, role.role, role.party_id, role.qualifier]
                    for role in master.assignment_roles])
    write_table(out / TABLE_FILES["assignment_sources"],
                TABLE_FIELDS["assignment_sources"], [
                    [link.assignment_id, link.source_id]
                    for link in master.assignment_sources])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--resolutions", type=Path, default=None,
        help="rulings CSV (default: <out>/migration_resolutions.csv)")
    parser.add_argument(
        "--public-text", type=Path, default=None,
        help="reviewed public copies CSV (default: <out>/public_text.csv)")
    parser.add_argument(
        "--no-count-check", action="store_true",
        help="skip the 613/184/224 acceptance counts (synthetic fixtures only)")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
