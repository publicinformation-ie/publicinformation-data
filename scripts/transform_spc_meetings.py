#!/usr/bin/env python3
"""Publish the SPC meetings dataset from the pipeline's export step.

Reads pipelines/spc_pipeline/steps/export_spc_meetings/output.json and the
authoritative Public Bodies data, then writes JSON-LD, CSV and CSVW metadata
for meetings, people, attendance, items and decisions, the verbatim Markdown
minutes and a README to public/v1.1.0/spc-meetings/, mirrors that directory to
public/latest/spc-meetings/, and stamps dct:modified only when the payload
changes.

Usage: uv run python scripts/transform_spc_meetings.py
"""
import csv
import io
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.lib.body_refs import BASE_URI, build_body_slug_lookup, body_uri
from src.lib.dataset_publish import render_jsonld, stamp_if_changed, stamp_modified

EXPORT_PATH = "pipelines/spc_pipeline/steps/export_spc_meetings/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v1.1.0/spc-meetings"
LATEST_DIR = "public/latest/spc-meetings"
TTL_PATH = "public/catalog/dataset-spc-meetings.ttl"

KINDS = ("meetings", "people", "attendance", "items", "decisions")

CSV_FIELDS = {
    "meetings": ["id", "meeting_id", "committee_id", "committee_name", "public_body",
                 "public_body_id", "meeting_date", "venue", "start_time", "end_time",
                 "source_url", "source_sha256", "minutes_path", "attendance_published"],
    "people": ["id", "person_id", "canonical_name", "kind", "councillor_id",
               "public_body", "public_body_id"],
    "attendance": ["id", "meeting_id", "meeting_date", "person_id", "category", "role",
                   "status", "mode", "presented"],
    "items": ["id", "item_id", "meeting_id", "item_number", "item_key", "title", "text",
              "is_minutes_approval", "topics_published", "cofog", "subdomains",
              "procedural"],
    "decisions": ["id", "decision_id", "meeting_id", "meeting_date", "item_number",
                  "item_key", "decision_text", "decision_type", "proposer", "seconder",
                  "proposer_unresolved", "seconder_unresolved"],
}

ARRAY_FIELDS = {"cofog", "subdomains"}

CSVW_DESCRIPTIONS = {
    "meetings": "One SPC meeting, its date and its source minutes.",
    "people": "One person recorded in SPC attendance.",
    "attendance": "One person's attendance at one meeting.",
    "items": "One agenda item with its COFOG 1999 and transport-subdomain topics.",
    "decisions": "One official decision, as a verbatim quote.",
}

#: field -> (CSVW datatype, description). Kept in one place because the same
#: column appears in several tables.
FIELD_SPECS = {
    "id": ("uri", "Persistent URI for this record"),
    "meeting_id": ("string", "Canonical meeting identifier, <council>/<committee>/<YYYY-MM-DD>"),
    "meeting_date": ("date", "Date of the meeting"),
    "committee_id": ("string", "Committee identifier, <council>/<committee>"),
    "committee_name": ("string", "Committee name as published"),
    "public_body": ("uri", "URI of the body in the Public Bodies dataset"),
    "public_body_id": ("integer", "Internal public_body_id, retained for joins"),
    "venue": ("string", "Venue as printed in the minutes"),
    "start_time": ("string", "Start time as printed"),
    "end_time": ("string", "End time as printed"),
    "source_url": ("uri", "URL of the source minutes PDF"),
    "source_sha256": ("string", "SHA-256 of the source PDF bytes"),
    "minutes_path": ("string", "Verbatim Markdown minutes, relative to the dataset root"),
    "attendance_published": ("boolean", "false when the meeting's attendance was withheld"),
    "person_id": ("string", "Stable person identifier"),
    "canonical_name": ("string", "Canonical name from the committed register"),
    "kind": ("string", "councillor, sectoral_representative, official or guest"),
    "councillor_id": ("string", "Councillor ID used by the motions dataset; empty for other kinds"),
    "category": ("string", "councillors, sectoral_representatives, apologies, officials or presenters"),
    "role": ("string", "Role as printed, empty when none is printed"),
    "status": ("string", "present or apologies"),
    "mode": ("string", "remote, in_person or not_stated"),
    "presented": ("boolean", "true when the person's name also appears in the presenters block"),
    "item_number": ("string", "Number as printed; not unique (two items may share one)"),
    "item_id": ("string", "Dataset-relative item identifier, <meeting_id>/<item_key>"),
    "item_key": ("string", "Stable item key, e.g. item-6-0 and item-6-0-2"),
    "title": ("string", "Item title as printed"),
    "text": ("string", "Item text, page furniture removed"),
    "is_minutes_approval": ("boolean", "true for approval of the previous meeting's minutes"),
    "topics_published": ("boolean", "false when the item's topics were withheld"),
    "cofog": ("string", "Pipe-separated COFOG 1999 codes, primary first; empty when withheld"),
    "subdomains": ("string", "Pipe-separated transport subdomains; empty for non-transport items"),
    "procedural": ("boolean", "true for a purely procedural item; empty when withheld"),
    "decision_id": ("string", "Stable decision identifier, <meeting_id>/d<NN>"),
    "decision_text": ("string", "Verbatim contiguous quote from the item text"),
    "decision_type": ("string", "agreed, adopted, recommended_to_council, referred, deferred or appointment"),
    "proposer": ("string", "Person ID of the proposer; empty when the minutes do not name one"),
    "seconder": ("string", "Person ID of the seconder; empty when the minutes do not name one"),
    "proposer_unresolved": ("boolean", "true when a named proposer could not be resolved, grounded or found present"),
    "seconder_unresolved": ("boolean", "true when a named seconder could not be resolved, grounded or found present"),
}

FIELD_TITLES = {
    "id": "ID", "cofog": "COFOG 1999", "public_body": "Public Body",
    "public_body_id": "Public Body ID", "source_url": "Source URL",
    "source_sha256": "Source SHA-256", "minutes_path": "Minutes Path",
}


def _record_type(kind: str) -> str:
    return {
        "meetings": "spc:Meeting", "people": "spc:Person",
        "attendance": "spc:Attendance", "items": "spc:Item",
        "decisions": "spc:Decision",
    }[kind]


def _body_uri_for(body_id: int, lookup: dict[int, str]) -> str:
    try:
        return body_uri(lookup[body_id])
    except KeyError:
        raise ValueError(
            f"public_body_id {body_id} in the SPC export does not resolve in Public Bodies"
        ) from None


def build_records(export: dict, body_slug_lookup: dict[int, str]) -> dict[str, list[dict]]:
    """Add @id/@type and resolved public-body URIs to every exported record."""
    records: dict[str, list[dict]] = {kind: [] for kind in KINDS}
    for kind in KINDS:
        for row in export.get(kind, []):
            record = dict(row)
            record["@type"] = _record_type(kind)
            record.pop("id", None)
            if "public_body_id" in record:
                record["public_body"] = _body_uri_for(
                    int(record["public_body_id"]), body_slug_lookup)
            records[kind].append(record)

    # The export identifies each record by its canonical key; derive the @id
    # from that key so the JSON-LD and CSV identifiers agree.
    for meeting in records["meetings"]:
        meeting["@id"] = f"{BASE_URI}/spc-meetings/meeting/{meeting['meeting_id']}"
    for person in records["people"]:
        person["@id"] = f"{BASE_URI}/spc-meetings/person/{person['person_id']}"
    for row in records["attendance"]:
        row["@id"] = (f"{BASE_URI}/spc-meetings/attendance/"
                      f"{row['meeting_id']}/{row['person_id']}")
    for item in records["items"]:
        item["@id"] = (f"{BASE_URI}/spc-meetings/item/"
                       f"{item['meeting_id']}/{item['item_key']}")
    for decision in records["decisions"]:
        decision["@id"] = (f"{BASE_URI}/spc-meetings/decision/"
                           f"{decision['decision_id']}")
    return records


def _id_of(kind: str, record: dict) -> str:
    return record["@id"]


def jsonld_document(kind: str, records: list[dict]) -> bytes:
    context = {
        "@vocab": "https://schema.org/",
        "spc": f"{BASE_URI}/ns/spc#",
        "dct": "http://purl.org/dc/terms/",
        "public_body": {"@id": "spc:publicBody", "@type": "@id"},
    }
    return render_jsonld({"@context": context, "@graph": records})


def csv_bytes(kind: str, records: list[dict]) -> bytes:
    fieldnames = CSV_FIELDS[kind]
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for record in records:
        row = {}
        for field in fieldnames:
            if field == "id":
                value = _id_of(kind, record)
            else:
                value = record.get(field)
            if isinstance(value, list):
                value = "|".join(str(part) for part in value)
            elif isinstance(value, bool):
                value = "true" if value else "false"
            row[field] = "" if value is None else value
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def csvw_metadata(kind: str) -> bytes:
    columns = []
    for field in CSV_FIELDS[kind]:
        datatype, description = FIELD_SPECS[field]
        column = {
            "name": field,
            "titles": FIELD_TITLES.get(field, field.replace("_", " ").title()),
            "datatype": datatype,
            "description": description,
        }
        if field in ARRAY_FIELDS:
            column["separator"] = "|"
            column["null"] = ""
        columns.append(column)
    return json.dumps({
        "@context": "http://www.w3.org/ns/csvw",
        "url": f"{kind}.csv",
        "tableSchema": {
            "columns": columns,
            "primaryKey": "id",
            "aboutUrl": "{id}",
        },
    }, indent=2).encode("utf-8") + b"\n"


COVERAGE = ("Meath County Council's Transportation and Urban Regeneration Strategic Policy "
            "Committee: six meetings, February 2025 to May 2026")

TABLE_BLURBS = {
    "meetings": "one row per meeting",
    "people": "one row per person recorded in attendance",
    "attendance": "one row per person per meeting",
    "items": "agenda items with their topics",
    "decisions": "official decisions as contiguous quotes from the minutes",
}


def field_table(kind: str) -> list[str]:
    lines = ["| Field | Type | Description |", "|---|---|---|"]
    for field in CSV_FIELDS[kind]:
        datatype, description = FIELD_SPECS[field]
        lines.append(f"| `{field}` | {datatype} | {description} |")
    return lines


def minutes_index_bytes(export: dict) -> bytes:
    """A resolvable listing of the verbatim minutes (Pages serves no directory index)."""
    lines = ["# Verbatim minutes", "",
             "One Markdown file per meeting, rendered from the council's published PDF.", ""]
    for minutes in sorted(export.get("minutes", []), key=lambda m: m["path"]):
        name = minutes["path"].removeprefix("minutes/")
        lines.append(f"- [{name}]({name})")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def readme_bytes(export: dict, report: dict) -> bytes:
    lines = [
        "# SPC meetings",
        "",
        "**Dataset URI:** `https://data.publicinformation.ie/dataset/spc-meetings`",
        "",
        f"Coverage: {COVERAGE}. No other council or committee is published yet.",
        "The dataset holds who attended, their attendance, agenda items with COFOG 1999",
        "topics, official decisions as verbatim quotes, and the minutes rendered verbatim",
        "as Markdown.",
        "",
        "## Versioning",
        "",
        "This directory mirrors the newest immutable release, `../../v1.1.0/spc-meetings/`",
        "(earlier releases stay in place). `owl:versionInfo` is bumped by hand for a breaking",
        "or additive schema change; `dct:modified` in the catalogue record changes only when",
        "the published content changes.",
        "",
        "## Files",
        "",
    ]
    for kind in KINDS:
        lines.append(f"- `{kind}` – {TABLE_BLURBS[kind]}")
    lines += [
        "- `minutes/<council>/<committee>/<date>.md` – the verbatim minutes; "
        "[`minutes/index.md`](minutes/index.md) lists them",
        "",
        "Each table is published as JSON-LD and CSV with CSVW metadata "
        "(`<table>.csv-metadata.json`). Related: "
        "[JSON Schema](../../schemas/spc-meetings.schema.json), "
        "[DCAT-AP catalogue record](../../catalog/dataset-spc-meetings.ttl), and the "
        "vocabularies [`cofog-1999`](../../vocabularies/cofog-1999.md), "
        "[`transport-subdomain`](../../vocabularies/transport-subdomain.csv), "
        "[`spc-attendance-status`](../../vocabularies/spc-attendance-status.csv), "
        "[`spc-attendance-mode`](../../vocabularies/spc-attendance-mode.csv), "
        "[`spc-attendee-category`](../../vocabularies/spc-attendee-category.csv) and "
        "[`spc-decision-type`](../../vocabularies/spc-decision-type.csv) under "
        "[`../../vocabularies/`](../../vocabularies/).",
        "",
        "## Tables and fields",
        "",
        "Tables join on `meeting_id`, `item_key` (with `meeting_id`) and `person_id`.",
        "",
        "A `decision_id` (`<meeting_id>/d<NN>`) is allocated once and never changes or "
        "is reused, even if the extraction is re-run. A number can be missing from a "
        "meeting where a decision was retired; it is not reassigned.",
        "",
    ]
    for kind in KINDS:
        lines += [f"### {kind}", ""] + field_table(kind) + [""]
    lines += [
        "## Reading withheld and empty values",
        "",
        "- The pipeline fails closed: a value it cannot confirm is withheld, not guessed.",
        "- `attendance_published` is false on a meeting whose attendance is withheld because",
        "  a printed name could not be resolved to the committed register. That meeting has",
        "  no attendance rows.",
        "- `topics_published` is false when an item's topics were withheld; `cofog`,",
        "  `subdomains` and `procedural` are then null.",
        "- In JSON-LD, null means withheld and `[]` means genuinely none. In CSV both are an",
        "  empty cell, so read `topics_published` to tell them apart.",
        "- `cofog` and `subdomains` are pipe-joined in CSV (`a|b`); CSVW declares",
        "  `\"separator\": \"|\"`. They are arrays in JSON-LD.",
        "- `proposer` and `seconder` are empty when the minutes name no one, or the name",
        "  could not be confirmed; the matching `*_unresolved` flag is true in the second",
        "  case.",
        "",
        "## Counts",
        "",
        f"- Meetings: {report.get('meetings', 0)}",
        f"- People: {report.get('people', 0)}",
        f"- Attendance rows: {report.get('attendance', 0)}",
        f"- Items: {report.get('items', 0)}",
        f"- Decisions: {report.get('decisions', 0)}",
        "",
        "## People named in this dataset",
        "",
        "The dataset names councillors, council officials, sectoral representatives (which",
        "can include private citizens, for example Public Participation Network",
        "representatives), presenters and guests, with their attendance, apologies and",
        "the role printed in the minutes. Every name and role comes from minutes the",
        "council itself published. Names are matched to a committed register; nothing is",
        "added about a person beyond what the minutes print. To ask for a correction or",
        "removal, write to dave@publicinformation.ie.",
        "",
        "## Source, attribution and licence",
        "",
        "Source: Meath County Council, Transportation and Urban Regeneration Strategic",
        "Policy Committee minutes, retrieved from www.meath.ie; each meeting records its",
        "`source_url` and the PDF's `source_sha256`. The minutes are the council's",
        "material, reproduced here without alteration to their wording.",
        "",
        "COFOG 1999 is the UN Statistics Division classification; transport subdomains",
        "follow the transport-governance vocabulary. The topics, decisions and attendance",
        "tables are derived by PublicInformation.ie (an LLM proposes topics and decisions;",
        "each decision is checked to be a verbatim quote).",
        "",
        "The derived dataset is published under CC BY 4.0. Meath County Council's own",
        "re-use terms for the underlying minutes have not been independently confirmed",
        "against www.meath.ie; if you re-use the verbatim minutes, check them.",
        "Attribute as: *Source: Meath County Council; processed by PublicInformation.ie.*",
        "",
        "## Reproducing",
        "",
        "See `pipelines/spc_pipeline/README.md` in the repository: requirements, the LLM",
        "credentials and cost, and the step order.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def build_outputs(export: dict, records: dict[str, list[dict]],
                  output_dir: Path) -> dict[Path, bytes]:
    generated: dict[Path, bytes] = {}
    for kind in KINDS:
        generated[output_dir / f"{kind}.jsonld"] = jsonld_document(kind, records[kind])
        generated[output_dir / f"{kind}.csv"] = csv_bytes(kind, records[kind])
        generated[output_dir / f"{kind}.csv-metadata.json"] = csvw_metadata(kind)
    for minutes in export.get("minutes", []):
        generated[output_dir / minutes["path"]] = minutes["markdown"].encode("utf-8")
    generated[output_dir / "minutes" / "index.md"] = minutes_index_bytes(export)
    generated[output_dir / "README.md"] = readme_bytes(export, export.get("report", {}))
    return generated


def write_if_changed(generated: dict[Path, bytes], ttl_path: Path,
                     output_dir: Path) -> bool:
    """Write changed files, delete stale ones, and stamp only on a real change.

    ``output_dir`` is owned by the dataset: a file left there by an earlier run
    (a minutes file whose meeting now fails render, for example) is deleted, so
    it cannot stay public. Deleting a file is a content change.
    """
    for path in generated:
        path.parent.mkdir(parents=True, exist_ok=True)
    output_dir = Path(output_dir)
    stale = [
        path for path in output_dir.rglob("*")
        if path.is_file() and path not in generated
    ] if output_dir.exists() else []
    for path in stale:
        path.unlink()
    _remove_empty_directories(output_dir, stale)
    changed = stamp_if_changed(ttl_path, list(generated), generated)
    if stale and not changed:
        stamp_modified(ttl_path)
    return changed or bool(stale)


def _remove_empty_directories(output_dir: Path, removed: list[Path]) -> None:
    for path in sorted({path.parent for path in removed}, key=lambda p: len(p.parts),
                       reverse=True):
        while path != output_dir and path.exists() and not any(path.iterdir()):
            path.rmdir()
            path = path.parent


def mirror_to_latest(output_dir: Path, latest_dir: Path) -> None:
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(output_dir, latest_dir)


def main() -> None:
    export_data = json.loads(Path(EXPORT_PATH).read_text())
    export = export_data.get("results", export_data)
    export["report"] = export_data.get("report", {})
    with open(FIND_PUBLIC_BODIES_PATH) as handle:
        public_bodies = json.load(handle)["public_bodies"]
    with open(SLUG_SEED_PATH) as handle:
        slug_seed = {int(key): value for key, value in json.load(handle).items()}
    lookup = build_body_slug_lookup(public_bodies, slug_seed)

    records = build_records(export, lookup)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = build_outputs(export, records, output_dir)
    changed = write_if_changed(generated, Path(TTL_PATH), output_dir)
    if changed:
        mirror_to_latest(output_dir, Path(LATEST_DIR))
        print(f"Published {len(records['meetings'])} meetings (content changed, "
              f"dct:modified updated)")
    else:
        print(f"Published {len(records['meetings'])} meetings (no content change, "
              f"dct:modified untouched)")


if __name__ == "__main__":
    main()
