#!/usr/bin/env python3
"""Evaluate filter_phantom_rows: did row-structure repair actually clean the rows?

Primary metric: post_filter_clean_rate — fraction of PDF files whose output has
no leaked split rows (single-non-None-cell rows across >=3 columns) and no
remaining blank rows. Secondary: totals of blank_rows_dropped / fragments_merged /
null_columns_pruned aggregated from per-item filter_stats.
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_STEP_DIR = _HERE.parent
sys.path.insert(0, str(_HERE.parents[2]))  # steps/filter_phantom_rows/eval -> foi_pipeline

from eval import utils as eval_utils

STEP = "filter_phantom_rows"


def has_leaked_split_row(rows):
    """True if any non-header row still has exactly 1 non-None cell across >= 3 columns.

    Sparse-layout files (guarded in the step: >50% single-value data rows) are
    excluded — their single-value rows are the file's shape, not leaks.
    """
    data = rows[1:]
    if not data:
        return False
    singles = [r for r in data if len(r) >= 3 and sum(1 for c in r if c is not None) == 1]
    if len(singles) / len(data) > 0.5:
        return False
    return bool(singles)


def has_blank_row(rows):
    return any(
        not row or all(c is None or (isinstance(c, str) and not c.strip()) for c in row)
        for row in rows
    )


def run_eval(items, input_hash):
    with_rows = [r for r in items if r.get("rows")]
    pdf_items = [r for r in with_rows if r.get("file_type") == "pdf"]

    totals = {"blank_rows_dropped": 0, "fragments_merged": 0, "null_columns_pruned": 0}
    for r in items:
        for k, v in (r.get("filter_stats") or {}).items():
            totals[k] = totals.get(k, 0) + v

    clean = 0
    flagged = []
    for item in pdf_items:
        rows = item["rows"]
        if has_leaked_split_row(rows) or has_blank_row(rows):
            flagged.append(item["file_url"])
        else:
            clean += 1

    total = len(pdf_items)
    metrics = [
        eval_utils.Metric("post_filter_clean_rate",
                          round(clean / total, 3) if total else 0.0,
                          {"clean": clean, "total": total}, is_primary=True),
        eval_utils.Metric("blank_rows_dropped_total", float(totals["blank_rows_dropped"]),
                          {"total_files": len(items)}),
        eval_utils.Metric("fragments_merged_total", float(totals["fragments_merged"]),
                          {"total_files": len(items)}),
        eval_utils.Metric("null_columns_pruned_total", float(totals["null_columns_pruned"]),
                          {"total_files": len(items)}),
    ]

    issues = []
    if flagged:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{len(flagged)} files still contain split-fragment or blank rows after filtering",
            affected_count=len(flagged),
            affected_ids=flagged[:50],
            suggested_upstream_step="transform_disclosure_files",
            suggestion_detail="fragment merge / blank-row drop heuristics in filter_phantom_rows missed these files",
            confidence=0.9))
    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash, judge_model=None)
    return results, issues


def main():
    parser = argparse.ArgumentParser(description="Evaluate filter_phantom_rows output")
    parser.add_argument("--input-path", dest="input_path",
                        default=str(_STEP_DIR / "output.json"))
    args = parser.parse_args()

    input_path = Path(args.input_path)
    data = json.loads(input_path.read_text())
    results, issues = run_eval(data["results"], eval_utils.input_hash(input_path))
    eval_utils.write_eval_outputs(_HERE, results, issues)
    primary = results.metrics[0]
    print(f"{STEP}: post_filter_clean_rate={primary.value:.3f} "
          f"({primary.counts['clean']}/{primary.counts['total']} clean PDFs), "
          f"{len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
