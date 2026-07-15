#!/usr/bin/env python3
"""Scoring + aggregation for the llm-structuring-repair experiment.

Reads arms.json (Task 4) + ground_truth.json and writes results.json:
structural repair/regression, per-field fidelity, value-fidelity violations,
invented/dropped rows, and aggregated + extrapolated cost.

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-llm-structuring-repair/compare.py
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
if str(_FOI_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.eval.evaluate import (  # noqa: E402
    has_null_first_row,
    has_null_column,
    has_newline_split_row,
)

_ARMS = _HERE / "arms.json"
_GROUND_TRUTH = _HERE / "ground_truth.json"
_RESULTS = _HERE / "results.json"

FULL_TAIL_FILES = 323
PRICE_INPUT_PER_1M_USD = 0.5
PRICE_OUTPUT_PER_1M_USD = 1.5


def _load_schema():
    path = _HERE / "schema.py"
    spec = importlib.util.spec_from_file_location("llm_repair_schema", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_schema = _load_schema()
entries_to_rows = _schema.entries_to_rows
CANONICAL_FIELDS = _schema.CANONICAL_FIELDS

_PREDICATES = {
    "null_first_row": has_null_first_row,
    "null_column": has_null_column,
    "newline_split_row": has_newline_split_row,
}


def flags_for_rows(rows) -> set:
    if not rows:
        return set()
    return {name for name, fn in _PREDICATES.items() if fn(rows)}


def repair_stats(records: list) -> dict:
    broken = 0
    repaired = 0
    regressions = []
    per_pred = {name: {"broken": 0, "repaired": 0} for name in _PREDICATES}

    for rec in records:
        a_flags = flags_for_rows(rec.get("arm_a_rows"))
        b_entries = rec.get("arm_b_entries")
        is_failure = b_entries is None
        b_rows = entries_to_rows(b_entries or [])
        b_flags = flags_for_rows(b_rows)

        if a_flags:
            broken += 1
            for name in a_flags:
                per_pred[name]["broken"] += 1
            if not is_failure and not (a_flags & b_flags):  # none of A's predicates persist
                repaired += 1
                for name in a_flags:
                    per_pred[name]["repaired"] += 1

        if not is_failure and (b_flags - a_flags):  # arm B trips something arm A did not
            regressions.append(rec["file_url"])

    return {
        "broken": broken,
        "repaired": repaired,
        "repair_rate": round(repaired / broken, 3) if broken else 0.0,
        "regressions": regressions,
        "per_predicate": per_pred,
    }
