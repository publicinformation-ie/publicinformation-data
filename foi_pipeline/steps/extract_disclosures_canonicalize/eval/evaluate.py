#!/usr/bin/env python3
"""Evaluate canonicalization: header-mapping accuracy (primary, LLM-judged
labels) + record field coverage (label-free).

Header mapping re-runs the real canonicalize_header() so the score reflects
column_map.py changes. Coverage reads the live canonical output.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

import eval_utils
import eval_judge
from steps.extract_disclosures_canonicalize.column_map import canonicalize_header

STEP = "extract_disclosures_canonicalize"
COVERAGE_FIELDS = ["decision_date", "decision_status", "foi_reference_id", "request_description"]


def _norm_field(value):
    """Map a canonical field name or None to the label vocabulary."""
    return value if value else "__none__"


def score_header_mapping(labels):
    correct = total = 0
    mismatches = []
    for row in labels:
        if row.get("verified") != "yes":
            continue
        total += 1
        expected = row["expected_canonical_field"] or "__none__"
        actual = _norm_field(canonicalize_header(row["raw_header"]))
        if actual == expected:
            correct += 1
        else:
            mismatches.append((row["raw_header"], expected, actual))
    acc = correct / total if total else 0.0
    return acc, {"correct": correct, "total": total}, mismatches


def score_field_coverage(records):
    n = len(records) or 1
    cov = {}
    for field in COVERAGE_FIELDS:
        populated = sum(1 for r in records if r.get(field) not in (None, ""))
        cov[field] = round(populated / n, 3)
    return cov


def run_eval(labels, records, input_hash):
    acc, mapping_counts, mismatches = score_header_mapping(labels)
    cov = score_field_coverage(records)

    metrics = [
        eval_utils.Metric("header_mapping_accuracy", round(acc, 3),
                          mapping_counts, is_primary=True),
        eval_utils.Metric("field_coverage",
                          round(sum(cov.values()) / len(cov), 3) if cov else 0.0,
                          cov),
    ]

    issues = []
    unmapped = [h for h, exp, act in mismatches if act == "__none__" and exp != "__none__"]
    if unmapped:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{len(unmapped)} verified headers map to nothing",
            affected_count=len(unmapped), affected_ids=unmapped[:50],
            suggested_upstream_step=None,
            suggestion_detail="consider adding to column_map.py", confidence=0.8))
    low_cov = [f for f, v in cov.items() if v < 0.5]
    if low_cov:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"Low population for fields: {', '.join(low_cov)}",
            affected_count=len(low_cov), affected_ids=low_cov,
            suggested_upstream_step="extract_disclosures_detect_header_row",
            suggestion_detail="possible wrong header row detected upstream",
            confidence=0.6))

    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash,
                                     judge_model=eval_judge.judge_model_id())
    return results, issues


def _load_labels(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    here = Path(__file__).parent
    step_out = here.parent / "output.json"
    parser = argparse.ArgumentParser(description="Evaluate canonicalization")
    parser.add_argument("--labels", default=str(here / "labels.csv"))
    parser.add_argument("--input-path", dest="input_path", default=str(step_out))
    args = parser.parse_args()

    labels = _load_labels(args.labels)
    records = json.loads(Path(args.input_path).read_text())["results"]
    results, issues = run_eval(labels, records,
                               eval_utils.input_hash(Path(args.labels)))
    eval_utils.write_eval_outputs(here, results, issues)
    p = results.metrics[0]
    print(f"{STEP}: header_mapping_accuracy={p.value:.3f} "
          f"({p.counts['correct']}/{p.counts['total']}), {len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
