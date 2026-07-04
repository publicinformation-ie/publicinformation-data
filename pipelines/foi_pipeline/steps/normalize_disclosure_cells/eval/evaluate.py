#!/usr/bin/env python3
"""Evaluate normalize_disclosure_cells: cell-level change coverage.

Row-structure flags (null columns, leaked split rows, preamble-in-header) now
live in filter_phantom_rows/eval, since row-structure repair moved to that
step. This eval keeps only the cell-level measurement: change coverage,
i.e. the fraction of records that received any cell-level changes, with rule
breakdown from changes.json.

Primary metric: cells_changed_rate.

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
    total_records = len(items)
    changed = sum(1 for r in items if r.get("file_url") in changes_by_url)
    cells_changed_rate = round(changed / total_records, 3) if total_records else 0.0

    metrics = [
        eval_utils.Metric("cells_changed_rate", cells_changed_rate,
                          {"changed": changed, "total": total_records}, is_primary=True),
    ]
    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash, judge_model=None)
    return results, []


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate normalize_disclosure_cells change coverage"
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
    top_rules = rule_counts.most_common(3)
    rule_str = ", ".join(f"{r}={n}" for r, n in top_rules) if top_rules else "none"
    print(
        f"{STEP}: cells_changed_rate={primary.value:.3f} "
        f"({primary.counts['changed']}/{primary.counts['total']} records changed) "
        f"[{rule_str}], "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
