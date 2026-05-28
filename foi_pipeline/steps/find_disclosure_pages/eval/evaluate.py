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


def _load_labels(path):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("label")]


def _load_records(path):
    data = json.loads(Path(path).read_text())
    return {str(r["public_body_id"]): r for r in data["results"]}


def main():
    parser = argparse.ArgumentParser(description="Evaluate find_disclosure_pages output")
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    labels = _load_labels(args.labels)
    records = _load_records(args.output)
    counts, precision, recall, f1, details, skipped = score(records, labels)

    print(f"Labelled bodies evaluated: {sum(counts.values())}")
    print(f"  TP={counts['TP']}  FP={counts['FP']}  FN={counts['FN']}  TN={counts['TN']}")
    print(f"  precision={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}")
    if skipped:
        print(f"  WARNING: {skipped} labelled bodies had no output record (excluded from metrics)")
    if details["FP"]:
        print("\nFALSE POSITIVES (returned a wrong/spurious distinct page):")
        for pid, url in details["FP"]:
            print(f"  [{pid}] {url}")
    if details["FN"]:
        print("\nFALSE NEGATIVES (a log exists but we fell back to the FOI page):")
        for pid, url in details["FN"]:
            print(f"  [{pid}] {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
