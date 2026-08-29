#!/usr/bin/env python3
"""Transform FOI pipeline disclosure-files data to JSON-LD and CSV for the
FOI Request Files dataset.
Usage: python scripts/transform_foi_request_files.py
"""
import json
import os
import shutil
import hashlib
from pathlib import Path

from src.lib.body_refs import BASE_URI, build_body_slug_lookup, body_uri
from src.lib.dataset_publish import render_csv, render_jsonld, stamp_if_changed

DISCLOSURE_FILES_PATH = "public/disclosure-files.json"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v1.1.0/foi-request-files"
LATEST_DIR = "public/latest/foi-request-files"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/foi-request-files.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/foi-request-files.csv"
TTL_PATH = "public/catalog/dataset-foi-request-files.ttl"


def hash_document_id(document_url):
    """Deterministic 12-char id derived from document_url.

    Stable across pipeline reruns since document_url is unique per file
    and never null (verified: 1593/1593 unique in current data).
    """
    return hashlib.sha1(document_url.encode("utf-8")).hexdigest()[:12]


def build_record(file_record, body_slug_lookup):
    """Build one FOI request file record.

    Raises for an unresolvable public_body_id rather than guessing or
    dropping the relationship silently — a broken public_body URI would
    be a fabricated link, worse than a loud failure.
    """
    body_id = file_record["public_body_id"]
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(f"Unknown public_body_id in disclosure-files.json: {body_id!r}")
    return {
        "@id": f"{BASE_URI}/foi-request-file/{hash_document_id(file_record['document_url'])}",
        "@type": "foi:FoiRequestFile",
        "public_body": body_uri(slug),
        "document_url": file_record["document_url"],
        "source_page_url": file_record["source_page_url"],
        "file_type": file_record["file_type"],
    }


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "foi": f"{BASE_URI}/ns/foi#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "foi:publicBody", "@type": "@id"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows."""
    fieldnames = ["id", "public_body", "document_url", "source_page_url", "file_type"]
    rows = []
    for r in records:
        rows.append({
            "id": r["@id"],
            "public_body": r["public_body"],
            "document_url": r["document_url"],
            "source_page_url": r["source_page_url"],
            "file_type": r["file_type"],
        })
    return fieldnames, rows


def copy_to_latest():
    """Copy the versioned output directory to latest/ as a build-time snapshot.

    Not a symlink: Codeberg Pages and various git checkout paths don't
    reliably serve/preserve symlinks.
    """
    shutil.copytree(OUTPUT_DIR, LATEST_DIR, dirs_exist_ok=True)


def publish(
    jsonld_data, fieldnames, rows,
    jsonld_path=Path(JSONLD_OUTPUT_PATH), csv_path=Path(CSV_OUTPUT_PATH), ttl_path=Path(TTL_PATH),
):
    """Write jsonld/csv and stamp dct:modified only if content changed. Returns True if written."""
    generated = {
        jsonld_path: render_jsonld(jsonld_data),
        csv_path: render_csv(fieldnames, rows),
    }
    return stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(DISCLOSURE_FILES_PATH) as f:
        file_records = json.load(f)
    with open(PIPELINE_DATA_PATH) as f:
        pipeline_bodies = json.load(f)["public_bodies"]
    with open(SLUG_SEED_PATH) as f:
        raw_slug_seed = json.load(f)
    slug_seed = {int(k): v for k, v in raw_slug_seed.items()}
    body_slug_lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    records = [build_record(fr, body_slug_lookup) for fr in file_records]
    jsonld_data = transform_to_jsonld(records)
    fieldnames, rows = transform_to_csv_rows(records)
    changed = publish(jsonld_data, fieldnames, rows)
    if changed:
        copy_to_latest()
        print(f"Transformed {len(records)} FOI request files to JSON-LD and CSV (content changed, dct:modified updated)")
    else:
        print(f"Transformed {len(records)} FOI request files to JSON-LD and CSV (no content change, dct:modified untouched)")


if __name__ == "__main__":
    main()
