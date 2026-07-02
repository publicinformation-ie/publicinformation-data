#!/usr/bin/env python3
"""Transform FOI pipeline data to JSON-LD and CSV for Slice 1 (Public Bodies).
Usage: python scripts/transform_public_bodies.py
"""
import json
import csv
import re

BASE_URI = "https://publicinformation-ie.codeberg.page/publicinformation-data"

BODY_TYPE_MAP = {
    "government department": "department",
    "local authority": "local_authority",
    "public body": "public_body",
}

FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
INCLUSIONS_PATH = "pipelines/foi_pipeline/steps/find_public_bodies_subject_to_foi/inclusions.json"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
JSONLD_OUTPUT_PATH = "public/public-bodies.jsonld"
CSV_OUTPUT_PATH = "public/public-bodies.csv"


def slugify(text):
    """Convert text to a URL slug."""
    if not text:
        return "unknown"
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug.strip('-')


def map_body_type(category):
    """Map a raw pipeline category to a body-type vocabulary notation.

    Raises ValueError for unrecognized categories rather than guessing —
    an unbacked type would be a fabricated value.
    """
    try:
        return BODY_TYPE_MAP[category]
    except KeyError:
        raise ValueError(f"Unrecognized public body category: {category!r}")


def build_contact_email_lookup(pipeline_data_bodies):
    """Map public_body_id -> email for bodies with a successfully crawled FOI email.

    find_public_bodies/output.json never has real crawl results (always
    "not_attempted"); only pipeline-data.json's 229 crawled records do.
    """
    lookup = {}
    for body in pipeline_data_bodies:
        foi_email = body.get("status", {}).get("foi_email", {})
        if foi_email.get("status") == "success" and foi_email.get("email"):
            lookup[body["public_body_id"]] = foi_email["email"]
    return lookup


def build_record(body, foi_subject_ids, contact_email_lookup):
    """Build one public body record in the corrected Slice 1 data model."""
    body_id = body["public_body_id"]
    slug = slugify(body["name"])
    foi_subject = body_id in foi_subject_ids
    record = {
        "@id": f"{BASE_URI}/body/{slug}",
        "@type": "foi:PublicBody",
        "name": body["name"],
        "type": map_body_type(body["category"]),
        "foi_subject": foi_subject,
        "foi_scope": f"{BASE_URI}/ns/foi#FullScope" if foi_subject else f"{BASE_URI}/ns/foi#NoScope",
    }
    if body.get("official_website_url"):
        record["website"] = body["official_website_url"]
    email = contact_email_lookup.get(body_id)
    if email:
        record["contact_email"] = email
    return record
