#!/usr/bin/env python3
"""Build the transport RACI vocabularies and dataset.

Usage:
    uv run python scripts/build_transport_raci.py
    uv run python scripts/build_transport_raci.py --check

One generator writes every published output from the committed master under
``reference/transport-raci/``:

    public/vocabularies/transport-stage.{json,csv,csv-metadata.json,ttl,md}
    public/vocabularies/transport-activity.{json,csv,csv-metadata.json,ttl,md}
    public/vocabularies/transport-raci-party.{json,csv,csv-metadata.json,ttl,md}
    public/vocabularies/raci-evidence-level.{json,csv,csv-metadata.json,ttl,md}
    public/ns/<vocabulary>/index.html
    public/latest/transport-raci/ and public/v0.1.0/transport-raci/
    public/catalog/dataset-transport-raci.ttl

Validation is fail closed: the generator validates the master, checks the leak
rules and builds everything in memory before writing. Writes go through
``stamp_if_changed``. ``--check`` compares the committed files with the built
bytes, names every differing file and exits non-zero.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.lib.dataset_publish import stamp_if_changed  # noqa: E402
from src.lib.transport_raci import generate_rows, load_master, validate  # noqa: E402
from src.lib.transport_raci.model import (  # noqa: E402
    INTERNAL_REF,
    LEAK_REF,
    MASTER_DIR,
    Master,
    Party,
)

VERSION = "0.1.0"
BASE = "https://data.publicinformation.ie"
NS = f"{BASE}/ns"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
DATASET_ID = f"{BASE}/dataset/transport-raci"
VOCAB_DIR = REPO / "public" / "vocabularies"
NS_DIR = REPO / "public" / "ns"
LATEST_DIR = REPO / "public" / "latest" / "transport-raci"
VERSION_DIR = REPO / "public" / "v0.1.0" / "transport-raci"
CATALOG = REPO / "public" / "catalog" / "dataset-transport-raci.ttl"
MASTER = MASTER_DIR
MEATH_URI = f"{BASE}/body/meath-county-council"
# The contact published in every DCAT record (see dataset-public-body-actions.ttl).
CONTACT_EMAIL = "dave@publicinformation.ie"
PUBLIC_BODIES_DATASET = f"{BASE}/dataset/public-bodies"
COFOG_DATASET = f"{BASE}/dataset/cofog-1999"
MEATH_SCOPE = (
    "The assignments have been analysed for Meath County Council only. They "
    "may differ for other councils. Meath is in the Greater Dublin Area.")

# Both patterns are defined once in the model; see INTERNAL_REF there.
LEAK = LEAK_REF
NOTE_LEAK = INTERNAL_REF
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

CSV_FIELDS = ["uri", "notation", "name", "description"]
CSV_COLUMNS = [
    {"name": "uri", "titles": "URI", "datatype": "uri",
     "description": "Persistent URI for this term"},
    {"name": "notation", "titles": "Notation", "datatype": "string",
     "description": "Short notation used in the dataset"},
    {"name": "name", "titles": "Name", "datatype": "string",
     "description": "Human-readable name"},
    {"name": "description", "titles": "Description", "datatype": "string",
     "description": "Meaning of the term"},
]

VOCABULARIES = {
    "transport-stage": "Transport lifecycle stages",
    "transport-activity": "Transport activities and L4 groupings",
    "transport-raci-party": "Transport RACI parties",
    "raci-evidence-level": "RACI evidence levels",
}

DATASET_TABLES = [
    "assignments", "assignment-roles", "assignment-sources", "variants",
    "sources", "boundary-rules", "rows", "raci-wide",
]


# ---------------------------------------------------------------------------
# Small serialisation helpers


def csv_bytes(header: list[str], rows: list[list[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def metadata_bytes(name: str, fields: list[str], primary_key: list[str],
                   uri_fields: set[str]) -> bytes:
    columns: list[dict[str, Any]] = []
    for field in fields:
        column: dict[str, Any] = {
            "name": field,
            "titles": field.replace("_", " ").title(),
            "datatype": "uri" if field in uri_fields else "string",
        }
        if field == "no_local_authority_role":
            column["datatype"] = "boolean"
            column["null"] = "unknown"
            column["dc:description"] = (
                "Derived. false: a council organ holds a role. true: the "
                "line has an Accountable party and no council organ holds "
                "any role. unknown (null): it is not established who is "
                "Accountable on the line; it does not mean the council has "
                "no role.")
        columns.append(column)
    payload: dict[str, Any] = {
        "@context": "http://www.w3.org/ns/csvw",
        "url": name,
        "tableSchema": {
            "columns": columns,
            "primaryKey": primary_key if len(primary_key) > 1
            else primary_key[0],
        },
    }
    if primary_key == ["uri"]:
        payload["tableSchema"]["aboutUrl"] = "{uri}"
    return json_bytes(payload)


def turtle_string(value: str) -> str:
    value = CONTROL_CHARS.sub(" ", value)
    return (value.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\r", " ").replace("\n", " "))


def terms_for(master: Master) -> dict[str, list[dict[str, Any]]]:
    """The four vocabularies as concept dicts."""
    groupings = master.groupings
    grouping_links: dict[str, list] = {}
    for link in master.activity_groupings:
        grouping_links.setdefault(link.activity_id, []).append(link)
    cofog_rows: dict[str, list] = {}
    for row in master.activity_cofog:
        cofog_rows.setdefault(row.activity_id, []).append(row)

    stage_terms = [
        {
            "uri": f"{NS}/transport-stage#{stage.stage_id}",
            "notation": stage.stage_id,
            "name": stage.public_name,
            "description": stage.public_definition,
            "sort_order": stage.sort_order,
        }
        for stage in master.stages
    ]

    grouping_terms = [
        {
            "uri": f"{NS}/transport-activity#{grouping.grouping_id}",
            "notation": grouping.grouping_id,
            "name": grouping.name,
            "description": (
                f"{grouping.name}. COFOG class {grouping.cofog_class} "
                f"({grouping.cofog_status})."
                if grouping.cofog_class else
                f"{grouping.name}. A cross-cutting grouping with no single "
                "COFOG class."),
            "kind": "grouping",
            "status": grouping.status,
            "cofog_class": grouping.cofog_class,
            "cofog_status": grouping.cofog_status,
        }
        for grouping in groupings
    ]

    activity_terms = []
    for activity in master.activities:
        links = grouping_links.get(activity.activity_id, [])
        primary = next((link.grouping_id for link in links if link.is_primary), "")
        others = [link.grouping_id for link in links
                  if not link.is_primary and link.grouping_id != primary]
        described = activity.public_definition
        if activity.status != "active":
            described = f"{activity.status.capitalize()} activity. {described}"
        activity_terms.append({
            "uri": f"{NS}/transport-activity#{activity.activity_id}",
            "notation": activity.activity_id,
            "name": activity.public_name,
            "description": described,
            "kind": "activity",
            "status": activity.status,
            "primary_grouping": primary,
            "other_groupings": others,
            "cofog": [
                {"code": row.cofog_code, "status": row.status}
                for row in cofog_rows.get(activity.activity_id, [])
            ],
            "stages": [
                link.stage_id for link in master.activity_stages
                if link.activity_id == activity.activity_id
            ],
        })

    party_terms = [
        {
            "uri": f"{NS}/transport-raci-party#{party.party_id}",
            "notation": party.party_id,
            "name": party.public_name,
            "description": party.public_description or party.public_name,
            "kind": party.kind,
            "plain_label": party.plain_label,
            "public_body_uri": party.public_body_uri,
            "parent_party_id": party.parent_party_id,
        }
        for party in master.parties
    ]

    evidence_terms = [
        {
            "uri": f"{NS}/raci-evidence-level#{level.evidence_id}",
            "notation": level.evidence_id,
            "name": level.label,
            "description": level.definition,
            "plain_label": level.plain_label,
            "coverage_state": False,
        }
        for level in master.evidence_levels
    ]
    evidence_terms.append({
        "uri": f"{NS}/raci-evidence-level#not-assessed",
        "notation": "not-assessed",
        "name": "Not assessed",
        "description": (
            "A generated coverage state: the activity x stage row has no "
            "assessment. It is never stored on an assignment."),
        "plain_label": "not yet assessed",
        "coverage_state": True,
    })

    return {
        "transport-stage": stage_terms,
        "transport-activity": grouping_terms + activity_terms,
        "transport-raci-party": party_terms,
        "raci-evidence-level": evidence_terms,
    }


# ---------------------------------------------------------------------------
# Vocabularies


def build_vocabularies(master: Master) -> dict[Path, bytes]:
    outputs: dict[Path, bytes] = {}
    terms = terms_for(master)
    for name, concepts in terms.items():
        title = VOCABULARIES[name]
        namespace = f"{NS}/{name}"
        payload = {
            "scheme": {
                "title": title,
                "version": VERSION,
                "namespace": f"{namespace}#",
                "license": LICENSE,
                "source": "reference/transport-raci",
            },
            "concepts": concepts,
        }
        outputs[VOCAB_DIR / f"{name}.json"] = json_bytes(payload)
        outputs[VOCAB_DIR / f"{name}.csv"] = csv_bytes(
            CSV_FIELDS,
            [[concept["uri"], concept["notation"], concept["name"],
              concept["description"]] for concept in concepts],
        )
        outputs[VOCAB_DIR / f"{name}.csv-metadata.json"] = metadata_bytes(
            f"{name}.csv", CSV_FIELDS, ["uri"], {"uri"})
        outputs[VOCAB_DIR / f"{name}.ttl"] = build_turtle(
            name, title, concepts).encode("utf-8")
        outputs[VOCAB_DIR / f"{name}.md"] = vocabulary_readme(
            name, title, namespace, concepts).encode("utf-8")
        outputs[NS_DIR / name / "index.html"] = resolver_page(
            name, title, namespace, concepts).encode("utf-8")
    return outputs


def build_turtle(name: str, title: str, concepts: list[dict[str, Any]]) -> str:
    scheme = f"{NS}/{name}"
    top = [concept for concept in concepts
           if concept.get("kind") != "activity"]
    lines = [
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        f"<{scheme}>",
        "    a skos:ConceptScheme ;",
        f'    dct:title "{turtle_string(title)}"@en ;',
        f"    dct:license <{LICENSE}> ;",
        f'    owl:versionInfo "{VERSION}" ;',
        "    skos:hasTopConcept "
        + ", ".join(f"<{concept['uri']}>" for concept in top) + " .",
        "",
    ]
    for concept in concepts:
        predicates = [
            f'    skos:notation "{turtle_string(concept["notation"])}"',
            f'    skos:prefLabel "{turtle_string(concept["name"])}"@en',
            f'    skos:definition "{turtle_string(concept["description"])}"@en',
        ]
        if name == "transport-activity":
            kind = concept["kind"]
            if kind == "grouping":
                code = concept.get("cofog_class")
                if code:
                    predicate = ("skos:broader" if concept["cofog_status"]
                                 == "confirmed" else "skos:related")
                    predicates.append(
                        f'    {predicate} <{NS}/cofog#{code}>')
                predicates.append(
                    f'    skos:note "Status: {concept["status"]}"@en')
            else:
                primary = concept.get("primary_grouping")
                if primary:
                    predicates.append(
                        f'    skos:broader <{NS}/transport-activity#{primary}>')
                for other in concept.get("other_groupings", []):
                    predicates.append(
                        f'    skos:related <{NS}/transport-activity#{other}>')
                # Activity-level COFOG placements (where they differ from the
                # grouping's, or are uncertain). The activity stays narrower
                # than its grouping, so both are related, not broader.
                for item in concept.get("cofog", []):
                    predicates.append(
                        f'    skos:related <{NS}/cofog#{item["code"]}>')
                    predicates.append(
                        f'    skos:scopeNote "COFOG {item["code"]}: '
                        f'{item["status"]}"@en')
                predicates.append(
                    f'    skos:note "Status: {concept["status"]}"@en')
                stages = concept.get("stages", [])
                predicates.append(
                    '    skos:note "Stages: '
                    + (", ".join(stages) if stages else "none") + '"@en')
        elif name == "transport-raci-party":
            if concept.get("public_body_uri"):
                predicates.append(
                    f'    skos:exactMatch <{concept["public_body_uri"]}>')
            predicates.append(
                f'    skos:altLabel "{turtle_string(concept["plain_label"])}"@en')
            predicates.append(
                f'    skos:scopeNote "Kind: {concept["kind"]}"@en')
        elif name == "raci-evidence-level":
            predicates.append(
                f'    skos:altLabel "{turtle_string(concept["plain_label"])}"@en')
            if concept["coverage_state"]:
                predicates.append(
                    '    skos:note "Generated coverage state; never stored '
                    'on an assignment."@en')
        predicates.append(f"    skos:inScheme <{scheme}>")
        lines.append(f"<{concept['uri']}>")
        lines.append("    a skos:Concept ;")
        lines.append(" ;\n".join(predicates) + " .")
        lines.append("")
    return "\n".join(lines)


def vocabulary_readme(name: str, title: str, namespace: str,
                      concepts: list[dict[str, Any]]) -> str:
    return "\n".join([
        f"# {title}",
        "",
        f"This vocabulary holds {len(concepts)} terms. It is generated from the "
        "transport RACI master and is not edited by hand.",
        "",
        f"- Namespace: `{namespace}#`",
        f"- JSON: [{name}.json]({name}.json)",
        f"- CSV: [{name}.csv]({name}.csv) "
        f"(CSVW metadata: [{name}.csv-metadata.json]({name}.csv-metadata.json))",
        f"- SKOS Turtle: [{name}.ttl]({name}.ttl)",
        f"- Resolver page: [/ns/{name}/]({BASE}/ns/{name})",
        "",
        "A term URI has the form "
        f"`{namespace}#<notation>`, for example "
        f"`{concepts[0]['uri']}`.",
        "",
        "| Notation | Name |",
        "|---|---|",
        *[f"| `{concept['notation']}` | {concept['name']} |"
          for concept in concepts],
        "",
    ])


def resolver_page(name: str, title: str, namespace: str,
                  concepts: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f'  <tr><td><a href="{concept["uri"]}">'
        f'{concept["notation"]}</a></td><td>{html_escape(concept["name"])}</td>'
        f"</tr>"
        for concept in concepts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html_escape(title)} — PublicInformation.ie</title>
<link rel="alternate" type="application/json" title="{html_escape(title)} (JSON)" href="../../vocabularies/{name}.json">
<link rel="alternate" type="text/csv" title="{html_escape(title)} (CSV)" href="../../vocabularies/{name}.csv">
<link rel="describedby" type="application/ld+json" title="{html_escape(title)} (CSVW metadata)" href="../../vocabularies/{name}.csv-metadata.json">
<link rel="alternate" type="text/turtle" title="{html_escape(title)} (Turtle)" href="../../vocabularies/{name}.ttl">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 64rem; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ font-size: 1.6rem; }}
  p.lead {{ font-size: 1.05rem; color: #333; }}
  a {{ color: #0645ad; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  table {{ border-collapse: collapse; margin: 1rem 0; width: 100%; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; font-size: 0.95em; vertical-align: top; }}
  th {{ color: #555; font-weight: 600; }}
  code {{ background: #f2f2f2; padding: 0.1em 0.35em; border-radius: 3px; }}
</style>
</head>
<body>
<h1>{html_escape(title)}</h1>
<p class="lead">{len(concepts)} terms published by PublicInformation.ie as part
of the <a href="../../latest/transport-raci/README.md">transport RACI dataset</a>.
This page is a resolver: every term has the URI
<code>{namespace}#&lt;notation&gt;</code>.</p>

<h2>Downloads</h2>
<table>
  <tr><th>Format</th><th>File</th><th>Use it for</th></tr>
  <tr><td>JSON</td><td><a href="../../vocabularies/{name}.json">{name}.json</a></td>
      <td>The scheme and every term with its structured fields.</td></tr>
  <tr><td>CSV</td><td><a href="../../vocabularies/{name}.csv">{name}.csv</a></td>
      <td>Spreadsheets and joins, one row per term; CSVW metadata in
      <a href="../../vocabularies/{name}.csv-metadata.json">{name}.csv-metadata.json</a>.</td></tr>
  <tr><td>Turtle</td><td><a href="../../vocabularies/{name}.ttl">{name}.ttl</a></td>
      <td>SKOS for linked-data tools.</td></tr>
</table>

<h2>Terms</h2>
<table>
  <tr><th>Notation</th><th>Name</th></tr>
{rows}
</table>
</body>
</html>
"""


def html_escape(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Dataset tables


COUNCIL_ORGANS = frozenset({"LA-M", "LA-CE"})
COUNCIL_PLACEHOLDER = "the council"
FLAG_NULL = "unknown"


def derived_flag(master: Master, assignment_id: str) -> bool | None:
    """The derived ``no_local_authority_role`` value of one assignment.

    ``False``: a council organ (LA-M or LA-CE) holds a role. ``True``: the line
    has an Accountable party and no council organ holds any role. ``None``
    (unknown): the line has no Accountable party, so it is not established
    who is Accountable, and the data cannot say that the council has no role.
    """
    lines = [role for role in master.assignment_roles
             if role.assignment_id == assignment_id]
    if any(line.party_id in COUNCIL_ORGANS for line in lines):
        return False
    if any(line.role == "A" for line in lines):
        return True
    return None


def flag_cell(value: bool | None) -> str:
    """The CSV cell for a derived flag; CSVW maps ``unknown`` to null."""
    if value is None:
        return FLAG_NULL
    return "true" if value else "false"


def party_label(party: Party | None, party_id: str, council: str) -> str:
    """A party's plain label, naming the assignment's council for an organ."""
    if party is None:
        return party_id
    if party.kind != "organ":
        return party.plain_label
    if COUNCIL_PLACEHOLDER not in party.plain_label:
        raise ValueError(
            f"organ party {party.party_id!r} plain label does not name "
            f"{COUNCIL_PLACEHOLDER!r}")
    return party.plain_label.replace(COUNCIL_PLACEHOLDER, council)


def dataset_tables(master: Master) -> dict[str, tuple[list[str], list[list[object]]]]:
    groupings = {grouping.grouping_id: grouping
                 for grouping in master.groupings}
    variants = {variant.variant_id: variant for variant in master.variants}
    evidence = master.evidence_by_id()
    parties = master.parties_by_id()
    jurisdictions = {jurisdiction.public_body_uri: jurisdiction
                     for jurisdiction in master.jurisdictions}
    sources = master.sources_by_id()

    roles_by_assignment: dict[str, list] = {}
    for role in master.assignment_roles:
        roles_by_assignment.setdefault(role.assignment_id, []).append(role)
    source_links: dict[str, list[str]] = {}
    for link in master.assignment_sources:
        source_links.setdefault(link.assignment_id, []).append(link.source_id)

    tables: dict[str, tuple[list[str], list[list[object]]]] = {}

    tables["assignments"] = (
        ["assignment_id", "activity", "stage", "variant", "applies_to",
         "evidence", "public_note"],
        [[assignment.assignment_id,
          f"{NS}/transport-activity#{assignment.activity_id}",
          f"{NS}/transport-stage#{assignment.stage_id}",
          assignment.variant_id,
          assignment.applies_to,
          f"{NS}/raci-evidence-level#{assignment.evidence_id}",
          assignment.public_note]
         for assignment in master.assignments],
    )

    role_rows = []
    for assignment in master.assignments:
        for line in roles_by_assignment.get(assignment.assignment_id, []):
            role_rows.append([
                line.assignment_id, line.role,
                f"{NS}/transport-raci-party#{line.party_id}", line.qualifier])
    tables["assignment-roles"] = (
        ["assignment_id", "role", "party", "qualifier"], role_rows)

    tables["assignment-sources"] = (
        ["assignment_id", "source_id"],
        [[link.assignment_id, link.source_id]
         for link in master.assignment_sources],
    )

    tables["variants"] = (
        ["variant_id", "label", "description"],
        [[variant.variant_id, variant.label, variant.description]
         for variant in master.variants],
    )

    tables["sources"] = (
        ["source_id", "citation", "urls"],
        [[source.source_id, source.citation, source.urls]
         for source in master.sources],
    )

    tables["boundary-rules"] = (
        ["rule_id", "rule"],
        [[rule.rule_id, rule.rule] for rule in master.boundary_rules],
    )

    rows = generate_rows(master)
    tables["rows"] = (
        ["row_id", "activity", "stage", "coverage", "assessed_lines"],
        [[row.row_id, f"{NS}/transport-activity#{row.activity_id}",
          f"{NS}/transport-stage#{row.stage_id}", row.coverage,
          row.assessed_lines]
         for row in rows],
    )

    wide_rows = []
    for assignment in master.assignments:
        lines = roles_by_assignment.get(assignment.assignment_id, [])
        grouped = {
            role: [line for line in lines if line.role == role]
            for role in ("R", "A", "C", "I")
        }
        readable = {}
        for role, role_lines in grouped.items():
            labels = []
            for line in role_lines:
                label = party_label(parties.get(line.party_id), line.party_id,
                                    jurisdictions[assignment.applies_to].name)
                if line.qualifier:
                    label = f"{label} ({line.qualifier})"
                labels.append(label)
            readable[role] = "; ".join(labels)
        activity = next(
            item for item in master.activities
            if item.activity_id == assignment.activity_id)
        stage = next(
            item for item in master.stages
            if item.stage_id == assignment.stage_id)
        variant = variants.get(assignment.variant_id)
        level = evidence[assignment.evidence_id]
        jurisdiction = jurisdictions[assignment.applies_to]
        cited = source_links.get(assignment.assignment_id, [])
        wide_rows.append([
            assignment.assignment_id,
            f"{assignment.activity_id}.{assignment.stage_id}",
            assignment.activity_id, activity.public_name,
            assignment.stage_id, stage.public_name,
            variant.label if variant else "",
            level.plain_label,
            jurisdiction.name,
            readable["R"], readable["A"], readable["C"], readable["I"],
            "; ".join(cited),
            assignment.public_note,
            flag_cell(derived_flag(master, assignment.assignment_id)),
        ])
    tables["raci-wide"] = (
        ["assignment_id", "row_id", "activity_id", "activity", "stage_id",
         "stage", "variant", "evidence", "jurisdiction", "R", "A", "C", "I",
         "sources", "public_note", "no_local_authority_role"],
        wide_rows,
    )
    return tables


def build_dataset_tables(master: Master) -> dict[str, bytes]:
    outputs: dict[str, bytes] = {}
    for name, (fields, rows) in dataset_tables(master).items():
        outputs[f"{name}.csv"] = csv_bytes(fields, rows)
        uri_fields = {
            field for field in fields
            if field in {"activity", "stage", "applies_to", "evidence", "party"}
        }
        key = {
            "assignment-roles": ["assignment_id", "role", "party"],
            "assignment-sources": ["assignment_id", "source_id"],
        }.get(name, [fields[0]])
        outputs[f"{name}.csv-metadata.json"] = metadata_bytes(
            f"{name}.csv", fields, key, uri_fields)
    outputs["transport-raci.json"] = json_bytes(nested_json(master))
    return outputs


def nested_json(master: Master) -> dict[str, Any]:
    roles_by_assignment: dict[str, list] = {}
    for role in master.assignment_roles:
        roles_by_assignment.setdefault(role.assignment_id, []).append(role)
    sources_by_assignment: dict[str, list[str]] = {}
    for link in master.assignment_sources:
        sources_by_assignment.setdefault(link.assignment_id, []).append(
            link.source_id)
    parties = master.parties_by_id()
    evidence = master.evidence_by_id()
    variants = {variant.variant_id: variant for variant in master.variants}
    stages = {stage.stage_id: stage for stage in master.stages}
    jurisdictions = {jurisdiction.public_body_uri: jurisdiction
                     for jurisdiction in master.jurisdictions}
    rows = generate_rows(master)
    row_by_key = {(row.activity_id, row.stage_id): row for row in rows}
    assignments_by_key: dict[tuple[str, str], list] = {}
    for assignment in master.assignments:
        assignments_by_key.setdefault(
            (assignment.activity_id, assignment.stage_id), []).append(assignment)
    cofog_rows: dict[str, list] = {}
    for row in master.activity_cofog:
        cofog_rows.setdefault(row.activity_id, []).append(row)
    grouping_by_id = {grouping.grouping_id: grouping
                      for grouping in master.groupings}
    links_by_activity: dict[str, list] = {}
    for link in master.activity_groupings:
        links_by_activity.setdefault(link.activity_id, []).append(link)

    activities = []
    for activity in master.activities:
        activity_stages = []
        for link in master.activity_stages:
            if link.activity_id != activity.activity_id:
                continue
            row = row_by_key[(activity.activity_id, link.stage_id)]
            published = []
            for assignment in assignments_by_key.get(
                    (activity.activity_id, link.stage_id), []):
                level = evidence[assignment.evidence_id]
                variant = variants.get(assignment.variant_id)
                published.append({
                    "assignment_id": assignment.assignment_id,
                    "variant_id": assignment.variant_id,
                    "variant_label": variant.label if variant else "",
                    "evidence_id": assignment.evidence_id,
                    "evidence_label": level.label,
                    "evidence_plain_label": level.plain_label,
                    "sources": sources_by_assignment.get(
                        assignment.assignment_id, []),
                    "public_note": assignment.public_note,
                    "no_local_authority_role": derived_flag(
                        master, assignment.assignment_id),
                    "roles": [
                        {
                            "role": line.role,
                            "party_id": line.party_id,
                            "party_uri": (
                                f"{NS}/transport-raci-party#{line.party_id}"),
                            "plain_label": party_label(
                                parties.get(line.party_id), line.party_id,
                                jurisdictions[assignment.applies_to].name),
                            "qualifier": line.qualifier,
                        }
                        for line in roles_by_assignment.get(
                            assignment.assignment_id, [])
                    ],
                })
            activity_stages.append({
                "stage_id": link.stage_id,
                "stage_name": stages[link.stage_id].public_name,
                "row_id": row.row_id,
                "coverage": row.coverage,
                "assessed_lines": row.assessed_lines,
                "assignments": published,
            })
        links = links_by_activity.get(activity.activity_id, [])
        cofog_status: dict[str, str] = {}
        for link in links:
            grouping = grouping_by_id[link.grouping_id]
            if grouping.cofog_class:
                cofog_status[grouping.cofog_class] = grouping.cofog_status
        for row in cofog_rows.get(activity.activity_id, []):
            cofog_status[row.cofog_code] = row.status
        cofog = [
            {"code": code, "status": status,
             "uri": f"{NS}/cofog#{code}"}
            for code, status in cofog_status.items()
        ]
        activities.append({
            "activity_id": activity.activity_id,
            "name": activity.public_name,
            "definition": activity.public_definition,
            "status": activity.status,
            "groupings": [
                {"grouping_id": link.grouping_id,
                 "name": grouping_by_id[link.grouping_id].name,
                 "primary": link.is_primary}
                for link in links
            ],
            "cofog": cofog,
            "coverage": {
                "rows": len(activity_stages),
                "assessed": sum(1 for stage in activity_stages
                                if stage["coverage"] == "assessed"),
                "not_assessed": sum(1 for stage in activity_stages
                                    if stage["coverage"] != "assessed"),
                "assessed_lines": sum(stage["assessed_lines"]
                                      for stage in activity_stages),
            },
            "stages": activity_stages,
        })
    return {
        "dataset": "transport-raci",
        "version": VERSION,
        "scope": MEATH_SCOPE,
        "activities": activities,
    }


# ---------------------------------------------------------------------------
# Documentation


def load_unresolved() -> list[dict[str, str]]:
    path = MASTER / "migration_errors.json"
    if not path.exists():
        return []
    errors = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for error in errors:
        if error["column"] not in {"R", "A", "C", "I"}:
            continue
        row_id, variant, column, token = error["error_key"].split("|", 3)
        result.append({
            "row_id": row_id, "variant": variant, "role": column,
            "token": token,
        })
    return result


def build_readme(master: Master, tables: dict[str, bytes]) -> str:
    rows = generate_rows(master)
    assessed_rows = sum(1 for row in rows if row.coverage == "assessed")
    unresolved = load_unresolved()
    unresolved_lines = []
    for item in unresolved:
        variant = "" if item["variant"] == "-" else f" ({item['variant']})"
        unresolved_lines.append(
            f"- `{item['row_id']}`{variant}, role {item['role']}: role not yet "
            f"published: awaiting review (recorded value `{item['token']}`).")
    evidence_rows = "\n".join(
        f"| `{level.evidence_id}` | {level.plain_label} |"
        for level in master.evidence_levels)
    return f"""# Transport RACI

Who is Responsible, Accountable, Consulted and Informed for local transport
activities and lifecycle stages, as compiled by PublicInformation.ie.

**This is analysis, not official data.** It is not a statement of any body's
legal duties and it is not legal advice. Every line carries its evidence so you
can check or challenge it.

## Scope

{MEATH_SCOPE}

The activity and stage vocabulary is generic to Irish local authorities; only
the assignments are analysed for Meath.

## How to read a line

Each row is one activity × stage. A line names the parties for each role:

- **R** does the work.
- **A** owns the decision; there is at most one.
- **C** must be asked.
- **I** is told afterwards.

A row is `assessed` when at least one line exists for it, and `not assessed`
otherwise. "Not assessed" is a gap, not a finding that nobody is responsible.

Each assessed line carries a derived `no_local_authority_role` value. It is a
boolean with a null: in `transport-raci.json` it is `true`, `false` or `null`;
in `raci-wide.csv` the cell reads `true`, `false` or `unknown`, and the CSVW
metadata declares the column as boolean with `unknown` as its null value.

- `false`: the council's elected members or its Chief Executive and executive
  hold a role on the line.
- `true`: the line has an Accountable party and no council organ holds any
  role. That is a finding.
- `unknown` (`null` in JSON): the line has no Accountable party (for example
  an unverified line). Unknown means it is not established who is
  Accountable — not that the council has no role.

"The council" in a party label means the council named in the line's
`jurisdiction` column; for this version that is Meath County Council.

## Evidence levels

| Evidence | Plain meaning |
|---|---|
{evidence_rows}

## Coverage

- {len(rows)} activity × stage rows.
- {assessed_rows} rows assessed; {len(rows) - assessed_rows} not assessed.
- {len(master.assignments)} assessed lines.
- {len(unresolved)} roles awaiting review.

## Files

- [assignments.csv](assignments.csv) — one line per assessed assignment.
- [assignment-roles.csv](assignment-roles.csv) — one line per role, with the
  party URI.
- [assignment-sources.csv](assignment-sources.csv) — the sources for each line.
- [rows.csv](rows.csv) — every activity × stage row with its coverage state.
- [raci-wide.csv](raci-wide.csv) — a generated reading view, one line per
  assignment with readable party names and evidence. It is never edited.
- [transport-raci.json](transport-raci.json) — the same data nested by
  activity → stage → assignments, for programs and LLMs.
- [sources.csv](sources.csv), [variants.csv](variants.csv) and
  [boundary-rules.csv](boundary-rules.csv) — the cited sources, the variant
  labels and the boundary rules.
- [METHODOLOGY.md](METHODOLOGY.md) — how the model was built and what it means.

## Roles awaiting review

These roles are recorded in the working model but are not published yet. They
are listed here so the gap is visible.

{chr(10).join(unresolved_lines)}

## Corrections

If a line is wrong, email {CONTACT_EMAIL} with the assignment ID (for example
`RT-09.S12`), the role and, where possible, the source that contradicts it.
This is the contact point in the dataset's catalogue record. Corrections are
reviewed and appear in a later version.

Licence: [CC BY 4.0]({LICENSE}).
"""


def build_llms(master: Master) -> str:
    return f"""# Transport RACI

> Who is Responsible, Accountable, Consulted and Informed for local transport
> activities and lifecycle stages. Compiled by PublicInformation.ie as
> analysis, not official data and not legal advice.

{MEATH_SCOPE}

## How to answer a question

1. Read the activity from the JSON (nested activity → stage → assignment) or
   filter `raci-wide.csv` by activity and stage.
2. Check the row's `coverage`. `not assessed` means the model has not assessed
   it; say so and do not invent a role.
3. Read the roles from `A`, `R`, `C` and `I`. A is the Accountable party.
4. State the evidence in plain words from the `evidence` column.
5. Read `no_local_authority_role` (`true` / `false` / `null` in the JSON;
   `true` / `false` / `unknown` in the CSV): `true` means no council organ
   holds a role on the assessed line; `false` means one does; unknown means it
   is not established who is Accountable — not that the council has no role.
   Do not say the council has no role.
6. Cite the row ID (for example `RT-09.S12`) and the dataset version.

## Files

- [README]({BASE}/latest/transport-raci/README.md)
- [Methodology]({BASE}/latest/transport-raci/METHODOLOGY.md)
- [Nested JSON]({BASE}/latest/transport-raci/transport-raci.json)
- [Wide reading view]({BASE}/latest/transport-raci/raci-wide.csv)
- [Coverage rows]({BASE}/latest/transport-raci/rows.csv)
- [Assignments]({BASE}/latest/transport-raci/assignments.csv)
- [Version 0.1.0]({BASE}/v0.1.0/transport-raci/README.md)
"""


# ---------------------------------------------------------------------------
# Catalogue


def build_catalogue(master: Master, modified: str) -> bytes:
    urls: list[str] = []
    for source in master.sources:
        for url in source.urls.split(";"):
            url = url.strip()
            if url and url not in urls:
                urls.append(url)
    distributions = []
    descriptions = {
        "assignments": "One line per assessed activity × stage assignment.",
        "assignment-roles": "One line per role (R, A, C or I) and party.",
        "assignment-sources": "The source IDs cited by each assignment.",
        "variants": "The variant labels used on assignments.",
        "sources": "Citations and URLs for every source cited.",
        "boundary-rules": "The boundary rules used to allocate decisions to stages.",
        "rows": "Every activity × stage row with its coverage state.",
        "raci-wide": "A generated reading view, one line per assignment.",
    }
    for name in DATASET_TABLES:
        distributions.append(f"""    dcat:distribution [
        a dcat:Distribution ;
        dct:title "{name}.csv"@en ;
        dct:description "{turtle_string(descriptions[name])}"@en ;
        dct:format <http://publications.europa.eu/resource/authority/file-type/CSV> ;
        dcat:accessURL <{BASE}/latest/transport-raci/{name}.csv> ;
        dcat:downloadURL <{BASE}/v{VERSION}/transport-raci/{name}.csv> ;
        dct:conformsTo <http://www.w3.org/ns/csvw> ;
        dct:conformsTo <{BASE}/v{VERSION}/transport-raci/{name}.csv-metadata.json> ;
        dct:license <{LICENSE}> ;
        dcat:mediaType "text/csv" ;
    ]""")
    distributions.append(f"""    dcat:distribution [
        a dcat:Distribution ;
        dct:title "transport-raci.json"@en ;
        dct:description "The same data nested by activity, stage and assignment, for programs and LLMs."@en ;
        dct:format <http://publications.europa.eu/resource/authority/file-type/JSON> ;
        dcat:accessURL <{BASE}/latest/transport-raci/transport-raci.json> ;
        dcat:downloadURL <{BASE}/v{VERSION}/transport-raci/transport-raci.json> ;
        dct:license <{LICENSE}> ;
        dcat:mediaType "application/json" ;
    ]""")
    derived = "\n".join(
        f"    prov:wasDerivedFrom <{url}> ;" for url in urls)
    distribution_text = " ;\n".join(distributions)
    return f"""@prefix adms: <http://www.w3.org/ns/adms#> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix vcard: <http://www.w3.org/2006/vcard/ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<{DATASET_ID}>
    a dcat:Dataset ;
    dct:title "Transport RACI (Meath County Council)"@en ;
    dct:description "An analysis compiled by PublicInformation.ie of who is Responsible, Accountable, Consulted and Informed for local transport activities and lifecycle stages. This is not official data and not republished source data. Assignments have been analysed for Meath County Council only; they may differ for other councils. Meath is in the Greater Dublin Area. Not legal advice."@en ;
    dct:publisher <https://www.publicinformation.ie/> ;
    dct:creator <https://www.publicinformation.ie/> ;
    dct:issued "2026-11-28"^^xsd:date ;
    dct:modified "{modified}"^^xsd:date ;
    owl:versionInfo "{VERSION}" ;
    dct:language <http://publications.europa.eu/resource/authority/language/ENG> ;
    dct:license <{LICENSE}> ;
    dct:spatial <{MEATH_URI}> ;
    adms:status <http://purl.org/adms/status/UnderDevelopment> ;
    dct:provenance [
        a dct:ProvenanceStatement ;
        rdfs:label "Compiled from cited legislation, guidance and observed practice; see the methodology."@en ;
        dct:source <{BASE}/latest/transport-raci/METHODOLOGY.md> ;
    ] ;
    dct:relation <{PUBLIC_BODIES_DATASET}> ;
    dct:relation <{COFOG_DATASET}> ;
    dcat:keyword "transport", "RACI", "local government", "Meath", "COFOG", "open data"@en ;
    dcat:theme <http://data.europa.eu/m8g/TRANSPORT> ;
    dcat:contactPoint [
        a vcard:Organization ;
        vcard:fn "PublicInformation.ie" ;
        vcard:hasEmail <mailto:{CONTACT_EMAIL}> ;
    ] ;
{derived}
{distribution_text} .

<{DATASET_ID}>
    prov:wasGeneratedBy [
        a prov:Activity ;
        prov:wasAssociatedWith [
            a prov:Agent ;
            prov:actedOnBehalfOf <https://www.publicinformation.ie/> ;
            foaf:name "PublicInformation.ie build_transport_raci.py" ;
            foaf:homepage <https://github.com/publicinformation-ie/publicinformation-data> ;
        ] ;
    ] .
"""


# ---------------------------------------------------------------------------
# Build, check and write


def build_all(master: Master) -> dict[Path, bytes]:
    outputs = build_vocabularies(master)
    tables = build_dataset_tables(master)
    readme = build_readme(master, tables).encode("utf-8")
    llms = build_llms(master).encode("utf-8")
    methodology = (LATEST_DIR / "METHODOLOGY.md").read_bytes()
    for base in (LATEST_DIR, VERSION_DIR):
        for name, data in tables.items():
            outputs[base / name] = data
        outputs[base / "README.md"] = readme
        outputs[base / "llms.txt"] = llms
        outputs[base / "METHODOLOGY.md"] = methodology
    modified = date.today().isoformat()
    if CATALOG.exists():
        found = re.search(r'dct:modified "(\d{4}-\d{2}-\d{2})"',
                          CATALOG.read_text(encoding="utf-8"))
        if found:
            modified = found.group(1)
    outputs[CATALOG] = build_catalogue(master, modified).encode("utf-8")
    return outputs


def check(master: Master, outputs: dict[Path, bytes]) -> list[Path]:
    leaks: list[str] = []
    for path, data in outputs.items():
        if path.suffix not in {".csv", ".json", ".ttl", ".md", ".html",
                               ".txt"}:
            continue
        text = data.decode("utf-8")
        for match in LEAK.finditer(text):
            leaks.append(f"{path.relative_to(REPO)}: {match.group(0)!r}")
    for assignment in master.assignments:
        if NOTE_LEAK.search(assignment.note) and not assignment.public_note:
            leaks.append(
                f"assignments[{assignment.assignment_id}]: note cites an "
                "internal reference and public_note is empty")
        if assignment.public_note and LEAK.search(assignment.public_note):
            leaks.append(
                f"assignments[{assignment.assignment_id}]: public_note "
                "contains an internal reference")
    if leaks:
        for leak in leaks:
            print(f"leak: {leak}", file=sys.stderr)
        raise SystemExit(1)
    return [path for path, data in outputs.items()
            if not path.exists() or path.read_bytes() != data]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare the committed files with what this "
                             "script would write, without writing")
    args = parser.parse_args(argv)

    master = load_master()
    errors = validate(master)
    if errors:
        for error in errors:
            print(f"validation: {error}", file=sys.stderr)
        return 1
    outputs = build_all(master)

    if args.check:
        differing = check(master, outputs)
        if differing:
            for path in differing:
                print(f"differing: {path.relative_to(REPO)}", file=sys.stderr)
            return 1
        print("transport-raci: all outputs match")
        return 0

    check(master, outputs)
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    changed = stamp_if_changed(CATALOG, list(outputs), outputs)
    if changed:
        print(f"Wrote transport RACI {VERSION} to public/")
    else:
        print("transport-raci: unchanged, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
