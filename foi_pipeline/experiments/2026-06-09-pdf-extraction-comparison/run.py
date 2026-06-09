#!/usr/bin/env python3
"""PDF extractor comparison: pdfplumber vs camelot lattice vs camelot stream.

Run from repo root:
    cd foi_pipeline && uv run python experiments/2026-06-09-pdf-extraction-comparison/run.py
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.process import _DEFAULT_PDF_TABLE_SETTINGS, serialise_cell

_CACHE_DIR = _FOI_PIPELINE / "steps/transform_disclosure_files/cache"
_OUTPUT_JSON = _FOI_PIPELINE / "steps/transform_disclosure_files/output.json"
_LABELS_PATH = _HERE / "labels.jsonl"
_RESULTS_PATH = _HERE / "results.json"

_DATE_RE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")


# ---------------------------------------------------------------------------
# Scoring utilities
# ---------------------------------------------------------------------------

def apply_merge_groups(rows, merge_groups):
    """Apply merge_groups to rows, returning ground-truth rows.

    merge_groups is a list of index lists, e.g. [[0, 1], [3, 4, 5]].
    The first index in each group is the primary row; subsequent indices are
    continuation rows whose non-null cells are appended to the primary.
    Continuation rows are dropped from the output.
    """
    primary_to_conts = {}
    absorbed = set()
    for group in merge_groups:
        if len(group) < 2:
            continue
        primary_to_conts[group[0]] = group[1:]
        absorbed.update(group[1:])

    result = []
    for i, row in enumerate(rows):
        if i in absorbed:
            continue
        if i in primary_to_conts:
            merged = list(row)
            ncols = len(merged)
            for cont_idx in primary_to_conts[i]:
                if cont_idx >= len(rows):
                    continue
                for col_idx, cell in enumerate(rows[cont_idx]):
                    if cell is not None and col_idx < ncols:
                        if merged[col_idx] is not None:
                            merged[col_idx] = str(merged[col_idx]) + " " + str(cell)
                        else:
                            merged[col_idx] = str(cell)
            result.append(merged)
        else:
            result.append(list(row))
    return result


def row_to_text(row):
    """Concatenate non-null cells, whitespace-normalised."""
    parts = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def score_extractor(ground_truth, extracted):
    """Score an extractor's output against ground truth rows.

    Returns dict with row_count_match (bool), exact_row_match (bool),
    expected_rows (int), actual_rows (int), exact_matches (int).
    """
    extracted_texts = {row_to_text(r) for r in extracted}
    exact_matches = sum(
        1 for expected in ground_truth if row_to_text(expected) in extracted_texts
    )
    return {
        "row_count_match": len(extracted) == len(ground_truth),
        "exact_row_match": exact_matches == len(ground_truth),
        "expected_rows": len(ground_truth),
        "actual_rows": len(extracted),
        "exact_matches": exact_matches,
    }


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_with_pdfplumber(file_bytes):
    """Extract rows using pdfplumber with pipeline's default settings."""
    import pdfplumber
    rows = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables(table_settings=_DEFAULT_PDF_TABLE_SETTINGS):
                for row in table:
                    rows.append([serialise_cell(cell)[0] for cell in row])
    return rows


def extract_with_camelot(file_bytes, flavor):
    """Extract rows using camelot. Returns None if camelot is unavailable or fails."""
    try:
        import camelot
    except ImportError:
        print(f"WARNING: camelot not installed (brew install ghostscript && uv add camelot-py[cv])",
              file=sys.stderr)
        return None

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(file_bytes)
        tmp_path = f.name

    try:
        tables = camelot.read_pdf(tmp_path, flavor=flavor, pages="all")
        rows = []
        for table in tables:
            for _, row in table.df.iterrows():
                rows.append([cell if cell != "" else None for cell in row.tolist()])
        return rows
    except Exception as e:
        print(f"WARNING: camelot {flavor} failed: {e}", file=sys.stderr)
        return None
    finally:
        os.unlink(tmp_path)
