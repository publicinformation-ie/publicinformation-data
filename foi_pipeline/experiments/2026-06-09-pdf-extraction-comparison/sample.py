#!/usr/bin/env python3
"""Generate stratified sample → pending_labels.jsonl.

Tier 1 (5 files): confirmed multi-line row problem files (Meath, Galway).
Tier 2 (15 files): random from high-error-rate bodies (Justice, Housing, etc.)
Tier 3 (10 files): random from remaining PDFs.

Run from repo root:
    cd foi_pipeline && uv run python experiments/2026-06-09-pdf-extraction-comparison/sample.py
"""
import hashlib
import io
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.process import _DEFAULT_PDF_TABLE_SETTINGS, serialise_cell

_CACHE_DIR = _FOI_PIPELINE / "steps/transform_disclosure_files/cache"
_OUTPUT_JSON = _FOI_PIPELINE / "steps/transform_disclosure_files/output.json"
_PENDING_LABELS = _HERE / "pending_labels.jsonl"

# Confirmed multi-line row problem files (manually verified)
_TIER1_URLS = [
    "https://www.meath.ie/system/files/media/file-uploads/2019-05/FOI%20Disclosure%20Log%202016.pdf",
    "https://www.meath.ie/system/files/media/file-uploads/2019-05/FOI%20Disclosure%20Log%202017.pdf",
    "https://www.meath.ie/system/files/media/file-uploads/2019-05/FOI%20Disclosure%20Log%202018%20%28Jan%20to%20Jun%29.pdf",
    "http://www.galway.ie/sites/default/files/2025-06/FOI%20Disclosure%20log%202016.pdf",
    "http://www.galway.ie/sites/default/files/2025-06/FOI%20Disclosure%20log%202017.pdf",
]

# Bodies with most StatusValueIsDate + StatusValueIsColumnHeader errors
_TIER2_BODY_IDS = {1013, 1012, 1017, 1039, 1016, 1084}

_TIER2_N = 15
_TIER3_N = 10
_MAX_ROWS_TO_SHOW = 200  # cap per file to keep pending_labels.jsonl readable
_SEED = 42


def _cache_path(url):
    return _CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()}.bytes"


def _is_cached(url):
    return _cache_path(url).exists()


def _extract_rows(url):
    import pdfplumber
    file_bytes = _cache_path(url).read_bytes()
    rows = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables(table_settings=_DEFAULT_PDF_TABLE_SETTINGS):
                for row in table:
                    rows.append([serialise_cell(cell)[0] for cell in row])
    return rows[:_MAX_ROWS_TO_SHOW]


def main():
    random.seed(_SEED)

    data = json.loads(_OUTPUT_JSON.read_text())
    all_pdfs = {r["file_url"]: r for r in data.get("results", []) if r.get("file_type") == "pdf"}

    # --- Tier 1 ---
    tier1 = []
    for url in _TIER1_URLS:
        if url not in all_pdfs:
            print(f"WARNING: tier 1 URL not found in output: {url}", file=sys.stderr)
            continue
        if not _is_cached(url):
            print(f"WARNING: tier 1 URL not cached: {url}", file=sys.stderr)
            continue
        tier1.append(all_pdfs[url])

    tier1_urls = {r["file_url"] for r in tier1}

    # --- Tier 2 ---
    tier2_pool = [
        r for url, r in all_pdfs.items()
        if r["public_body_id"] in _TIER2_BODY_IDS
        and url not in tier1_urls
        and _is_cached(url)
    ]
    tier2 = random.sample(tier2_pool, min(_TIER2_N, len(tier2_pool)))
    tier2_urls = {r["file_url"] for r in tier2}

    # --- Tier 3 ---
    tier3_pool = [
        r for url, r in all_pdfs.items()
        if url not in tier1_urls
        and url not in tier2_urls
        and _is_cached(url)
    ]
    tier3 = random.sample(tier3_pool, min(_TIER3_N, len(tier3_pool)))

    total = len(tier1) + len(tier2) + len(tier3)
    print(f"Sample: {len(tier1)} tier1 + {len(tier2)} tier2 + {len(tier3)} tier3 = {total} files")

    with _PENDING_LABELS.open("w") as f:
        for tier_num, items in [(1, tier1), (2, tier2), (3, tier3)]:
            for item in items:
                rows = _extract_rows(item["file_url"])
                entry = {
                    "file_url": item["file_url"],
                    "public_body_id": item["public_body_id"],
                    "name": item.get("name", ""),
                    "tier": tier_num,
                    "rows": [{"idx": i, "cells": row} for i, row in enumerate(rows)],
                    "merge_groups": [],
                }
                f.write(json.dumps(entry) + "\n")
                print(f"  [{tier_num}] {item.get('name', '')[:40]}: {len(rows)} rows shown")

    print(f"\nWrote {_PENDING_LABELS}")
    print("\nNext steps:")
    print("  1. Open pending_labels.jsonl and fill in 'merge_groups' for each file")
    print("  2. cp pending_labels.jsonl labels.jsonl")
    print("  3. uv run python run.py")


if __name__ == "__main__":
    main()
