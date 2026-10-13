#!/usr/bin/env python3
"""Publish the Transport Policies dataset: one row per policy in
pipelines/document_pipeline/input_plans_transport.md, joined to the PDFs
curated for it in documents.yml.

`has_document` / `doc_slugs` are derived from documents.yml (a curated entry
is a verified PDF), never from the markdown. Multi-valued cells (`source_urls`,
`doc_slugs`) are `|`-separated; the CSVW descriptor declares the separator.

Usage: uv run python scripts/transform_transport_policies.py
"""
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT, REPO_ROOT / "src", REPO_ROOT / "pipelines" / "document_pipeline"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from documents import load_documents
from policies import load_policies
from src.lib.dataset_publish import render_csv, stamp_if_changed

OUTPUT_DIR = "public/v1.0.0/transport-policies"
LATEST_DIR = "public/latest/transport-policies"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/transport-policies.csv"
TTL_PATH = "public/catalog/dataset-transport-policies.ttl"

FIELDNAMES = ["policy_id", "title", "kind", "issuing_authority", "horizon", "scope",
              "linkages", "source_urls", "has_document", "doc_slugs"]
MULTI_SEP = "|"


def build_rows(policies, documents):
    """One CSV row (all-string values) per policy, in inventory order.

    Raises for a document whose policy_id is not in the inventory — the loader
    already guarantees this, so reaching here means the two inputs drifted.
    """
    slugs_by_policy = {}
    for doc in documents:
        slugs_by_policy.setdefault(doc["policy_id"], []).append(doc["doc_slug"])

    unknown = sorted(set(slugs_by_policy) - {p["policy_id"] for p in policies})
    if unknown:
        raise ValueError(f"documents reference policy_id(s) not in the inventory: {unknown}")

    rows = []
    for policy in policies:
        doc_slugs = slugs_by_policy.get(policy["policy_id"], [])
        rows.append({
            "policy_id": policy["policy_id"],
            "title": policy["title"],
            "kind": policy["kind"],
            "issuing_authority": policy["issuing_authority"],
            "horizon": policy["horizon"],
            "scope": policy["scope"],
            "linkages": policy["linkages"],
            "source_urls": MULTI_SEP.join(policy["source_urls"]),
            "has_document": "true" if doc_slugs else "false",
            "doc_slugs": MULTI_SEP.join(doc_slugs),
        })
    return rows


def copy_to_latest():
    """Copy the versioned directory (CSV, CSVW, README) to latest/ as a
    build-time snapshot — not a symlink, same as the other datasets."""
    shutil.copytree(OUTPUT_DIR, LATEST_DIR, dirs_exist_ok=True)


def publish(rows, csv_path=Path(CSV_OUTPUT_PATH), ttl_path=Path(TTL_PATH)):
    """Write the CSV and stamp dct:modified only if content changed."""
    csv_path = Path(csv_path)
    generated = {csv_path: render_csv(FIELDNAMES, rows)}
    return stamp_if_changed(Path(ttl_path), [csv_path], generated)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    rows = build_rows(load_policies(), load_documents())
    if publish(rows):
        copy_to_latest()
        print(f"Published {len(rows)} transport policies (content changed, dct:modified updated)")
    else:
        print(f"Published {len(rows)} transport policies (no content change, dct:modified untouched)")


if __name__ == "__main__":
    main()
