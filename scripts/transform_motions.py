#!/usr/bin/env python3
"""Publish the Motions dataset from minutes_pipeline's canonical output.

Reads pipelines/minutes_pipeline/steps/export_motions/output.json (the flat,
deterministic source of every canonical motion record) and the authoritative
Public Bodies data, then writes JSON-LD + CSV to public/v1.0.0/motions/ (with
the committed CSVW metadata and README alongside), and mirrors the directory
to public/latest/motions/ only when the payload content actually changes.

The public_body URI on every record is resolved through the same permanent
slug machinery as the public-bodies dataset (body_refs.build_body_slug_lookup
with slug_seed.json), never the motion's own public_body_slug — an
unresolvable public_body_id aborts publication rather than emitting a motion
with a missing or invented body link.
Usage: uv run python scripts/transform_motions.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.lib.body_refs import BASE_URI, build_body_slug_lookup, body_uri
from src.lib.dataset_publish import render_csv, render_jsonld, stamp_if_changed

EXPORT_MOTIONS_PATH = "pipelines/minutes_pipeline/steps/export_motions/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v1.0.0/motions"
LATEST_DIR = "public/latest/motions"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/motions.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/motions.csv"
TTL_PATH = "public/catalog/dataset-motions.ttl"

CSV_FIELDNAMES = [
    "id", "public_body", "public_body_id", "motion_id", "municipal_district",
    "meeting_date", "meeting_type", "source_file_url", "motion_text",
    "proposer", "seconder", "status",
]

# Retained verbatim from export_motions output; municipal_district, proposer
# and seconder may be null (a full-council meeting has no district; a proposer
# or seconder is sometimes not recorded).
MOTION_FIELDS = [
    "motion_id", "public_body_id", "municipal_district", "meeting_date",
    "meeting_type", "source_file_url", "motion_text", "proposer", "seconder",
    "status",
]


def build_record(motion, body_slug_lookup):
    """Build one motion record.

    Resolves public_body_id through the authoritative permanent slug lookup
    (never the motion's own public_body_slug) and raises on an unresolvable
    id rather than guessing or dropping the link silently.
    """
    body_id = motion["public_body_id"]
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(
            f"Unknown public_body_id in export_motions output: {body_id!r}")
    record = {
        "@id": f"{BASE_URI}/motion/{motion['motion_id']}",
        "@type": "mot:Motion",
        "public_body": body_uri(slug),
    }
    for field in MOTION_FIELDS:
        value = motion.get(field)
        if value is not None:
            record[field] = value
    return record


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "mot": f"{BASE_URI}/ns/motions#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "mot:publicBody", "@type": "@id"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows, @id -> id, null fields as empty cells."""
    fieldnames = CSV_FIELDNAMES
    rows = []
    for r in records:
        row = {field: r.get(field, "") for field in MOTION_FIELDS}
        row["id"] = r["@id"]
        row["public_body"] = r["public_body"]
        rows.append(row)
    return fieldnames, rows


def copy_to_latest():
    """Copy the versioned output directory to latest/ as a build-time snapshot.

    Not a symlink: Static hosts and various git checkout paths don't
    reliably serve/preserve symlinks. This also sweeps the committed
    csv-metadata.json and README.md into latest/ alongside the payloads.
    """
    shutil.copytree(OUTPUT_DIR, LATEST_DIR, dirs_exist_ok=True)


def publish(
    jsonld_data, fieldnames, rows,
    jsonld_path=Path(JSONLD_OUTPUT_PATH), csv_path=Path(CSV_OUTPUT_PATH),
    ttl_path=Path(TTL_PATH),
):
    """Write jsonld/csv and stamp dct:modified only if content changed. Returns True if written."""
    generated = {
        jsonld_path: render_jsonld(jsonld_data),
        csv_path: render_csv(fieldnames, rows),
    }
    return stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(EXPORT_MOTIONS_PATH) as f:
        motions = json.load(f)["results"]
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        public_bodies = json.load(f)["public_bodies"]
    with open(SLUG_SEED_PATH) as f:
        raw_slug_seed = json.load(f)
    slug_seed = {int(k): v for k, v in raw_slug_seed.items()}
    body_slug_lookup = build_body_slug_lookup(public_bodies, slug_seed)

    records = [build_record(m, body_slug_lookup) for m in motions]

    jsonld_data = transform_to_jsonld(records)
    fieldnames, rows = transform_to_csv_rows(records)
    changed = publish(jsonld_data, fieldnames, rows)
    if changed:
        copy_to_latest()
        print(f"Transformed {len(records)} motions to JSON-LD and CSV (content changed, dct:modified updated)")
    else:
        print(f"Transformed {len(records)} motions to JSON-LD and CSV (no content change, dct:modified untouched)")


if __name__ == "__main__":
    main()