#!/usr/bin/env python3
"""
Evaluate find_disclosure_pages output against a labelled eval set.

A "positive" prediction = the system returned a *distinct* disclosure page
(disclosure_page_url != foi_page_url). Correctness depends on the label:

  distinct_log  -> TP if predicted distinct AND url matches expected, else
                   FN if it fell back to the FOI page, else FP (wrong url).
  use_foi_page  -> TN if it fell back to the FOI page, else FP.
  no_log_exists -> same as use_foi_page.

Usage (from foi_pipeline/):
    uv run python steps/find_disclosure_pages/eval/evaluate.py \
        --labels steps/find_disclosure_pages/eval/labels.csv \
        --output steps/find_disclosure_pages/eval/matcher_output.json
"""
import argparse
import csv
import json
import sys
from pathlib import Path

# Allow running as a script from foi_pipeline/ or any parent directory
_HERE = Path(__file__).resolve().parent
_FOI_PIPELINE_ROOT = _HERE.parents[2]  # steps/find_disclosure_pages/eval -> foi_pipeline
if str(_FOI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FOI_PIPELINE_ROOT))

import eval_utils


def _norm(url):
    return (url or "").rstrip("/").lower()


def classify(record, label_row):
    """Return 'TP' | 'FP' | 'FN' | 'TN' for one labelled body."""
    predicted = record["disclosure_page_url"]
    foi = record["foi_page_url"]
    label = label_row["label"]
    expected = label_row["expected_url"]

    predicted_distinct = _norm(predicted) != _norm(foi)

    if label == "distinct_log":
        if not predicted_distinct:
            return "FN"
        return "TP" if _norm(predicted) == _norm(expected) else "FP"
    # use_foi_page / no_log_exists
    return "FP" if predicted_distinct else "TN"


def score(records_by_id, labels):
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    details = {"FP": [], "FN": []}
    skipped = 0
    for row in labels:
        record = records_by_id.get(str(row["public_body_id"]))
        if record is None:
            skipped += 1
            continue
        outcome = classify(record, row)
        counts[outcome] += 1
        if outcome == "FP":
            details["FP"].append((str(row["public_body_id"]), record["disclosure_page_url"]))
        elif outcome == "FN":
            details["FN"].append((str(row["public_body_id"]), row["expected_url"]))
    tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return counts, precision, recall, f1, details, skipped


def run_eval(records_by_id, labels, fixture_path):
    """Build EvalResults + Issues from scored records. Pure given inputs."""
    counts, precision, recall, f1, details, skipped = score(records_by_id, labels)

    metrics = [
        eval_utils.Metric("f1", round(f1, 3),
                          {"TP": counts["TP"], "FP": counts["FP"], "FN": counts["FN"],
                           "TN": counts["TN"]}, is_primary=True),
        eval_utils.Metric("precision", round(precision, 3),
                          {"TP": counts["TP"], "FP": counts["FP"]}),
        eval_utils.Metric("recall", round(recall, 3),
                          {"TP": counts["TP"], "FN": counts["FN"]}),
    ]

    issues = []
    for pid, url in details["FP"]:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"Spurious distinct disclosure page returned for body {pid}",
            affected_count=1, affected_ids=[str(pid)],
            suggested_upstream_step=None,
            suggestion_detail=f"returned {url}", confidence=0.6))
    if skipped:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{skipped} labelled bodies had no output record "
                        f"(excluded from metrics — label rot)",
            affected_count=skipped, affected_ids=[],
            suggested_upstream_step=None,
            suggestion_detail="re-check labels.csv against current bodies",
            confidence=1.0))

    results = eval_utils.EvalResults(
        step="find_disclosure_pages",
        metrics=metrics,
        input_hash=eval_utils.input_hash(fixture_path),
        judge_model=None,
    )
    return results, issues


def _load_labels(path):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("label")]


def _load_records(path):
    data = json.loads(Path(path).read_text())
    return {str(r["public_body_id"]): r for r in data["results"]}


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Evaluate find_disclosure_pages output")
    parser.add_argument("--labels", default=str(here / "labels.csv"))
    parser.add_argument("--input-path", dest="input_path",
                        default=str(here / "matcher_output.json"),
                        help="Frozen fixture to score (default) or a live run path")
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture matcher_output.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, here / "matcher_output.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    labels = _load_labels(args.labels)
    records = _load_records(args.input_path)
    counts, precision, recall, f1, details, skipped = score(records, labels)

    print(f"Labelled bodies evaluated: {sum(counts.values())}")
    print(f"  TP={counts['TP']}  FP={counts['FP']}  FN={counts['FN']}  TN={counts['TN']}")
    print(f"  precision={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}")
    if skipped:
        print(f"  WARNING: {skipped} labelled bodies had no output record (excluded)")

    results, issues = run_eval(records, labels, Path(args.input_path))
    eval_utils.write_eval_outputs(here, results, issues)
    return 0


if __name__ == "__main__":
    sys.exit(main())
