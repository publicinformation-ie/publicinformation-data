#!/usr/bin/env python3
"""Evaluate extract_disclosures_normalize_header: null_header_column_rate after repair."""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))

from eval import utils as eval_utils

STEP = "extract_disclosures_normalize_header"


def _has_null_header_column(rows, header_row_idx):
    if not rows or header_row_idx >= len(rows):
        return False
    return any(c is None for c in rows[header_row_idx])


def run_eval(items, input_hash):
    pdf_items = [
        it for it in items
        if it.get("file_type") == "pdf"
        and it.get("rows")
        and it.get("header_row_idx") is not None
    ]
    total = len(pdf_items)
    flagged = [
        it for it in pdf_items
        if _has_null_header_column(it["rows"], it["header_row_idx"])
    ]
    flagged_count = len(flagged)
    rate = round(flagged_count / total, 3) if total else 0.0

    metrics = [
        eval_utils.Metric("null_header_column_rate", rate,
                          {"flagged": flagged_count, "total": total},
                          is_primary=True),
    ]
    issues = []
    if flagged:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"{flagged_count} PDFs still have None in header after normalization ({rate:.1%})",
            affected_count=flagged_count,
            affected_ids=[it["file_url"] for it in flagged[:50]],
            suggested_upstream_step=STEP,
            suggestion_detail="these may be genuinely non-tabular PDFs",
            confidence=0.7,
        ))

    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash, judge_model=None)
    return results, issues


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate normalize_header: null column rate after repair"
    )
    parser.add_argument("--input-path", dest="input_path",
                        default=str(_HERE / "input.json"))
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture input.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, _HERE / "input.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    data = json.loads(Path(args.input_path).read_text())
    items = data["results"]
    results, issues = run_eval(items, eval_utils.input_hash(Path(args.input_path)))
    eval_utils.write_eval_outputs(_HERE, results, issues)
    primary = results.metrics[0]
    print(f"{STEP}: null_header_column_rate={primary.value:.3f} "
          f"({primary.counts['flagged']}/{primary.counts['total']}), "
          f"{len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
