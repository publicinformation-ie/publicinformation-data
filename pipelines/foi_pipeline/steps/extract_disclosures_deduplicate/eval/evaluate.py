#!/usr/bin/env python3
"""Evaluate deduplication quality via records_kept_ratio per public body.

The primary metric is overall_records_kept_ratio (dedup output / canonicalize
output across all bodies). Bodies with a very low ratio are flagged as likely
having upstream extraction artefacts (e.g. repeated page-header rows in PDFs)
that should be fixed at the source rather than papered over here.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ on sys.path

from eval import utils as eval_utils

STEP = "extract_disclosures_deduplicate"
LOW_RATIO_THRESHOLD = 0.5  # bodies keeping <50% of records get flagged


def _count_by_body(records):
    counts = defaultdict(int)
    for r in records:
        body_id = r.get("public_body_id")
        if body_id is not None:
            counts[body_id] += 1
    return dict(counts)


def run_eval(before_records, after_records, input_hash):
    before_counts = _count_by_body(before_records)
    after_counts = _count_by_body(after_records)

    total_before = sum(before_counts.values())
    total_after = sum(after_counts.values())
    overall_ratio = round(total_after / total_before, 3) if total_before else 0.0

    body_ratios = {
        body_id: round(after_counts.get(body_id, 0) / before, 3)
        for body_id, before in before_counts.items()
        if before > 0
    }
    low_ratio_bodies = sorted(
        body_id for body_id, ratio in body_ratios.items()
        if ratio < LOW_RATIO_THRESHOLD
    )
    pct_bodies_low = round(len(low_ratio_bodies) / len(body_ratios), 3) if body_ratios else 0.0

    metrics = [
        eval_utils.Metric(
            "overall_records_kept_ratio",
            overall_ratio,
            {
                "total_before": total_before,
                "total_after": total_after,
                "removed": total_before - total_after,
            },
            is_primary=True,
        ),
        eval_utils.Metric(
            "pct_bodies_low_ratio",
            pct_bodies_low,
            {
                "threshold": LOW_RATIO_THRESHOLD,
                "low_ratio_count": len(low_ratio_bodies),
                "total_bodies_with_records": len(body_ratios),
            },
        ),
    ]

    issues = []
    if low_ratio_bodies:
        issues.append(eval_utils.Issue(
            severity="info",
            description=(
                f"{len(low_ratio_bodies)} bodies kept "
                f"<{LOW_RATIO_THRESHOLD:.0%} of records after dedup"
            ),
            affected_count=len(low_ratio_bodies),
            affected_ids=[str(b) for b in low_ratio_bodies],
            suggested_upstream_step="transform_disclosure_files",
            suggestion_detail=(
                "Repeated page-header and blank separator rows in PDFs inflate "
                "record counts before dedup. Fix at extraction time."
            ),
            confidence=0.8,
        ))

    results = eval_utils.EvalResults(
        step=STEP,
        metrics=metrics,
        input_hash=input_hash,
        judge_model=None,
    )
    return results, issues


def main():
    here = Path(__file__).parent
    step_dir = here.parent
    before_path = step_dir.parent / "extract_disclosures_canonicalize" / "output.json"
    after_path = step_dir / "output.json"

    before_records = json.loads(before_path.read_text())["results"]
    after_records = json.loads(after_path.read_text())["results"]

    results, issues = run_eval(
        before_records,
        after_records,
        eval_utils.input_hash(after_path),
    )
    eval_utils.write_eval_outputs(here, results, issues)

    p = results.metrics[0]
    low = results.metrics[1]
    print(
        f"{STEP}: overall_records_kept_ratio={p.value:.3f} "
        f"({p.counts['total_after']}/{p.counts['total_before']}), "
        f"{low.counts['low_ratio_count']} bodies below "
        f"{LOW_RATIO_THRESHOLD:.0%} threshold, "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
