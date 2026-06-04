#!/usr/bin/env python3
"""Evaluate transform_disclosure_files: raw PDF extraction quality via heuristic flags.

Measures the *pre-normalization* state of extracted PDF rows — i.e. what pdfplumber
produces before normalize_disclosure_cells applies its fixes. Use the normalize eval
(steps/normalize_disclosure_cells/eval/evaluate.py) to measure post-normalization quality.

Three binary flags per PDF record:
  null_first_row     — any cell in rows[0] is None
  null_column        — at least one column index where every row has None
                       (addressed downstream by normalize_disclosure_cells._prune_null_columns)
  newline_split_row  — at least one non-header row with exactly 1 non-None cell
                       across >= 3 columns
                       (addressed downstream by normalize_disclosure_cells._merge_continuation_rows)

Primary metric: clean_extraction_rate (fraction of PDFs with zero flags).
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

from eval import utils as eval_utils

STEP = "transform_disclosure_files"


def has_null_first_row(rows):
    """True if any cell in rows[0] is None."""
    if not rows:
        return False
    return any(c is None for c in rows[0])


def has_null_column(rows):
    """True if any column index is missing in some row or has None in every row."""
    if not rows:
        return False
    ncols = max(len(row) for row in rows)
    for col in range(ncols):
        if any(col >= len(row) for row in rows):  # missing in some row
            return True
        if all(row[col] is None for row in rows):  # all-None in complete columns
            return True
    return False


def has_newline_split_row(rows):
    """True if any non-header row has exactly 1 non-None cell across >= 3 columns."""
    for row in rows[1:]:
        if len(row) >= 3 and sum(1 for c in row if c is not None) == 1:
            return True
    return False


def _flag_item(item):
    rows = item.get("rows") or []
    return {
        "null_first_row": has_null_first_row(rows),
        "null_column": has_null_column(rows),
        "newline_split_row": has_newline_split_row(rows),
    }


def _flagged_row_count(rows):
    return sum(
        1 for row in rows[1:]
        if len(row) >= 3 and sum(1 for c in row if c is not None) == 1
    )


def build_quality_by_body(items, process_warning_urls):
    by_body = {}
    for item in items:
        bid = item.get("public_body_id")
        if bid not in by_body:
            by_body[bid] = {
                "name": item.get("name", ""),
                "total_pdfs": 0,
                "clean": 0,
                "null_first_row": 0,
                "null_column": 0,
                "newline_split_row": 0,
                "flagged_samples": [],
            }
        entry = by_body[bid]
        entry["total_pdfs"] += 1
        flags = _flag_item(item)
        if not any(flags.values()):
            entry["clean"] += 1
            continue
        for flag_name, fired in flags.items():
            if fired:
                entry[flag_name] += 1
        rows = item.get("rows") or []
        entry["flagged_samples"].append({
            "file_url": item["file_url"],
            "flags": [k for k, v in flags.items() if v],
            "total_rows": len(rows),
            "flagged_rows": _flagged_row_count(rows) if flags["newline_split_row"] else 1,
            "has_process_warning": item["file_url"] in process_warning_urls,
            "first_rows": rows[:3],
        })
    return by_body


def run_eval(items, process_warning_urls, input_hash):
    if not items:
        metrics = [
            eval_utils.Metric("clean_extraction_rate", 0.0, {"clean": 0, "total": 0}, is_primary=True),
            eval_utils.Metric("null_first_row_rate", 0.0, {"flagged": 0, "total": 0}),
            eval_utils.Metric("null_column_rate", 0.0, {"flagged": 0, "total": 0}),
            eval_utils.Metric("newline_split_row_rate", 0.0, {"flagged": 0, "total": 0}),
        ]
        results = eval_utils.EvalResults(step=STEP, metrics=metrics, input_hash=input_hash, judge_model=None)
        return results, [], {}

    clean = 0
    null_first_row_ids, null_col_ids, newline_split_ids = [], [], []

    for item in items:
        flags = _flag_item(item)
        if not any(flags.values()):
            clean += 1
        if flags["null_first_row"]:
            null_first_row_ids.append(item["file_url"])
        if flags["null_column"]:
            null_col_ids.append(item["file_url"])
        if flags["newline_split_row"]:
            newline_split_ids.append(item["file_url"])

    total = len(items)
    metrics = [
        eval_utils.Metric("clean_extraction_rate", round(clean / total, 3),
                          {"clean": clean, "total": total}, is_primary=True),
        eval_utils.Metric("null_first_row_rate", round(len(null_first_row_ids) / total, 3),
                          {"flagged": len(null_first_row_ids), "total": total}),
        eval_utils.Metric("null_column_rate", round(len(null_col_ids) / total, 3),
                          {"flagged": len(null_col_ids), "total": total}),
        eval_utils.Metric("newline_split_row_rate", round(len(newline_split_ids) / total, 3),
                          {"flagged": len(newline_split_ids), "total": total}),
    ]

    issues = []
    for flag_name, ids in [
        ("null_first_row", null_first_row_ids),
        ("null_column", null_col_ids),
        ("newline_split_row", newline_split_ids),
    ]:
        if ids:
            issues.append(eval_utils.Issue(
                severity="warning",
                description=f"{len(ids)} PDFs flagged: {flag_name} ({len(ids)/total:.1%})",
                affected_count=len(ids),
                affected_ids=ids[:50],
                suggested_upstream_step=STEP,
                suggestion_detail=f"Improve pdfplumber extraction to reduce {flag_name} failures",
                confidence=1.0,
            ))

    quality_by_body = build_quality_by_body(items, process_warning_urls)
    results = eval_utils.EvalResults(step=STEP, metrics=metrics, input_hash=input_hash, judge_model=None)
    return results, issues, quality_by_body


def _load_process_warning_urls(errors_path):
    if not errors_path.exists():
        return set()
    errors = json.loads(errors_path.read_text())
    return {
        e["context"]["file_url"]
        for e in errors
        if e.get("error_type") in ("MultipleTableWarning", "CellSerializationWarning")
        and "file_url" in e.get("context", {})
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate transform_disclosure_files PDF extraction quality"
    )
    parser.add_argument("--input-path", dest="input_path", default=str(_HERE / "input.json"))
    parser.add_argument("--errors-path", dest="errors_path", default=str(_HERE.parent / "errors.json"))
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture input.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, _HERE / "input.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    data = json.loads(Path(args.input_path).read_text())
    items = [
        r for r in data["results"]
        if r.get("file_type") == "pdf" and r.get("rows") is not None
    ]
    process_warning_urls = _load_process_warning_urls(Path(args.errors_path))

    results, issues, quality_by_body = run_eval(
        items, process_warning_urls, eval_utils.input_hash(Path(args.input_path))
    )

    eval_utils.write_eval_outputs(_HERE, results, issues)
    (_HERE / "quality_by_body.json").write_text(json.dumps(quality_by_body, indent=2))

    primary = results.metrics[0]
    print(
        f"{STEP}: clean_extraction_rate={primary.value:.3f} "
        f"({primary.counts['clean']}/{primary.counts['total']} clean PDFs), "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
