#!/usr/bin/env python3
"""Evaluate header-row detection: exact-match accuracy vs net-new labels.

Deterministic — re-runs detect_header_row() on a frozen input fixture and
compares the integer index to verified labels.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

from eval import utils as eval_utils
from steps.extract_disclosures_detect_header_row.process import detect_header_row

STEP = "extract_disclosures_detect_header_row"


def _has_null_header_column(rows):
    """True if the detected header row contains at least one None cell."""
    if not rows:
        return False
    idx = detect_header_row(rows)
    if idx >= len(rows):
        return False
    return any(c is None for c in rows[idx])


def run_eval(items, labels, input_hash):
    by_url = {it["file_url"]: it for it in items}
    correct = 0
    total = 0
    mismatches = []
    for row in labels:
        if row.get("verified") != "yes":
            continue
        item = by_url.get(row["file_url"])
        if item is None or item.get("rows") is None:
            continue
        total += 1
        expected = int(row["expected_header_row_index"])
        detected = detect_header_row(item["rows"])
        if detected == expected:
            correct += 1
        else:
            mismatches.append((row["file_url"], expected, detected))

    accuracy = correct / total if total else 0.0

    # --- new: null_header_column_rate over all PDF items ---
    pdf_items = [it for it in items if it.get("file_type") == "pdf" and it.get("rows")]
    pdf_total = len(pdf_items)
    null_header_flagged = [it for it in pdf_items if _has_null_header_column(it["rows"])]
    null_header_count = len(null_header_flagged)
    null_header_rate = round(null_header_count / pdf_total, 3) if pdf_total else 0.0

    metrics = [
        eval_utils.Metric("accuracy", round(accuracy, 3),
                          {"correct": correct, "total": total}, is_primary=True),
        eval_utils.Metric("null_header_column_rate", null_header_rate,
                          {"flagged": null_header_count, "total": pdf_total}),
    ]

    issues = []
    for url, expected, detected in mismatches:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"Detected header row {detected}, expected {expected}",
            affected_count=1, affected_ids=[url],
            suggested_upstream_step=None,
            suggestion_detail="detect_header_row guard logic may need work",
            confidence=0.7))
    if null_header_flagged:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{null_header_count} PDFs have None cells in detected header ({null_header_rate:.1%})",
            affected_count=null_header_count,
            affected_ids=[it["file_url"] for it in null_header_flagged[:50]],
            suggested_upstream_step="extract_disclosures_normalize_header",
            suggestion_detail="forward-fill nulls and collapse multi-row headers",
            confidence=1.0))

    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash, judge_model=None)
    return results, issues


def _load_labels(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Evaluate header-row detection")
    parser.add_argument("--input-path", dest="input_path", default=str(here / "input.json"))
    parser.add_argument("--labels", default=str(here / "labels.csv"))
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture input.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, here / "input.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    items = json.loads(Path(args.input_path).read_text())["results"]
    labels = _load_labels(args.labels)
    results, issues = run_eval(items, labels, eval_utils.input_hash(Path(args.input_path)))
    eval_utils.write_eval_outputs(here, results, issues)
    primary = results.metrics[0]
    null_rate_metric = results.metrics[1]
    print(f"{STEP}: accuracy={primary.value:.3f} "
          f"({primary.counts['correct']}/{primary.counts['total']}), "
          f"null_header_column_rate={null_rate_metric.value:.3f} "
          f"({null_rate_metric.counts['flagged']}/{null_rate_metric.counts['total']}), "
          f"{len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
