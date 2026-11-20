#!/usr/bin/env python3
"""Transform the datacatalogue.gov.ie pipeline's resolved records to JSON-LD and
CSV for the datacatalogue-gov-ie-links dataset.
Usage: python scripts/transform_datacatalogue_links.py
"""
import json
import os
import shutil
from pathlib import Path

from src.lib.body_refs import BASE_URI, build_body_slug_lookup
from src.lib.dataset_publish import render_csv, render_jsonld, stamp_if_changed

APPLY_OVERRIDES_OUTPUT_PATH = "pipelines/datacatalogue_pipeline/steps/apply_overrides/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v1.0.0/datacatalogue-gov-ie-links"
LATEST_DIR = "public/latest/datacatalogue-gov-ie-links"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/datacatalogue-gov-ie-links.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/datacatalogue-gov-ie-links.csv"
TTL_PATH = "public/catalog/dataset-datacatalogue-gov-ie-links.ttl"

CSV_FIELDNAMES = [
    "id", "public_body", "datacatalogue_slug", "datacatalogue_name",
    "datacatalogue_url", "datacatalogue_package_count", "datacatalogue_description",
]


def load_slug_lookup():
    """Map public_body_id -> permanent slug, exactly as public-bodies does.

    Delegates to the shared build_body_slug_lookup() with the frozen slug
    seed (not a fresh slugify of the name): a seeded id must keep the slug
    already published, so the `public_body` URI below always equals the
    `@id` in the public-bodies dataset. Names with diacritics or an
    apostrophe ("An Coimisiún Pleanála", "President's Establishment")
    deliberately differ between the two.
    """
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        bodies = json.load(f)["public_bodies"]
    with open(SLUG_SEED_PATH) as f:
        slug_seed = {int(k): v for k, v in json.load(f).items()}
    return build_body_slug_lookup(bodies, slug_seed)


def build_record(record, body_slug_lookup):
    """Build one datacatalogue.gov.ie link record.

    Raises for an unresolvable public_body_id rather than guessing or
    dropping the relationship silently — apply_overrides already drops
    every record without a non-null public_body_id, so a KeyError here
    means it doesn't resolve against the current public-bodies data.

    Package count and description are carried only where the source
    provides them, per the dataset's published-record contract.
    """
    body_id = record["public_body_id"]
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(f"Unknown public_body_id in apply_overrides output: {body_id!r}")

    built = {
        "@id": f"{BASE_URI}/datacatalogue-gov-ie-links/{record['datacatalogue_slug']}",
        "@type": "dcl:DataCatalogueLink",
        "public_body": f"{BASE_URI}/body/{slug}",
        "datacatalogue_slug": record["datacatalogue_slug"],
        "datacatalogue_name": record["datacatalogue_name"],
        "datacatalogue_url": record["datacatalogue_url"],
    }
    if record.get("datacatalogue_package_count") is not None:
        built["datacatalogue_package_count"] = record["datacatalogue_package_count"]
    description = (record.get("datacatalogue_description") or "").strip()
    if description:
        built["datacatalogue_description"] = description
    return built


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "dcl": f"{BASE_URI}/ns/dcl#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "dcl:publicBody", "@type": "@id"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows, leaving absent optional values empty."""
    rows = []
    for r in records:
        rows.append({
            "id": r["@id"],
            "public_body": r["public_body"],
            "datacatalogue_slug": r["datacatalogue_slug"],
            "datacatalogue_name": r["datacatalogue_name"],
            "datacatalogue_url": r["datacatalogue_url"],
            "datacatalogue_package_count": r.get("datacatalogue_package_count", ""),
            "datacatalogue_description": r.get("datacatalogue_description", ""),
        })
    return CSV_FIELDNAMES, rows


def copy_to_latest():
    """Copy the versioned output directory to latest/ as a build-time snapshot.

    Copies the committed CSVW metadata and README alongside the payloads.
    Not a symlink: static hosts and various git checkout paths don't
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

    with open(APPLY_OVERRIDES_OUTPUT_PATH) as f:
        resolved = json.load(f)["results"]

    body_slug_lookup = load_slug_lookup()
    records = [build_record(r, body_slug_lookup) for r in resolved]

    jsonld_data = transform_to_jsonld(records)
    fieldnames, rows = transform_to_csv_rows(records)
    changed = publish(jsonld_data, fieldnames, rows)
    if changed:
        copy_to_latest()
        print(f"Transformed {len(records)} datacatalogue.gov.ie links to JSON-LD and CSV (content changed, dct:modified updated)")
    else:
        print(f"Transformed {len(records)} datacatalogue.gov.ie links to JSON-LD and CSV (no content change, dct:modified untouched)")


if __name__ == "__main__":
    main()
