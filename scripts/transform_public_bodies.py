#!/usr/bin/env python3
"""Transform FOI pipeline data to JSON-LD and CSV for Slice 1 (Public Bodies).
Usage: python scripts/transform_public_bodies.py
"""
import json
import csv
import re
import os
import shutil

from scripts.lib.body_refs import build_body_slug_lookup, body_uri

BASE_URI = "https://publicinformation-ie.codeberg.page/publicinformation-data"

BODY_TYPE_MAP = {
    "government department": "department",
    "local authority": "local_authority",
    "public body": "public_body",
}

FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
INCLUSIONS_PATH = "pipelines/foi_pipeline/steps/find_public_bodies_subject_to_foi/inclusions.json"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v2.0.0/public-bodies"
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


CSO_FIELDS = [
    "parent_id", "parent_name", "sector", "legal_status",
    "government_department_id", "government_department",
    "nace_code", "nace_section", "nace_section_name", "nace_division",
    "nace_group", "nace_class", "nace_class_name",
    "cro", "data_vintage", "is_commercial", "is_financial",
    "aegis", "legal_entity_type",
]


def build_cso_lookup(cso_records):
    """public_body_id -> dict of whitelisted CSO fields only. Deliberately
    excludes internal CSO-pipeline fields (llm_*, apify_*,
    description_for_sub_sector, official_website_url) that are not part of
    the published catalog schema."""
    lookup = {}
    for r in cso_records:
        lookup[r["public_body_id"]] = {field: r.get(field) for field in CSO_FIELDS}
    return lookup


def build_crawl_status_lookup(pipeline_bodies):
    """public_body_id -> raw status dict, for the 229 of 883 bodies present
    in pipeline_bodies. Bodies absent from pipeline_bodies simply have no
    key here -- callers must treat a missing key as "no crawl data at all",
    not as empty/default crawl-status objects."""
    lookup = {}
    for body in pipeline_bodies:
        lookup[body["public_body_id"]] = body.get("status", {})
    return lookup


def build_status_object(raw, value_field):
    """Build a {value_field, status[, verified]} object from a raw crawl
    status dict, e.g. {"url": ..., "status": ..., "verified": ...} for
    website_url/foi_page/disclosures_page, or {"email": ..., "status": ...}
    for foi_email. Returns None if raw itself is missing (body was never
    crawled at all). Omits value_field if its value is null (crawl attempted
    but found nothing); omits "verified" unless the source actually has it
    (never fabricates verified: false)."""
    if raw is None:
        return None
    obj = {}
    value = raw.get(value_field)
    if value is not None:
        obj[value_field] = value
    obj["status"] = raw.get("status")
    if "verified" in raw:
        obj["verified"] = raw["verified"]
    return obj


def build_disclosure_files_object(raw):
    """total/valid/failed are always present ints when raw is present (no
    per-leaf null-omission needed), only the whole object is omitted when
    raw itself is missing."""
    if raw is None:
        return None
    return {
        "total": raw.get("total"),
        "valid": raw.get("valid"),
        "failed": raw.get("failed"),
        "status": raw.get("status"),
    }


def build_foi_requests_object(raw):
    if raw is None:
        return None
    return {
        "valid": raw.get("valid"),
        "errors": raw.get("errors"),
        "status": raw.get("status"),
    }


def build_record(body, foi_subject_ids, contact_email_lookup, slug_lookup):
    """Build one public body record in the corrected Slice 1 data model."""
    body_id = body["public_body_id"]
    slug = slug_lookup[body_id]
    foi_subject = body_id in foi_subject_ids
    record = {
        "@id": body_uri(slug),
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
    with open(SLUG_SEED_PATH) as f:
        raw_slug_seed = json.load(f)
    slug_seed = {int(k): v for k, v in raw_slug_seed.items()}
    slug_lookup = build_body_slug_lookup(bodies, slug_seed)
    contact_email_lookup = build_contact_email_lookup(pipeline_bodies)
    records = [build_record(b, foi_subject_ids, contact_email_lookup, slug_lookup) for b in bodies]
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
