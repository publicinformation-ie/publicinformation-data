#!/usr/bin/env python3
"""Build the published COFOG 1999 vocabulary from the pinned SPC reference.

Usage:
    uv run python scripts/build_cofog_vocabulary.py
    uv run python scripts/build_cofog_vocabulary.py --check

Reads pipelines/spc_pipeline/reference/cofog_1999.json — which records the
UNSD source URL, retrieval date and sha256 — and writes every distribution of
the COFOG 1999 vocabulary under public/vocabularies/:

    cofog-1999.json              scheme metadata, nested tree, flat index
    cofog-1999.csv               four-column vocabulary CSV (uri/notation/…)
    cofog-1999.csv-metadata.json CSVW metadata for the CSV
    cofog-1999.ttl               SKOS Turtle

This script is the single writer for those files. The SPC pipeline's
build_vocabularies.py no longer writes COFOG.

Validation is fail closed: the reference must carry complete provenance, unique
codes, known parents (group → division, class → group) and exactly 10
divisions, 69 groups and 109 classes. Every output is built in memory before
anything is written, so an invalid reference changes no file.

Writes go through src/lib/dataset_publish.stamp_if_changed: files are written
and `dct:modified` in public/catalog/dataset-cofog-1999.ttl is restamped only
when a distribution's bytes actually change.

With --check the script builds the same bytes and compares them with the
committed files, exiting non-zero and naming any file that differs. It never
writes.
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
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.lib.dataset_publish import stamp_if_changed  # noqa: E402

REFERENCE = REPO / "pipelines" / "spc_pipeline" / "reference" / "cofog_1999.json"
OUT_DIR = REPO / "public" / "vocabularies"
CATALOG_TTL = REPO / "public" / "catalog" / "dataset-cofog-1999.ttl"

# Control characters cannot be written safely into a Turtle short string or a
# CSV cell; a label carrying one is rejected rather than escaped or rewritten.
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

TITLE = "Classification of the Functions of Government (COFOG) 1999"
NAMESPACE = "https://data.publicinformation.ie/ns/cofog"
SCHEME_URI = NAMESPACE
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
VERSION = "1999"

EXPECTED_COUNTS = {"division": 10, "group": 69, "class": 109}
LEVELS = set(EXPECTED_COUNTS)
SERVICE_TYPES = {"CS": "collective", "IS": "individual"}

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

OUTPUT_NAMES = [
    "cofog-1999.json",
    "cofog-1999.csv",
    "cofog-1999.csv-metadata.json",
    "cofog-1999.ttl",
]


def load_reference(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(reference: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the reference and return its codes, in file order."""
    metadata = reference.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("reference has no metadata object")
    source_url = metadata.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith("http"):
        raise ValueError("reference metadata has no source URL")
    retrieved = metadata.get("retrieved_date")
    if not isinstance(retrieved, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", retrieved):
        raise ValueError("reference metadata has no retrieval date")
    try:
        date.fromisoformat(retrieved)
    except ValueError:
        raise ValueError(f"reference retrieval date {retrieved!r} is not a valid date") from None
    sha256 = metadata.get("sha256")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("reference metadata has no sha256")

    codes = reference.get("codes")
    if not isinstance(codes, list):
        raise ValueError("reference has no codes list")

    seen: set[str] = set()
    for entry in codes:
        if not isinstance(entry, dict):
            raise ValueError(f"code entry {entry!r} is not an object")
        code = entry.get("code")
        level = entry.get("level")
        if not isinstance(code, str) or not code:
            raise ValueError("code entry without a code")
        if code in seen:
            raise ValueError(f"duplicate code {code!r}")
        seen.add(code)
        if level not in LEVELS:
            raise ValueError(f"code {code!r} has unknown level {level!r}")
        if not isinstance(entry.get("description"), str) or not entry["description"]:
            raise ValueError(f"code {code!r} has no description")
        if CONTROL_CHARS.search(code) or CONTROL_CHARS.search(entry["description"]):
            raise ValueError(f"code {code!r} contains a control character")
        parent = entry.get("parent")
        if level == "division":
            if parent is not None:
                raise ValueError(f"division {code!r} has a parent {parent!r}")
        else:
            if not isinstance(parent, str) or parent not in seen:
                raise ValueError(f"code {code!r} has unknown parent {parent!r}")
            if parent == code:
                raise ValueError(f"code {code!r} is its own parent")
        marker = entry.get("marker")
        if level == "class":
            if marker not in SERVICE_TYPES:
                raise ValueError(f"class {code!r} has unknown marker {marker!r}")
        elif marker is not None:
            raise ValueError(f"{level} {code!r} carries a marker {marker!r}")

    counts: dict[str, int] = {level: 0 for level in EXPECTED_COUNTS}
    for entry in codes:
        counts[entry["level"]] += 1
    for level, expected in EXPECTED_COUNTS.items():
        if counts[level] != expected:
            raise ValueError(f"expected {expected} {level}s, found {counts[level]}")

    # Every group's parent must be a division and every class's a group.
    levels = {entry["code"]: entry["level"] for entry in codes}
    for entry in codes:
        parent = entry["parent"]
        if entry["level"] == "group" and levels.get(parent) != "division":
            raise ValueError(f"group {entry['code']!r} parent {parent!r} is not a division")
        if entry["level"] == "class" and levels.get(parent) != "group":
            raise ValueError(f"class {entry['code']!r} parent {parent!r} is not a group")
    return codes


def concept_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """The fields every published concept carries, in JSON and in the tree."""
    return {
        "code": entry["code"],
        "uri": f"{NAMESPACE}#{entry['code']}",
        "label": entry["description"],
        "level": entry["level"],
        "parent": entry["parent"],
        "service_type": SERVICE_TYPES.get(entry.get("marker")),
    }


def build(reference: dict[str, Any]) -> dict[str, bytes]:
    """Build every distribution in memory, keyed by output file name."""
    codes = validate(reference)
    metadata = reference["metadata"]
    index = {c["code"]: c for c in (concept_fields(e) for e in codes)}

    divisions: list[dict[str, Any]] = []
    for entry in codes:
        if entry["level"] == "division":
            divisions.append({**concept_fields(entry), "groups": []})
    for entry in codes:
        if entry["level"] == "group":
            parent = next(d for d in divisions if d["code"] == entry["parent"])
            parent["groups"].append({**concept_fields(entry), "classes": []})
    for entry in codes:
        if entry["level"] == "class":
            for division in divisions:
                for group in division["groups"]:
                    if group["code"] == entry["parent"]:
                        group["classes"].append(concept_fields(entry))
                        break
                else:
                    continue
                break
            else:
                raise ValueError(f"class {entry['code']!r} reached no division")

    scheme = {
        "title": TITLE,
        "version": VERSION,
        "namespace": f"{NAMESPACE}#",
        "license": LICENSE,
        "source": {
            "url": metadata["source_url"],
            "retrieved_date": metadata["retrieved_date"],
            "sha256": metadata["sha256"],
        },
    }
    payload = {"scheme": scheme, "divisions": divisions, "concepts": list(index.values())}
    json_bytes = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    csv_bytes = _build_csv(codes)
    metadata_bytes = (json.dumps({
        "@context": "http://www.w3.org/ns/csvw",
        "url": "cofog-1999.csv",
        "tableSchema": {"columns": CSV_COLUMNS, "primaryKey": "uri",
                        "aboutUrl": "{uri}"},
    }, indent=2) + "\n").encode("utf-8")

    ttl_bytes = _build_turtle(metadata, divisions, list(index.values())).encode("utf-8")

    return {
        "cofog-1999.json": json_bytes,
        "cofog-1999.csv": csv_bytes,
        "cofog-1999.csv-metadata.json": metadata_bytes,
        "cofog-1999.ttl": ttl_bytes,
    }


def _build_csv(codes: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for entry in codes:
        marker = f" ({entry['marker']})" if entry.get("marker") else ""
        writer.writerow({
            "uri": f"{NAMESPACE}#{entry['code']}",
            "notation": entry["code"],
            "name": entry["description"],
            "description": f"COFOG 1999 {entry['level']}{marker}",
        })
    return buffer.getvalue().encode("utf-8")


def _turtle_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_turtle(
    metadata: dict[str, Any],
    divisions: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
) -> str:
    scheme_ref = f"<{SCHEME_URI}>"
    top_concepts = ", ".join(f"<{NAMESPACE}#{d['code']}>" for d in divisions)
    lines = [
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        f"{scheme_ref}",
        "    a skos:ConceptScheme ;",
        f'    dct:title "{_turtle_string(TITLE)}"@en ;',
        f"    dct:source <{metadata['source_url']}> ;",
        f"    dct:license <{LICENSE}> ;",
        f'    owl:versionInfo "{VERSION}" ;',
        f"    skos:hasTopConcept {top_concepts} .",
        "",
    ]
    scope_notes = {
        "collective": "Collective service",
        "individual": "Individual service",
    }
    for concept in concepts:
        service_type = concept["service_type"]
        lines.append(f"<{concept['uri']}>")
        lines.append("    a skos:Concept ;")
        lines.append(f"    skos:notation \"{concept['code']}\" ;")
        lines.append(
            f"    skos:prefLabel \"{_turtle_string(concept['label'])}\"@en ;")
        if concept["parent"] is not None:
            lines.append(
                f"    skos:broader <{NAMESPACE}#{concept['parent']}> ;")
        if service_type is not None:
            lines.append(
                f"    skos:scopeNote \"{scope_notes[service_type]}\"@en ;")
        lines.append(f"    skos:inScheme {scheme_ref} .")
        lines.append("")
    return "\n".join(lines)


def check(out_dir: Path, outputs: dict[str, bytes]) -> list[str]:
    """Return the committed files whose bytes differ from the built outputs."""
    differing = []
    for name in OUTPUT_NAMES:
        path = out_dir / name
        if not path.exists() or path.read_bytes() != outputs[name]:
            differing.append(name)
    return differing


def write(out_dir: Path, outputs: dict[str, bytes], catalog_ttl: Path) -> bool:
    """Write changed distributions and restamp the catalogue's dct:modified.

    Returns True when anything changed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = {out_dir / name: outputs[name] for name in OUTPUT_NAMES}
    return stamp_if_changed(catalog_ttl, list(generated), generated)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare the committed files with what this "
                             "script would write, without writing")
    args = parser.parse_args(argv)

    reference = load_reference(REFERENCE)
    outputs = build(reference)
    if args.check:
        differing = check(OUT_DIR, outputs)
        if differing:
            for name in differing:
                print(f"differing: {OUT_DIR / name}", file=sys.stderr)
            return 1
        print("cofog-1999: all distributions match")
        return 0

    if write(OUT_DIR, outputs, CATALOG_TTL):
        print(f"Wrote COFOG 1999 vocabulary to {OUT_DIR}; restamped {CATALOG_TTL.name}")
    else:
        print("cofog-1999: unchanged, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
