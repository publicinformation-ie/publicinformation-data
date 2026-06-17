#!/usr/bin/env python3
"""Evaluate extract_disclosures_normalize_header: null_header_column_rate and null_first_row_rate after repair."""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))

from eval import utils as eval_utils

STEP = "extract_disclosures_normalize_header"


def _header_has_null_column(rows, header_row_idx):
    if not rows or header_row_idx >= len(rows):
        return False
    return any(c is None for c in rows[header_row_idx])


def _has_null_first_row(rows):
    if not rows:
        return False
    return any(c is None for c in rows[0])


def run_eval(items, input_hash):
    pdf_items = [
        it for it in items
        if it.get("file_type") == "pdf"
        and it.get("rows")
        and it.get("header_row_idx") is not None
    ]
    total = len(pdf_items)
    flagged_null_header = [
        it for it in pdf_items
        if _header_has_null_column(it["rows"], it["header_row_idx"])
    ]
    null_header_count = len(flagged_null_header)
    null_header_rate = round(null_header_count / total, 3) if total else 0.0

    flagged_nfr = [it for it in pdf_items if _has_null_first_row(it["rows"])]
    nfr_count = len(flagged_nfr)
    nfr_rate = round(nfr_count / total, 3) if total else 0.0

    metrics = [
        eval_utils.Metric("null_header_column_rate", null_header_rate,
                          {"flagged": null_header_count, "total": total},
                          is_primary=True),
        eval_utils.Metric("null_first_row_rate", nfr_rate,
                          {"count": nfr_count, "total": total}),
    ]
    issues = []
    if flagged_null_header:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"{null_header_count} PDFs still have None in header after normalization ({null_header_rate:.1%})",
            affected_count=null_header_count,
            affected_ids=[it["file_url"] for it in flagged_null_header[:50]],
            suggested_upstream_step=STEP,
            suggestion_detail="these may be genuinely non-tabular PDFs",
            confidence=0.7,
        ))
    if flagged_nfr:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{nfr_count} PDFs have null cells in rows[0] after normalization ({nfr_rate:.1%})",
            affected_count=nfr_count,
            affected_ids=[it["file_url"] for it in flagged_nfr[:50]],
            suggested_upstream_step=STEP,
            suggestion_detail="title rows before the header were not stripped",
            confidence=0.9,
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
    nfr = results.metrics[1]
    print(f"{STEP}: null_header_column_rate={primary.value:.3f} "
          f"({primary.counts['flagged']}/{primary.counts['total']}), "
          f"null_first_row_rate={nfr.value:.3f} "
          f"({nfr.counts['count']}/{nfr.counts['total']}), "
          f"{len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
