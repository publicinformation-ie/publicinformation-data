#!/usr/bin/env python3
"""Transform FOI pipeline disclosure data to JSON-LD and CSV for the
FOI Disclosures dataset.
Usage: python scripts/transform_foi_disclosures.py
"""
import json
import hashlib
from pathlib import Path

from src.lib.body_refs import BASE_URI, build_body_slug_lookup, body_uri
from src.lib.dataset_publish import render_csv, render_jsonld, write_xlsx

BODIES_DIR = "public/latest/foi-disclosures/bodies"
PIPELINE_DATA_PATH = "public/pipeline-data.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
LATEST_DIR = "public/latest/foi-disclosures"
JSONLD_OUTPUT_PATH = f"{LATEST_DIR}/foi-disclosures.jsonld"
CSV_OUTPUT_PATH = f"{LATEST_DIR}/foi-disclosures.csv"
XLSX_OUTPUT_PATH = f"{LATEST_DIR}/foi-disclosures.xlsx"
DATASET_VERSION = "1.0.0"
TTL_PATH = "public/catalog/dataset-foi-disclosures.ttl"

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


def compute_disclosure_id(row_id):
    """Published id derived from the row's stable `row_id`.

    `row_id` is itself a hash of (file_url, original_row_index), so the id does
    not depend on the order rows are stored or built in.
    """
    return hashlib.sha1(row_id.encode("utf-8")).hexdigest()[:12]


def known_issue_fields(issues):
    """Reduce pipeline known_issues to the published contract: an ordered,
    de-duplicated array of the field names flagged as uncertain.

    The pipeline emits {field, issue_type, raw_value} dicts; plain strings
    pass through. Anything else fails loudly rather than being guessed at.
    """
    out = []
    for issue in issues:
        if isinstance(issue, str):
            name = issue
        elif isinstance(issue, dict) and isinstance(issue.get("field"), str):
            name = issue["field"]
        else:
            raise ValueError(f"Unrecognised known_issues entry: {issue!r}")
        if name not in out:
            out.append(name)
    return out


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
        raise ValueError(f"Unknown public_body_id in FOI disclosures: {body_id!r}")

    disclosure_id = compute_disclosure_id(disclosure["row_id"])
    record = {
        "@id": f"{BASE_URI}/foi-disclosure/{disclosure_id}",
        "@type": "foi:FoiDisclosure",
        "public_body": body_uri(slug),
        "name": disclosure["name"],
        "file_url": disclosure["file_url"],
        "file_type": disclosure["file_type"],
        "known_issues": known_issue_fields(disclosure.get("known_issues", [])),
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


def build_forms(disclosures, pipeline_bodies, slug_seed):
    """Disclosure rows -> (jsonld document, csv fieldnames, csv rows)."""
    body_slug_lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    records = [build_record(d, body_slug_lookup) for d in disclosures]
    fieldnames, rows = transform_to_csv_rows(records)
    return transform_to_jsonld(records), fieldnames, rows


def publish(
    jsonld_data, fieldnames, rows,
    jsonld_path=Path(JSONLD_OUTPUT_PATH), csv_path=Path(CSV_OUTPUT_PATH), xlsx_path=Path(XLSX_OUTPUT_PATH),
):
    """Write the JSON-LD, CSV and XLSX forms. Never touches the catalog .ttl:
    dct:modified follows the stored per-body files and is stamped by export_status."""
    for path in (jsonld_path, csv_path, xlsx_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))
    write_xlsx(xlsx_path, fieldnames, rows)


def main():
    from scripts.build_foi_combined import build

    summary = build(Path("."))
    print(f"Built {summary['total_rows']} FOI disclosures (JSON, JSON-LD, CSV, XLSX, manifest)")


if __name__ == "__main__":
    main()
