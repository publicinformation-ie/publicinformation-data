#!/usr/bin/env python3
"""_CONTINUATION_NULL_THRESHOLD sweep experiment.

Phase 1 — Diagnostic: classify each InsufficientColumns failure as null_header,
vocab_gap, or not_in_fixture. Outputs diagnostic.csv.

Phase 2 — Sweep: for each threshold in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
run normalize_header_row against the frozen eval fixture, simulate the
InsufficientColumns check, and compute improvements/regressions vs baseline (0.5).
Outputs sweep_results.json.

Run from the experiment directory:
    uv run python run.py
"""
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

import steps.extract_disclosures_normalize_header.process as _nh_process
from steps.extract_disclosures_normalize_header.process import normalize_header_row
from steps.extract_disclosures_canonicalize.column_map import canonicalize_headers

_FIXTURE = _FOI_PIPELINE / "steps/extract_disclosures_normalize_header/eval/input.json"
_NH_OUTPUT = _FOI_PIPELINE / "steps/extract_disclosures_normalize_header/output.json"
_CANON_ERRORS = _FOI_PIPELINE / "steps/extract_disclosures_canonicalize/errors.json"
_DIAGNOSTIC_CSV = _HERE / "diagnostic.csv"
_SWEEP_JSON = _HERE / "sweep_results.json"

_THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
_BASELINE_THRESHOLD = 0.5
_MAX_CONTINUATION_ROWS = 3


if __name__ == "__main__":
    print("Skeleton OK — functions not yet implemented")
