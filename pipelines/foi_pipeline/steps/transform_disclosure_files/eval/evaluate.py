#!/usr/bin/env python3
"""Evaluate transform_disclosure_files: extraction quality of PDF table contents.

Primary metric: clean_extraction_rate — fraction of PDFs with no known quality issues.
Supplementary metrics track each issue type independently (null_first_row, null_column,
newline_split_row) plus camelot fallback and win rates.
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

from eval import utils as eval_utils

STEP = "transform_disclosure_files"


def has_null_first_row(rows: list) -> bool:
    if not rows:
        return False
    return any(cell is None for cell in rows[0])


def has_null_column(rows: list) -> bool:
    if not rows:
        return False
    data_rows = rows[1:]
    if not data_rows:
        return False
    n_cols = max(len(r) for r in rows)
    # Exclude newline-split rows (exactly 1 non-null in a 3+-col table) so
    # their structural nulls don't falsely flag a column as always-null.
    non_split = [
        row for row in data_rows
        if not (n_cols >= 3 and sum(1 for c in row if c is not None) == 1)
    ]
    if not non_split:
        return False
    for col_idx in range(n_cols):
        if all(col_idx >= len(row) or row[col_idx] is None for row in non_split):
            return True
    return False


def has_newline_split_row(rows: list) -> bool:
    if len(rows) < 2:
        return False
    n_cols = max(len(r) for r in rows)
    if n_cols < 3:
        return False
    for row in rows[1:]:
        if sum(1 for c in row if c is not None) == 1:
            return True
    return False


def _flags(rows: list) -> list[str]:
    result = []
    if has_null_first_row(rows):
        result.append("null_first_row")
    if has_null_column(rows):
        result.append("null_column")
    if has_newline_split_row(rows):
        result.append("newline_split_row")
    return result


def _count_split_rows(rows: list) -> int:
    if len(rows) < 2:
        return 0
    n_cols = max(len(r) for r in rows) if rows else 0
    if n_cols < 3:
        return 0
    return sum(
        1 for row in rows[1:]
        if sum(1 for c in row if c is not None) == 1
    )


def build_quality_by_body(items: list, process_warning_urls: set) -> dict:
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
        rows = item.get("rows") or []
        item_flags = _flags(rows)
        if not item_flags:
            entry["clean"] += 1
        else:
            for flag in item_flags:
                entry[flag] += 1
            entry["flagged_samples"].append({
                "file_url": item["file_url"],
                "flags": item_flags,
                "flagged_rows": _count_split_rows(rows),
                "total_rows": len(rows),
                "first_rows": rows[:3],
                "has_process_warning": item["file_url"] in process_warning_urls,
                "pdf_extractor": item.get("pdf_extractor", "pdfplumber"),
            })
    return by_body


def run_eval(items, process_warning_urls, input_hash, camelot_fallback_urls=None):
    if camelot_fallback_urls is None:
        camelot_fallback_urls = set()

    total = len(items)

    if total == 0:
        metrics = [
            eval_utils.Metric("clean_extraction_rate", 0.0, {"clean": 0, "total": 0}, is_primary=True),
            eval_utils.Metric("null_first_row_rate", 0.0, {"count": 0, "total": 0}),
            eval_utils.Metric("null_column_rate", 0.0, {"count": 0, "total": 0}),
            eval_utils.Metric("newline_split_row_rate", 0.0, {"count": 0, "total": 0}),
            eval_utils.Metric("camelot_fallback_rate", 0.0, {"attempted": 0, "total": 0}),
            eval_utils.Metric("camelot_win_rate", 0.0, {"wins": 0, "total": 0}),
        ]
        results = eval_utils.EvalResults(step=STEP, metrics=metrics, input_hash=input_hash, judge_model=None)
        return results, [], {}

    flags_by_item = [_flags(item.get("rows") or []) for item in items]

    clean_count = sum(1 for f in flags_by_item if not f)
    null_first_row_count = sum(1 for f in flags_by_item if "null_first_row" in f)
    null_column_count = sum(1 for f in flags_by_item if "null_column" in f)
    newline_split_count = sum(1 for f in flags_by_item if "newline_split_row" in f)
    camelot_fallback_count = sum(1 for item in items if item.get("file_url") in camelot_fallback_urls)
    camelot_win_count = sum(1 for item in items if item.get("pdf_extractor") == "camelot_stream")

    metrics = [
        eval_utils.Metric("clean_extraction_rate", round(clean_count / total, 3),
                          {"clean": clean_count, "total": total}, is_primary=True),
        eval_utils.Metric("null_first_row_rate", round(null_first_row_count / total, 3),
                          {"count": null_first_row_count, "total": total}),
        eval_utils.Metric("null_column_rate", round(null_column_count / total, 3),
                          {"count": null_column_count, "total": total}),
        eval_utils.Metric("newline_split_row_rate", round(newline_split_count / total, 3),
                          {"count": newline_split_count, "total": total}),
        eval_utils.Metric("camelot_fallback_rate", round(camelot_fallback_count / total, 3),
                          {"attempted": camelot_fallback_count, "total": total}),
        eval_utils.Metric("camelot_win_rate", round(camelot_win_count / total, 3),
                          {"wins": camelot_win_count, "total": total}),
    ]

    issues = []
    if null_first_row_count > 0:
        affected = [item["file_url"] for item, f in zip(items, flags_by_item) if "null_first_row" in f]
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{null_first_row_count} files have null_first_row",
            affected_count=null_first_row_count,
            affected_ids=affected[:50],
            suggested_upstream_step=STEP,
            suggestion_detail="First row contains null cells — may indicate header detection issues",
            confidence=0.9,
        ))
    if null_column_count > 0:
        affected = [item["file_url"] for item, f in zip(items, flags_by_item) if "null_column" in f]
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{null_column_count} files have null_column",
            affected_count=null_column_count,
            affected_ids=affected[:50],
            suggested_upstream_step=STEP,
            suggestion_detail="A column is entirely null — may indicate extraction alignment issues",
            confidence=0.9,
        ))
    if newline_split_count > 0:
        affected = [item["file_url"] for item, f in zip(items, flags_by_item) if "newline_split_row" in f]
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{newline_split_count} files have newline_split_row",
            affected_count=newline_split_count,
            affected_ids=affected[:50],
            suggested_upstream_step=STEP,
            suggestion_detail="Some rows have only 1 non-null value — may indicate newline-split rows",
            confidence=0.9,
        ))

    quality_by_body = build_quality_by_body(items, process_warning_urls)
    results = eval_utils.EvalResults(step=STEP, metrics=metrics, input_hash=input_hash, judge_model=None)
    return results, issues, quality_by_body


def _load_process_warning_urls(items: list) -> set:
    return {
        item["file_url"]
        for item in items
        if item.get("pdf_multiple_tables") and item.get("file_url")
    }


def _load_camelot_fallback_urls(items: list) -> set:
    return {
        item["file_url"]
        for item in items
        if item.get("pdf_camelot_attempted") and item.get("file_url")
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate transform_disclosure_files PDF extraction quality"
    )
    parser.add_argument("--input-path", dest="input_path", default=str(_HERE / "input.json"))
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
    process_warning_urls = _load_process_warning_urls(items)
    camelot_fallback_urls = _load_camelot_fallback_urls(items)

    results, issues, quality_by_body = run_eval(
        items, process_warning_urls, eval_utils.input_hash(Path(args.input_path)),
        camelot_fallback_urls=camelot_fallback_urls,
    )

    eval_utils.write_eval_outputs(_HERE, results, issues)
    (_HERE / "quality_by_body.json").write_text(json.dumps(quality_by_body, indent=2))

    primary = results.metrics[0]
    print(
        f"{STEP}: clean_extraction_rate={primary.value:.3f} "
        f"({primary.counts['clean']}/{primary.counts['total']} files), "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
