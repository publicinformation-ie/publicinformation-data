#!/usr/bin/env python3
"""Evaluate extract_disclosures_canonicalize_rows: status normalization accuracy.

Primary metric: canonicalization rate (fraction of decision_status values
successfully mapped to one of the 7 canonical statuses).

Secondary metrics:
- Distribution of canonical statuses in output
- Count of unrecognized status values (with top offenders)
- Error rate per public body

Input: ../output.json (step's live output) and ../errors.json
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).parent
_STEP_DIR = _HERE.parent
sys.path.insert(0, str(_HERE.parents[2]))  # steps/.../eval -> foi_pipeline

from eval import utils as eval_utils
from steps.extract_disclosures_canonicalize_rows.status_map import (
    CANONICAL_STATUSES,
)

STEP = "extract_disclosures_canonicalize_rows"


def run_eval(records, errors, input_hash):
    """
    records — list of canonical FOI record dicts from output.json
    errors  — list of error dicts from errors.json
    """
    total_records = len(records) or 1
    
    # Count canonical status distribution
    canonical_counts = {s: 0 for s in CANONICAL_STATUSES}
    non_canonical_count = 0
    non_canonical_statuses = Counter()
    
    for record in records:
        status = record.get("decision_status")
        if status in canonical_counts:
            canonical_counts[status] += 1
        elif status:
            non_canonical_count += 1
            non_canonical_statuses[status] += 1
    
    # Calculate canonicalization rate
    canonical_total = sum(canonical_counts.values())
    canonical_rate = round(canonical_total / total_records, 3)
    
    # Error analysis
    unrecognized_errors = [
        e for e in errors 
        if e.get("error_type") == "UnrecognizedDecisionStatus"
    ]
    unrecognized_count = len(unrecognized_errors)
    
    # Extract raw status values from unrecognized errors
    raw_status_counter = Counter()
    for error in unrecognized_errors:
        raw_status = error.get("context", {}).get("raw_status")
        if raw_status:
            raw_status_counter[raw_status] += 1
    
    # Top 10 most frequent unrecognized statuses
    top_unrecognized = raw_status_counter.most_common(10)
    
    # Build metrics
    metrics = [
        eval_utils.Metric(
            "canonicalization_rate",
            canonical_rate,
            {
                "canonical": canonical_total,
                "total": total_records,
                **{s: canonical_counts[s] for s in CANONICAL_STATUSES},
            },
            is_primary=True,
        ),
        eval_utils.Metric(
            "unrecognized_status_rate",
            round(unrecognized_count / total_records, 3) if total_records else 0.0,
            {
                "unrecognized": unrecognized_count,
                "total": total_records,
            },
        ),
        eval_utils.Metric(
            "non_canonical_passthrough_rate",
            round(non_canonical_count / total_records, 3) if total_records else 0.0,
            {
                "non_canonical": non_canonical_count,
                "total": total_records,
            },
        ),
    ]
    
    # Build issues
    issues = []
    
    # Issue: Unrecognized statuses
    if unrecognized_count > 0:
        top_statuses_str = ", ".join(f"'{s}' ({c})" for s, c in top_unrecognized[:5])
        all_unrecognized = list(raw_status_counter.keys())
        issues.append(eval_utils.Issue(
            severity="warning" if unrecognized_count < total_records * 0.1 else "error",
            description=f"{unrecognized_count} records have unrecognized decision_status values",
            affected_count=unrecognized_count,
            affected_ids=all_unrecognized[:50],
            suggested_upstream_step=STEP,
            suggestion_detail=f"Add mappings for top unrecognized: {top_statuses_str}",
            confidence=0.9,
        ))
    
    # Issue: Non-canonical passthrough (statuses that aren't canonical but weren't errored)
    if non_canonical_count > 0:
        top_non_canonical = non_canonical_statuses.most_common(5)
        top_str = ", ".join(f"'{s}' ({c})" for s, c in top_non_canonical)
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"{non_canonical_count} records have non-canonical but recognized statuses (passthrough)",
            affected_count=non_canonical_count,
            affected_ids=list(non_canonical_statuses.keys())[:50],
            suggested_upstream_step=STEP,
            suggestion_detail=f"Consider adding to canonical mapping: {top_str}",
            confidence=0.7,
        ))
    
    results = eval_utils.EvalResults(
        step=STEP,
        metrics=metrics,
        input_hash=input_hash,
        judge_model=None,
    )
    return results, issues


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate decision_status canonicalization"
    )
    parser.add_argument(
        "--input-path", dest="input_path",
        default=str(_STEP_DIR / "output.json"),
        help="Normalized output to evaluate (default: ../output.json)",
    )
    parser.add_argument(
        "--errors-path", dest="errors_path",
        default=str(_STEP_DIR / "errors.json"),
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    errors_path = Path(args.errors_path)

    data = json.loads(input_path.read_text())
    records = data.get("results", [])
    errors = json.loads(errors_path.read_text()) if errors_path.exists() else []

    results, issues = run_eval(records, errors, eval_utils.input_hash(input_path))
    eval_utils.write_eval_outputs(_HERE, results, issues)

    primary = results.metrics[0]
    unrec = next((m for m in results.metrics if m.name == "unrecognized_status_rate"), None)
    
    print(
        f"{STEP}: canonicalization_rate={primary.value:.3f} "
        f"({primary.counts['canonical']}/{primary.counts['total']}), "
        f"unrecognized_rate={unrec.value:.3f} "
        f"({unrec.counts['unrecognized']}/{unrec.counts['total']}) "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
