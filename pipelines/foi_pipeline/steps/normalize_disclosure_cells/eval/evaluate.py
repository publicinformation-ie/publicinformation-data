#!/usr/bin/env python3
"""Evaluate normalize_disclosure_cells: post-normalization quality and change coverage.

Two complementary measurements:
  1. Post-normalization quality flags (same heuristics as transform_disclosure_files
     eval, applied to the normalized output to confirm that continuation-row merging
     and null-column pruning are working).
  2. Change coverage: fraction of records that received any cell-level changes,
     with rule breakdown from changes.json.

Primary metric: post_normalization_clean_rate (fraction of PDFs with zero flags).

Input: ../output.json (the step's live output; no frozen fixture needed since this
step is a deterministic transformation). Override with --input-path.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_HERE = Path(__file__).parent
_STEP_DIR = _HERE.parent
sys.path.insert(0, str(_HERE.parents[2]))  # steps/normalize_disclosure_cells/eval -> foi_pipeline

from eval import utils as eval_utils

STEP = "normalize_disclosure_cells"

_PREAMBLE_CELL_LEN = 60  # header cells longer than this contain prose, not column labels


def has_null_column(rows):
    """True if any column is missing in some row or all-None in every row."""
    if not rows:
        return False
    ncols = max(len(row) for row in rows)
    for col in range(ncols):
        if any(col >= len(row) for row in rows):
            return True
        if all(row[col] is None for row in rows):
            return True
    return False


def has_newline_split_row(rows):
    """True if any non-header row has exactly 1 non-None cell across >= 3 columns."""
    for row in rows[1:]:
        if len(row) >= 3 and sum(1 for c in row if c is not None) == 1:
            return True
    return False


def has_preamble_in_header(rows):
    """True if any cell in rows[0] is a string longer than _PREAMBLE_CELL_LEN.

    Header column labels are short phrases; prose text merged from preamble
    continuation rows is always much longer. A hit here indicates that
    _merge_continuation_rows absorbed a preamble row into the header.
    """
    if not rows:
        return False
    return any(isinstance(c, str) and len(c) > _PREAMBLE_CELL_LEN for c in rows[0])


def _flag_item(item):
    rows = item.get("rows") or []
    return {
        "null_column": has_null_column(rows),
        "newline_split_row": has_newline_split_row(rows),
        "preamble_in_header": has_preamble_in_header(rows),
    }


def _load_changes(changes_path):
    """Return (changes_by_url, rule_counts).

    changes_by_url: {file_url: set of rules applied}
    rule_counts: Counter of rule -> total cell changes
    """
    if not changes_path.exists():
        return {}, Counter()
    changes = json.loads(changes_path.read_text())
    by_url = defaultdict(set)
    rule_counts = Counter()
    for ch in changes:
        for rule in ch["rules_applied"]:
            by_url[ch["file_url"]].add(rule)
            rule_counts[rule] += 1
    return dict(by_url), rule_counts


def run_eval(items, changes_by_url, rule_counts, input_hash):
    pdf_items = [r for r in items if r.get("file_type") == "pdf" and r.get("rows") is not None]

    total_records = len(items)
    changed = sum(1 for r in items if r.get("file_url") in changes_by_url)
    cells_changed_rate = round(changed / total_records, 3) if total_records else 0.0

    if not pdf_items:
        metrics = [
            eval_utils.Metric("post_normalization_clean_rate", 0.0,
                              {"clean": 0, "total": 0}, is_primary=True),
            eval_utils.Metric("null_column_rate", 0.0, {"flagged": 0, "total": 0}),
            eval_utils.Metric("newline_split_row_rate", 0.0, {"flagged": 0, "total": 0}),
            eval_utils.Metric("cells_changed_rate", cells_changed_rate,
                              {"changed": changed, "total": total_records}),
        ]
        results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                         input_hash=input_hash, judge_model=None)
        return results, []

    clean = 0
    null_col_ids = []
    split_row_ids = []
    preamble_header_ids = []

    for item in pdf_items:
        flags = _flag_item(item)
        if not any(flags.values()):
            clean += 1
        if flags["null_column"]:
            null_col_ids.append(item["file_url"])
        if flags["newline_split_row"]:
            split_row_ids.append(item["file_url"])
        if flags["preamble_in_header"]:
            preamble_header_ids.append(item["file_url"])

    total_pdfs = len(pdf_items)
    metrics = [
        eval_utils.Metric("post_normalization_clean_rate",
                          round(clean / total_pdfs, 3),
                          {"clean": clean, "total": total_pdfs}, is_primary=True),
        eval_utils.Metric("null_column_rate",
                          round(len(null_col_ids) / total_pdfs, 3),
                          {"flagged": len(null_col_ids), "total": total_pdfs}),
        eval_utils.Metric("newline_split_row_rate",
                          round(len(split_row_ids) / total_pdfs, 3),
                          {"flagged": len(split_row_ids), "total": total_pdfs}),
        eval_utils.Metric("preamble_in_header_rate",
                          round(len(preamble_header_ids) / total_pdfs, 3),
                          {"flagged": len(preamble_header_ids), "total": total_pdfs}),
        eval_utils.Metric("cells_changed_rate",
                          cells_changed_rate,
                          {"changed": changed, "total": total_records}),
    ]

    # null_column and newline_split_row are structural PDF-extraction artifacts.
    # They are tracked as metrics for observability but do not belong as issues
    # here: residual nulls are handled by downstream steps, and what remains
    # after normalization is either tolerated or owned by find_disclosure_files.
    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash, judge_model=None)
    return results, []


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate normalize_disclosure_cells post-normalization quality"
    )
    parser.add_argument("--input-path", dest="input_path",
                        default=str(_STEP_DIR / "output.json"),
                        help="Normalized output to evaluate (default: ../output.json)")
    parser.add_argument("--changes-path", dest="changes_path",
                        default=str(_STEP_DIR / "changes.json"))
    args = parser.parse_args()

    input_path = Path(args.input_path)
    data = json.loads(input_path.read_text())
    items = data["results"]
    changes_by_url, rule_counts = _load_changes(Path(args.changes_path))

    results, issues = run_eval(items, changes_by_url, rule_counts,
                               eval_utils.input_hash(input_path))
    eval_utils.write_eval_outputs(_HERE, results, issues)

    primary = results.metrics[0]
    changed_metric = next(m for m in results.metrics if m.name == "cells_changed_rate")
    preamble_metric = next(m for m in results.metrics if m.name == "preamble_in_header_rate")
    top_rules = rule_counts.most_common(3)
    rule_str = ", ".join(f"{r}={n}" for r, n in top_rules) if top_rules else "none"
    print(
        f"{STEP}: clean_rate={primary.value:.3f} "
        f"({primary.counts['clean']}/{primary.counts['total']} clean PDFs), "
        f"preamble_in_header_rate={preamble_metric.value:.3f} "
        f"({preamble_metric.counts['flagged']}/{preamble_metric.counts['total']}), "
        f"cells_changed_rate={changed_metric.value:.3f} "
        f"[{rule_str}], "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
