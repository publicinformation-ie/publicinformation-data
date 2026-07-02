#!/usr/bin/env python3
"""Transform FOI pipeline data to JSON-LD and CSV for Slice 1 (Public Bodies).
Usage: python scripts/transform_public_bodies.py
"""
import json
import csv
import re
import os
import shutil

BASE_URI = "https://publicinformation-ie.codeberg.page/publicinformation-data"

BODY_TYPE_MAP = {
    "government department": "department",
    "local authority": "local_authority",
    "public body": "public_body",
}

FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
INCLUSIONS_PATH = "pipelines/foi_pipeline/steps/find_public_bodies_subject_to_foi/inclusions.json"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
OUTPUT_DIR = "public/v1.0.0/public-bodies"
LATEST_DIR = "public/latest/public-bodies"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/public-bodies.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/public-bodies.csv"


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


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "foi": f"{BASE_URI}/ns/foi#",
            "dct": "http://purl.org/dc/terms/",
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows. Booleans use lowercase xsd:boolean lexical form."""
    fieldnames = ["id", "name", "type", "website", "foi_subject", "foi_scope", "contact_email"]
    rows = []
    for r in records:
        rows.append({
            "id": r["@id"],
            "name": r["name"],
            "type": r["type"],
            "website": r.get("website", ""),
            "foi_subject": "true" if r["foi_subject"] else "false",
            "foi_scope": r["foi_scope"],
            "contact_email": r.get("contact_email", ""),
        })
    return fieldnames, rows


def copy_to_latest():
    """Copy the versioned output directory to latest/ as a build-time snapshot.

    Not a symlink: Codeberg Pages and various git checkout paths don't
    reliably serve/preserve symlinks.
    """
    shutil.copytree(OUTPUT_DIR, LATEST_DIR, dirs_exist_ok=True)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(FIND_PUBLIC_BODIES_PATH) as f:
        bodies = json.load(f)["public_bodies"]
    with open(INCLUSIONS_PATH) as f:
        foi_subject_ids = set(json.load(f))
    with open(PIPELINE_DATA_PATH) as f:
        pipeline_bodies = json.load(f)["public_bodies"]
    contact_email_lookup = build_contact_email_lookup(pipeline_bodies)

    records = [build_record(b, foi_subject_ids, contact_email_lookup) for b in bodies]

    jsonld_data = transform_to_jsonld(records)
    with open(JSONLD_OUTPUT_PATH, "w") as f:
        json.dump(jsonld_data, f, indent=2, ensure_ascii=False)

    fieldnames, rows = transform_to_csv_rows(records)
    with open(CSV_OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    copy_to_latest()

    print(f"Transformed {len(records)} public bodies to JSON-LD and CSV")


if __name__ == "__main__":
    main()
