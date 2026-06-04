#!/usr/bin/env python3
"""Evaluate get_foi_emails: accuracy via human-verified labels.csv.

Compares foi_email in frozen fixture to expected_email in labels.
Primary metric = accuracy. No LLM judging required.

CLI:
  uv run python steps/get_foi_emails/eval/evaluate.py
  uv run python steps/get_foi_emails/eval/evaluate.py --refresh-fixture steps/get_foi_emails/output.json
"""
import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

from eval import utils as eval_utils

STEP = "get_foi_emails"


def _normalise(value):
    """Normalise email value for comparison: None and '' are both treated as absent."""
    if value is None:
        return ""
    return str(value).strip().lower()


def score_records(records, labels, *, input_hash):
    """Score records against labels. Returns (EvalResults, list[Issue]).

    records: list of dicts from input.json results (keys: public_body_id, foi_email, email_status)
    labels:  list of dicts from labels.csv (keys: public_body_id, expected_email)
    """
    record_by_id = {r["public_body_id"]: r for r in records}

    correct = 0
    incorrect_ids = []
    per_status = {}  # status -> {"correct": int, "total": int}

    for label in labels:
        body_id = int(label["public_body_id"])
        expected = _normalise(label["expected_email"])
        record = record_by_id.get(body_id)
        if record is None:
            continue
        actual = _normalise(record.get("foi_email"))
        status = record.get("email_status", "unknown")

        if status not in per_status:
            per_status[status] = {"correct": 0, "total": 0}
        per_status[status]["total"] += 1

        if actual == expected:
            correct += 1
            per_status[status]["correct"] += 1
        else:
            incorrect_ids.append(body_id)

    total = len(labels)
    accuracy = correct / total if total else 0.0

    metrics = [
        eval_utils.Metric(
            "accuracy",
            round(accuracy, 3),
            {"correct": correct, "total": total},
            is_primary=True,
        )
    ]

    for status_key in ("found", "multiple_found", "not_found"):
        counts = per_status.get(status_key, {"correct": 0, "total": 0})
        val = counts["correct"] / counts["total"] if counts["total"] else 0.0
        metrics.append(
            eval_utils.Metric(
                f"{status_key}_accuracy",
                round(val, 3),
                counts,
            )
        )

    issues = []
    if incorrect_ids:
        issues.append(
            eval_utils.Issue(
                severity="warning",
                description=f"{len(incorrect_ids)} records have incorrect foi_email",
                affected_count=len(incorrect_ids),
                affected_ids=[str(i) for i in incorrect_ids],
                suggested_upstream_step="get_foi_emails",
                suggestion_detail="foi_email does not match expected_email in labels.csv",
                confidence=1.0,
            )
        )

    results = eval_utils.EvalResults(
        step=STEP,
        metrics=metrics,
        input_hash=input_hash,
        judge_model=None,
    )
    return results, issues


def _load_labels(labels_path):
    with open(labels_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Evaluate get_foi_emails accuracy")
    parser.add_argument("--input-path", dest="input_path",
                        default=str(here / "input.json"))
    parser.add_argument("--labels", default=str(here / "labels.csv"))
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-slice input.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        labels = _load_labels(args.labels)
        label_ids = {int(row["public_body_id"]) for row in labels}
        live = json.loads(Path(args.refresh_fixture).read_text())
        sliced = [r for r in live["results"] if r["public_body_id"] in label_ids]
        fixture = {"metadata": {}, "results": sliced}
        Path(args.input_path).write_text(json.dumps(fixture, indent=2))
        print(f"Refreshed fixture: {len(sliced)} records -> {args.input_path}")
        return 0

    fixture = json.loads(Path(args.input_path).read_text())
    records = fixture["results"]
    labels = _load_labels(args.labels)

    results, issues = score_records(
        records, labels, input_hash=eval_utils.input_hash(Path(args.input_path))
    )

    eval_utils.write_eval_outputs(here, results, issues)
    primary = next(m for m in results.metrics if m.is_primary)
    print(
        f"{STEP}: accuracy={primary.value:.3f} "
        f"({primary.counts['correct']}/{primary.counts['total']} correct), "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
