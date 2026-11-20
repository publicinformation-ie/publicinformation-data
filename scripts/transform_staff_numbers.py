#!/usr/bin/env python3
"""Publish the staff-numbers dataset from staffnumbers_pipeline.

Reads pipelines/staffnumbers_pipeline/steps/apply_overrides/output.json and
writes JSON-LD + CSV to public/v1.0.0/staff-numbers/, mirroring to
public/latest/staff-numbers/ only when the content changed.

One record per source row of the Department of Public Expenditure's public
service numbers file, for its most recent quarter. Rows that could not be tied
to a canonical public body are kept with `public_body` empty and
`match_status` "unmatched" so no headcount is silently dropped; the pipeline's
errors.json lists the ones nobody has reviewed yet.
Usage: uv run python scripts/transform_staff_numbers.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.lib.body_refs import BASE_URI, body_uri, build_body_slug_lookup, slugify
from src.lib.dataset_publish import render_csv, render_jsonld, stamp_if_changed

APPLY_OVERRIDES_OUTPUT_PATH = "pipelines/staffnumbers_pipeline/steps/apply_overrides/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
OUTPUT_DIR = "public/v1.0.0/staff-numbers"
LATEST_DIR = "public/latest/staff-numbers"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/staff-numbers.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/staff-numbers.csv"
TTL_PATH = "public/catalog/dataset-staff-numbers.ttl"
MATCH_STATUSES = {"exact", "rule", "override", "unmatched"}
CSV_FIELDS = ["id", "public_body", "match_status", "year", "quarter", "source_name",
              "source_department", "source_category", "source_key", "fte"]


def load_slug_seed(path=SLUG_SEED_PATH):
    with open(path) as f:
        return {int(k): v for k, v in json.load(f).items()}


def build_record(rec, body_slug_lookup):
    """Build one record. Raises rather than guessing: an unknown body id, an
    unknown status, or a status that contradicts the body link aborts."""
    status = rec["match_status"]
    if status not in MATCH_STATUSES:
        raise ValueError(f"Unknown match_status {status!r} for {rec['source_key']!r}")
    body_id = rec["public_body_id"]
    if (body_id is None) != (status == "unmatched"):
        raise ValueError(f"match_status {status!r} contradicts public_body_id {body_id!r} "
                         f"for {rec['source_key']!r}")
    public_body = None
    if body_id is not None:
        try:
            public_body = body_uri(body_slug_lookup[body_id])
        except KeyError:
            raise ValueError(f"Unknown public_body_id in apply_overrides output: {body_id!r}")
    period = f"{rec['year']}-q{rec['quarter']}"
    return {
        "@id": f"{BASE_URI}/staff-numbers/{period}/{slugify(rec['source_key'].replace('|', ' '))}",
        "@type": "sn:StaffNumbersRecord",
        "public_body": public_body,
        "match_status": status,
        "year": rec["year"],
        "quarter": rec["quarter"],
        "source_name": rec["source_name"],
        "source_department": rec["level_2"],
        "source_category": rec["level_4"],
        "source_key": rec["source_key"],
        "fte": rec["fte"],
    }


def build_records(source_records, body_slug_lookup):
    records = [build_record(r, body_slug_lookup) for r in source_records]
    seen = set()
    for r in records:
        if r["@id"] in seen:
            raise ValueError(f"Duplicate @id {r['@id']!r}")
        seen.add(r["@id"])
    return sorted(records, key=lambda r: r["@id"])


def transform_to_jsonld(records):
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "sn": f"{BASE_URI}/ns/sn#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "sn:publicBody", "@type": "@id"},
        },
        "@graph": records,
    }


def transform_to_csv_rows(records):
    rows = [{"id": r["@id"], **{k: ("" if r[k] is None else r[k]) for k in CSV_FIELDS[1:]}}
            for r in records]
    return CSV_FIELDS, rows


def copy_to_latest():
    shutil.copytree(OUTPUT_DIR, LATEST_DIR, dirs_exist_ok=True)


def publish(jsonld_data, fieldnames, rows,
            jsonld_path=Path(JSONLD_OUTPUT_PATH), csv_path=Path(CSV_OUTPUT_PATH), ttl_path=Path(TTL_PATH)):
    generated = {jsonld_path: render_jsonld(jsonld_data), csv_path: render_csv(fieldnames, rows)}
    return stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(APPLY_OVERRIDES_OUTPUT_PATH) as f:
        source_records = json.load(f)["results"]
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        public_bodies = json.load(f)["public_bodies"]
    lookup = build_body_slug_lookup(public_bodies, load_slug_seed())
    records = build_records(source_records, lookup)
    changed = publish(transform_to_jsonld(records), *transform_to_csv_rows(records))
    matched = sum(1 for r in records if r["public_body"])
    note = "content changed, dct:modified updated" if changed else "no content change, dct:modified untouched"
    if changed:
        copy_to_latest()
    print(f"Published {len(records)} staff-number records ({matched} linked to a public body; {note})")


if __name__ == "__main__":
    main()
