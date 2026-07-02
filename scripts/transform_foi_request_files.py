#!/usr/bin/env python3
"""Transform FOI pipeline disclosure-files data to JSON-LD and CSV for the
FOI Request Files dataset.
Usage: python scripts/transform_foi_request_files.py
"""
import json
import csv
import os
import shutil
import hashlib

from scripts.transform_public_bodies import BASE_URI, slugify

DISCLOSURE_FILES_PATH = "public/disclosure-files.json"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
OUTPUT_DIR = "public/v1.0.0/foi-request-files"
LATEST_DIR = "public/latest/foi-request-files"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/foi-request-files.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/foi-request-files.csv"


def hash_document_id(document_url):
    """Deterministic 12-char id derived from document_url.

    Stable across pipeline reruns since document_url is unique per file
    and never null (verified: 1593/1593 unique in current data).
    """
    return hashlib.sha1(document_url.encode("utf-8")).hexdigest()[:12]


def build_body_slug_lookup(pipeline_bodies):
    """Map public_body_id -> slug, using the same slugify() as public-bodies.

    Reusing slugify() here (rather than re-deriving it) is what guarantees
    the public_body URI below matches an @id already published in the
    public-bodies dataset.
    """
    return {b["public_body_id"]: slugify(b["public_body_name"]) for b in pipeline_bodies}


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
        "public_body": f"{BASE_URI}/body/{slug}",
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
