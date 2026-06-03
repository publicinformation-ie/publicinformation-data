#!/usr/bin/env python3
"""Evaluate transform_disclosure_files: PDF extraction quality via heuristic flags.

Three binary flags per PDF record:
  null_first_row     — any cell in rows[0] is None
  null_column        — at least one column index where every row has None
  newline_split_row  — at least one non-header row with exactly 1 non-None cell
                       across >= 3 columns

Primary metric: clean_extraction_rate (fraction of PDFs with zero flags).
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

import eval_utils

STEP = "transform_disclosure_files"


def has_null_first_row(rows):
    """True if any cell in rows[0] is None."""
    if not rows:
        return False
    return any(c is None for c in rows[0])


def has_null_column(rows):
    """True if any column index is missing in some row or has None in every row."""
    if not rows:
        return False
    ncols = max(len(row) for row in rows)
    for col in range(ncols):
        if any(col >= len(row) for row in rows):  # missing in some row
            return True
        if all(row[col] is None for row in rows):  # all-None in complete columns
            return True
    return False


def has_newline_split_row(rows):
    """True if any non-header row has exactly 1 non-None cell across >= 3 columns."""
    for row in rows[1:]:
        if len(row) >= 3 and sum(1 for c in row if c is not None) == 1:
            return True
    return False
