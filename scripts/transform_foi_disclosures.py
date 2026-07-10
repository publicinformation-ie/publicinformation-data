#!/usr/bin/env python3
"""Transform FOI pipeline disclosure data to JSON-LD and CSV for the
FOI Disclosures dataset.
Usage: python scripts/transform_foi_disclosures.py
"""
import json
import csv
import os

from scripts.lib.body_refs import BASE_URI, build_body_slug_lookup, body_uri

FOI_DISCLOSURES_PATH = "public/foi-disclosures.json"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
LATEST_DIR = "public/latest/foi-disclosures"
JSONLD_OUTPUT_PATH = f"{LATEST_DIR}/foi-disclosures.jsonld"
CSV_OUTPUT_PATH = f"{LATEST_DIR}/foi-disclosures.csv"
DATASET_VERSION = "1.0.0"

# Present (possibly null) on every disclosure record; None is omitted from
# JSON-LD, empty string in CSV.
NULLABLE_FIELDS = [
    "foi_reference_id",
    "decision_date",
    "date_received",
    "requester_type",
    "decision_status",
    "review_status",
    "related_request",
    "request_description",
]

CSV_FIELDNAMES = (
    ["id", "public_body", "name", "file_url", "file_type"]
    + NULLABLE_FIELDS
    + ["known_issues", "missing_columns"]
)


def load_slug_seed(path=SLUG_SEED_PATH):
    """Load slug_seed.json with integer keys, matching db_upload's own loading."""
    with open(path) as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


def build_record(disclosure, body_slug_lookup):
    """Build one FOI disclosure record.

    Raises for an unresolvable public_body_id rather than guessing or
    dropping the relationship silently — a broken public_body URI would
    be a fabricated link, worse than a loud failure.
    """
    body_id = disclosure["public_body_id"]
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(f"Unknown public_body_id in foi-disclosures.json: {body_id!r}")

    record = {
        "@id": f"{BASE_URI}/foi-disclosure/{disclosure['row_id']}",
        "@type": "foi:FoiDisclosure",
        "public_body": body_uri(slug),
        "name": disclosure["name"],
        "file_url": disclosure["file_url"],
        "file_type": disclosure["file_type"],
        "known_issues": disclosure.get("known_issues", []),
        "missing_columns": disclosure.get("missing_columns", []),
    }
    for field in NULLABLE_FIELDS:
        value = disclosure.get(field)
        if value is not None:
            record[field] = value
    return record


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document.

    Carries an explicit "version" field at the document root — unlike the
    other catalog datasets, foi-disclosures does not keep a permanent
    public/vX.Y.Z/ directory (see the dataset README's Versioning section),
    so this field is the only in-band record of which version's content
    public/latest/ currently holds.
    """
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "foi": f"{BASE_URI}/ns/foi#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "foi:publicBody", "@type": "@id"},
        },
        "version": DATASET_VERSION,
        "@graph": records,
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows.

    known_issues/missing_columns are array-valued in JSON-LD; CSV flattens
    each to a "|"-delimited string (documented in
    foi-disclosures.csv-metadata.json via a csvw:separator annotation).
    """
    rows = []
    for r in records:
        row = {
            "id": r["@id"],
            "public_body": r["public_body"],
            "name": r["name"],
            "file_url": r["file_url"],
            "file_type": r["file_type"],
            "known_issues": "|".join(r["known_issues"]),
            "missing_columns": "|".join(r["missing_columns"]),
        }
        for field in NULLABLE_FIELDS:
            row[field] = r.get(field, "")
        rows.append(row)
    return CSV_FIELDNAMES, rows


def main():
    os.makedirs(LATEST_DIR, exist_ok=True)

    with open(FOI_DISCLOSURES_PATH) as f:
        disclosures = json.load(f)
    with open(PIPELINE_DATA_PATH) as f:
        pipeline_bodies = json.load(f)["public_bodies"]
    slug_seed = load_slug_seed()

    body_slug_lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    records = [build_record(d, body_slug_lookup) for d in disclosures]

    jsonld_data = transform_to_jsonld(records)
    with open(JSONLD_OUTPUT_PATH, "w") as f:
        json.dump(jsonld_data, f, indent=2, ensure_ascii=False)

    fieldnames, rows = transform_to_csv_rows(records)
    with open(CSV_OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Transformed {len(records)} FOI disclosures to JSON-LD and CSV")


if __name__ == "__main__":
    main()
