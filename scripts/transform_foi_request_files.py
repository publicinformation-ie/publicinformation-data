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
