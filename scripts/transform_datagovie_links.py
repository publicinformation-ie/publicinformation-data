#!/usr/bin/env python3
"""Transform the data.gov.ie pipeline's resolved records to JSON-LD and CSV
for the data-gov-ie-links dataset.
Usage: python scripts/transform_datagovie_links.py
"""
import json
import csv
import os
import shutil

from scripts.transform_public_bodies import BASE_URI, slugify

APPLY_OVERRIDES_OUTPUT_PATH = "pipelines/datagovie_pipeline/steps/apply_overrides/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
OUTPUT_DIR = "public/v1.0.0/data-gov-ie-links"
LATEST_DIR = "public/latest/data-gov-ie-links"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/data-gov-ie-links.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/data-gov-ie-links.csv"


def build_body_slug_lookup(public_bodies):
    """Map public_body_id -> slug, using the same slugify() as public-bodies.

    Reusing slugify() here (rather than re-deriving it) is what guarantees
    the public_body URI below matches an @id already published in the
    public-bodies dataset.
    """
    return {b["public_body_id"]: slugify(b["name"]) for b in public_bodies}


def build_record(dgi_record, body_slug_lookup):
    """Build one data.gov.ie link record.

    Raises for an unresolvable public_body_id rather than guessing or
    dropping the relationship silently — apply_overrides already drops
    every record without a non-null public_body_id, so a KeyError here
    means it doesn't resolve against the current public-bodies data.
    """
    body_id = dgi_record["public_body_id"]
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(f"Unknown public_body_id in apply_overrides output: {body_id!r}")
    return {
        "@id": f"{BASE_URI}/data-gov-ie-links/{dgi_record['datagovie_slug']}",
        "@type": "dgi:DataGovIeLink",
        "public_body": f"{BASE_URI}/body/{slug}",
        "datagovie_slug": dgi_record["datagovie_slug"],
        "datagovie_url": dgi_record["datagovie_url"],
        "datagovie_package_count": dgi_record["datagovie_package_count"],
    }


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "dgi": f"{BASE_URI}/ns/dgi#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "dgi:publicBody", "@type": "@id"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows."""
    fieldnames = ["id", "public_body", "datagovie_slug", "datagovie_url", "datagovie_package_count"]
    rows = []
    for r in records:
        rows.append({
            "id": r["@id"],
            "public_body": r["public_body"],
            "datagovie_slug": r["datagovie_slug"],
            "datagovie_url": r["datagovie_url"],
            "datagovie_package_count": r["datagovie_package_count"],
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

    with open(APPLY_OVERRIDES_OUTPUT_PATH) as f:
        dgi_records = json.load(f)["results"]
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        public_bodies = json.load(f)["public_bodies"]

    body_slug_lookup = build_body_slug_lookup(public_bodies)
    records = [build_record(r, body_slug_lookup) for r in dgi_records]

    jsonld_data = transform_to_jsonld(records)
    with open(JSONLD_OUTPUT_PATH, "w") as f:
        json.dump(jsonld_data, f, indent=2, ensure_ascii=False)

    fieldnames, rows = transform_to_csv_rows(records)
    with open(CSV_OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    copy_to_latest()

    print(f"Transformed {len(records)} data.gov.ie links to JSON-LD and CSV")


if __name__ == "__main__":
    main()
