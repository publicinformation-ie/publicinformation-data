#!/usr/bin/env python3
"""Transform the Who Does What pipeline's resolved records to JSON-LD and CSV
for the Who Does What dataset.
Usage: python scripts/transform_who_does_what.py
"""
import json
import csv
import os
import shutil

from scripts.transform_public_bodies import BASE_URI, slugify

APPLY_OVERRIDES_OUTPUT_PATH = "pipelines/wdw_pipeline/steps/apply_overrides/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
OUTPUT_DIR = "public/v1.0.0/who-does-what"
LATEST_DIR = "public/latest/who-does-what"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/who-does-what.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/who-does-what.csv"


def build_body_slug_lookup(public_bodies):
    """Map public_body_id -> slug, using the same slugify() as public-bodies.

    Reusing slugify() here (rather than re-deriving it) is what guarantees
    the public_body URI below matches an @id already published in the
    public-bodies dataset.
    """
    return {b["public_body_id"]: slugify(b["name"]) for b in public_bodies}


def build_record(wdw_record, body_slug_lookup):
    """Build one Who Does What link record.

    Raises for an unresolvable public_body_id rather than guessing or
    dropping the relationship silently — apply_overrides already guarantees
    every record has a non-null public_body_id, so a KeyError here means it
    doesn't resolve against the current public-bodies data.
    """
    body_id = wdw_record["public_body_id"]
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(f"Unknown public_body_id in apply_overrides output: {body_id!r}")
    return {
        "@id": f"{BASE_URI}/who-does-what/{wdw_record['wdw_slug']}",
        "@type": "wdw:WhoDoesWhatLink",
        "public_body": f"{BASE_URI}/body/{slug}",
        "wdw_slug": wdw_record["wdw_slug"],
        "wdw_url": wdw_record["wdw_url"],
    }


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "wdw": f"{BASE_URI}/ns/wdw#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "wdw:publicBody", "@type": "@id"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows."""
    fieldnames = ["id", "public_body", "wdw_slug", "wdw_url"]
    rows = []
    for r in records:
        rows.append({
            "id": r["@id"],
            "public_body": r["public_body"],
            "wdw_slug": r["wdw_slug"],
            "wdw_url": r["wdw_url"],
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
        wdw_records = json.load(f)["results"]
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        public_bodies = json.load(f)["public_bodies"]

    body_slug_lookup = build_body_slug_lookup(public_bodies)
    records = [build_record(r, body_slug_lookup) for r in wdw_records]

    jsonld_data = transform_to_jsonld(records)
    with open(JSONLD_OUTPUT_PATH, "w") as f:
        json.dump(jsonld_data, f, indent=2, ensure_ascii=False)

    fieldnames, rows = transform_to_csv_rows(records)
    with open(CSV_OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    copy_to_latest()

    print(f"Transformed {len(records)} Who Does What links to JSON-LD and CSV")


if __name__ == "__main__":
    main()
