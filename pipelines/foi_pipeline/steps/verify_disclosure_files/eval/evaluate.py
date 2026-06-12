#!/usr/bin/env python3
"""Evaluate verify_disclosure_files: content-based FOI signal detection precision.

Primary metric: true_rejection_rate — fraction of human-judged-no (verified="yes"|"mock")
files that receive "rejected" status. Must be high.

Secondary metric: false_rejection_rate — fraction of human-judged-yes files that receive
"rejected" status. Must be 0.

Judgments keyed by file_url in judgments.json:
  { url: { label: "yes"|"no", rationale: str, verified: "yes"|"no"|"auto"|"mock" } }

Only "yes" and "mock" verified entries count toward metrics.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # steps/verify_disclosure_files/eval -> foi_pipeline

from eval import utils as eval_utils
from eval.utils import EvalResults, Issue, Metric

STEP = "verify_disclosure_files"
_TRUSTED_VERIFIED = {"yes", "mock"}


def run_eval(items, judgments, input_hash):
    total = len(items)
    status_counts = Counter(r["verification_status"] for r in items)

    judged_yes = [
        r for r in items
        if judgments.get(r["file_url"], {}).get("label") == "yes"
        and judgments.get(r["file_url"], {}).get("verified") in _TRUSTED_VERIFIED
    ]
    judged_no = [
        r for r in items
        if judgments.get(r["file_url"], {}).get("label") == "no"
        and judgments.get(r["file_url"], {}).get("verified") in _TRUSTED_VERIFIED
    ]

    true_rejections = [r for r in judged_no if r["verification_status"] == "rejected"]
    false_rejections = [r for r in judged_yes if r["verification_status"] == "rejected"]

    true_rejection_rate = len(true_rejections) / len(judged_no) if judged_no else 0.0
    false_rejection_rate = len(false_rejections) / len(judged_yes) if judged_yes else 0.0

    metrics = [
        Metric(
            name="true_rejection_rate",
            value=true_rejection_rate,
            counts={
                "rejected": len(true_rejections),
                "not_rejected": len(judged_no) - len(true_rejections),
                "total_judged_no": len(judged_no),
            },
            is_primary=True,
        ),
        Metric(
            name="false_rejection_rate",
            value=false_rejection_rate,
            counts={
                "false_rejections": len(false_rejections),
                "total_judged_yes": len(judged_yes),
            },
        ),
        Metric(
            name="status_distribution",
            value=status_counts.get("verified", 0) / total if total else 0.0,
            counts=dict(status_counts),
        ),
    ]

    issues = []

    for r in false_rejections:
        j = judgments[r["file_url"]]
        issues.append(Issue(
            severity="error",
            description=f"Judged-yes file incorrectly rejected: {r['file_url']}",
            affected_count=1,
            affected_ids=[r["file_url"]],
            suggestion_detail=j.get("rationale", ""),
        ))

    escaped = [r for r in judged_no if r["verification_status"] == "verified"]
    if escaped:
        issues.append(Issue(
            severity="warning",
            description=f"{len(escaped)} judged-no file(s) passed verification (false negatives — escaped rejection)",
            affected_count=len(escaped),
            affected_ids=[r["file_url"] for r in escaped],
        ))

    return EvalResults(
        step=STEP,
        metrics=metrics,
        input_hash=input_hash,
    ), issues


def main():
    parser = argparse.ArgumentParser(description="Evaluate verify_disclosure_files signal precision")
    parser.add_argument("--input-path", dest="input_path",
                        default=str(_HERE.parent / "output.json"))
    parser.add_argument("--judgments-path", dest="judgments_path",
                        default=str(_HERE / "judgments.json"))
    args = parser.parse_args()

    data = json.loads(Path(args.input_path).read_text())
    items = data.get("results", [])

    judgments_path = Path(args.judgments_path)
    judgments = json.loads(judgments_path.read_text()) if judgments_path.exists() else {}

    results, issues = run_eval(items, judgments, eval_utils.input_hash(Path(args.input_path)))

    eval_utils.write_eval_outputs(_HERE, results, issues)

    primary = results.metrics[0]
    print(
        f"{STEP}: true_rejection_rate={primary.value:.3f} "
        f"({primary.counts['rejected']}/{primary.counts['total_judged_no']} judged-no files rejected), "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
