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

from eval import utils as eval_utils
from eval import judge as eval_judge
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


def run_eval(labels, records, errors, input_hash):
    """
    labels  — list of dicts from labels.csv (header mapping accuracy)
    records — list of canonical FOI record dicts from output.json
    errors  — list of error dicts from errors.json
    """
    acc, mapping_counts, mismatches = score_header_mapping(labels)
    cov = score_field_coverage(records)

    # --- file-level success / failure rates ---
    successful_urls = {r["file_url"] for r in records if "file_url" in r}
    insufficient_urls = {
        e["context"]["file_url"]
        for e in errors
        if e.get("error_type") == "InsufficientColumns"
        and "file_url" in e.get("context", {})
    }
    all_urls = successful_urls | insufficient_urls
    total_files = len(all_urls)
    successful_files = len(successful_urls)
    insufficient_files = len(insufficient_urls)
    success_rate = round(successful_files / total_files, 3) if total_files else 0.0
    insufficient_rate = round(insufficient_files / total_files, 3) if total_files else 0.0

    metrics = [
        eval_utils.Metric("header_mapping_accuracy", round(acc, 3),
                          mapping_counts, is_primary=True),
        eval_utils.Metric("field_coverage",
                          round(sum(cov.values()) / len(cov), 3) if cov else 0.0,
                          cov),
        eval_utils.Metric("file_success_rate", success_rate,
                          {"successful": successful_files, "total": total_files}),
        eval_utils.Metric("insufficient_columns_rate", insufficient_rate,
                          {"failed": insufficient_files, "total": total_files}),
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
    if insufficient_files:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{insufficient_files} files failed with InsufficientColumns ({insufficient_rate:.1%})",
            affected_count=insufficient_files,
            affected_ids=list(insufficient_urls)[:50],
            suggested_upstream_step="extract_disclosures_normalize_header",
            suggestion_detail="null header columns prevent canonical mapping",
            confidence=0.9))

    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash,
                                     judge_model=eval_judge.judge_model_id())
    return results, issues


def _load_labels(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    here = Path(__file__).parent
    step_dir = here.parent
    parser = argparse.ArgumentParser(description="Evaluate canonicalization")
    parser.add_argument("--labels", default=str(here / "labels.csv"))
    parser.add_argument("--input-path", dest="input_path",
                        default=str(step_dir / "output.json"))
    parser.add_argument("--errors-path", dest="errors_path",
                        default=str(step_dir / "errors.json"))
    args = parser.parse_args()

    labels = _load_labels(args.labels)
    records = json.loads(Path(args.input_path).read_text())["results"]
    errors = json.loads(Path(args.errors_path).read_text()) if Path(args.errors_path).exists() else []
    results, issues = run_eval(labels, records, errors,
                               eval_utils.input_hash(Path(args.labels)))
    eval_utils.write_eval_outputs(here, results, issues)
    p = results.metrics[0]
    s = next(m for m in results.metrics if m.name == "file_success_rate")
    print(f"{STEP}: header_mapping_accuracy={p.value:.3f} "
          f"({p.counts['correct']}/{p.counts['total']}), "
          f"file_success_rate={s.value:.3f} "
          f"({s.counts['successful']}/{s.counts['total']}), "
          f"{len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
