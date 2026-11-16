#!/usr/bin/env python3
"""Publish the Active Travel allocations dataset from activetravel_pipeline.

Reads pipelines/activetravel_pipeline/steps/export_allocations/output.json (the
flat, reconciled source of every published allocation record) and writes
JSON-LD + CSV to public/v1.0.0/active-travel-allocations/ (with the committed
CSVW metadata and README alongside), mirroring the directory to
public/latest/active-travel-allocations/ only when the payload content actually
changes.

Every local-authority record's public_body URI is re-resolved through the same
permanent slug machinery as the public-bodies dataset (body_refs +
slug_seed.json) and compared with what the pipeline exported: a URI that does
not match aborts publication rather than publishing an invented body link.
Usage: uv run python scripts/transform_active_travel_allocations.py
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.active_travel_splits import build_splits, write_splits
from src.lib.body_refs import BASE_URI, build_body_slug_lookup, body_uri
from src.lib.dataset_publish import render_csv, render_jsonld, stamp_if_changed

EXPORT_ALLOCATIONS_PATH = "pipelines/activetravel_pipeline/steps/export_allocations/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v1.0.0/active-travel-allocations"
LATEST_DIR = "public/latest/active-travel-allocations"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/active-travel-allocations.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/active-travel-allocations.csv"
TTL_PATH = "public/catalog/dataset-active-travel-allocations.ttl"

CSV_FIELDNAMES = [
    "id", "year", "public_body", "public_body_id", "recipient_name",
    "funding_stream", "project_code", "project_code_provisional",
    "project_name", "allocation_eur", "source_document_url",
    "source_document_sha256", "source_page",
]

# The published record fields, in publication order. @id is published as `id`
# in CSV; public_body/public_body_id are absent for a non-local-authority
# recipient.
RECORD_FIELDS = [
    "year", "public_body", "public_body_id", "recipient_name", "funding_stream",
    "project_code", "project_code_provisional", "project_name", "allocation_eur",
    "source_document_url", "source_document_sha256", "source_page",
]


def build_record(allocation: dict, body_slug_lookup: dict[int, str]) -> dict:
    """Build one published allocation, checking the body link against the
    permanent slug machinery rather than trusting the pipeline's own copy."""
    record = {
        "@id": allocation["@id"],
        "@type": "Allocation",
        "year": allocation["year"],
        "recipient_name": allocation["recipient_name"],
        "funding_stream": allocation["funding_stream"],
        "project_code": allocation["project_code"],
        "project_code_provisional": allocation["project_code_provisional"],
        "project_name": allocation["project_name"],
        "allocation_eur": allocation["allocation_eur"],
        "source_document_url": allocation["source_document_url"],
        "source_document_sha256": allocation["source_document_sha256"],
        "source_page": allocation["source_page"],
    }
    body_id = allocation.get("public_body_id")
    if body_id is None:
        if allocation.get("public_body") is not None:
            raise ValueError(
                f"{allocation['@id']}: public_body is set without a public_body_id")
        return record
    try:
        slug = body_slug_lookup[body_id]
    except KeyError:
        raise ValueError(
            f"Unknown public_body_id in export_allocations output: {body_id!r}"
        ) from None
    expected = body_uri(slug)
    if allocation.get("public_body") != expected:
        raise ValueError(
            f"{allocation['@id']}: exported public_body "
            f"{allocation.get('public_body')!r} does not match the permanent slug "
            f"URI {expected!r}"
        )
    record["public_body"] = expected
    record["public_body_id"] = body_id
    return record


def transform_to_jsonld(records: list[dict]) -> dict:
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "ata": f"{BASE_URI}/ns/active-travel#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "ata:publicBody", "@type": "@id"},
            "funding_stream": {"@id": "ata:fundingStream"},
            "allocation_eur": {"@id": "ata:allocationEur"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records: list[dict]) -> tuple[list[str], list[dict]]:
    rows = []
    for record in records:
        row = {}
        for field in RECORD_FIELDS:
            value = record.get(field, "")
            # CSVW declares this column as `boolean`, whose lexical space is
            # lowercase; str(True) would not parse as one.
            if isinstance(value, bool):
                value = "true" if value else "false"
            row[field] = value
        row["id"] = record["@id"]
        rows.append(row)
    return CSV_FIELDNAMES, rows


def mirror_to_latest() -> bool:
    """Mirror the versioned directory to latest/, writing only differing files.

    Not a symlink: static hosts and various git checkout paths do not reliably
    serve or preserve symlinks. An unchanged run therefore writes nothing.
    """
    latest = Path(LATEST_DIR)
    latest.mkdir(parents=True, exist_ok=True)
    written = False
    for source in sorted(Path(OUTPUT_DIR).iterdir()):
        data = source.read_bytes()
        target = latest / source.name
        if target.exists() and target.read_bytes() == data:
            continue
        target.write_bytes(data)
        written = True
    return written


def publish(jsonld_data, fieldnames, rows,
            jsonld_path=Path(JSONLD_OUTPUT_PATH), csv_path=Path(CSV_OUTPUT_PATH),
            ttl_path=Path(TTL_PATH)) -> bool:
    generated = {
        jsonld_path: render_jsonld(jsonld_data),
        csv_path: render_csv(fieldnames, rows),
    }
    return stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)


def load_inputs():
    with open(EXPORT_ALLOCATIONS_PATH) as f:
        allocations = json.load(f)["results"]
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        public_bodies = json.load(f)["public_bodies"]
    with open(SLUG_SEED_PATH) as f:
        slug_seed = {int(k): v for k, v in json.load(f).items()}
    return allocations, build_body_slug_lookup(public_bodies, slug_seed)


def main():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    allocations, body_slug_lookup = load_inputs()
    records = [build_record(a, body_slug_lookup) for a in allocations]

    jsonld_data = transform_to_jsonld(records)
    fieldnames, rows = transform_to_csv_rows(records)
    changed = publish(jsonld_data, fieldnames, rows)
    mirrored = mirror_to_latest()
    split_files = build_splits(records)
    if write_splits(split_files, Path(LATEST_DIR)):
        print(f"Wrote {len(split_files)} spreadsheet-friendly split files "
              "(by-recipient/, by-year/) under public/latest/")
    if changed:
        print(f"Transformed {len(records)} allocations to JSON-LD and CSV "
              "(content changed, dct:modified updated)")
    else:
        print(f"Transformed {len(records)} allocations to JSON-LD and CSV "
              "(no content change, dct:modified untouched)")
    if mirrored:
        print("Mirrored the versioned directory to public/latest/")


if __name__ == "__main__":
    main()
