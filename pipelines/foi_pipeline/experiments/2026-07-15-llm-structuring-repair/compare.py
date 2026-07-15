#!/usr/bin/env python3
"""Scoring + aggregation for the llm-structuring-repair experiment.

Reads arms.json (Task 4) + ground_truth.json and writes results.json:
structural repair/regression, per-field fidelity, value-fidelity violations,
invented/dropped rows, and aggregated + extrapolated cost.

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-llm-structuring-repair/compare.py
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
if str(_FOI_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.eval.evaluate import (  # noqa: E402
    has_null_first_row,
    has_null_column,
    has_newline_split_row,
)

_ARMS = _HERE / "arms.json"
_GROUND_TRUTH = _HERE / "ground_truth.json"
_RESULTS = _HERE / "results.json"

FULL_TAIL_FILES = 323
PRICE_INPUT_PER_1M_USD = 0.5
PRICE_OUTPUT_PER_1M_USD = 1.5


def _load_schema():
    path = _HERE / "schema.py"
    spec = importlib.util.spec_from_file_location("llm_repair_schema", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_schema = _load_schema()
entries_to_rows = _schema.entries_to_rows
CANONICAL_FIELDS = _schema.CANONICAL_FIELDS

_PREDICATES = {
    "null_first_row": has_null_first_row,
    "null_column": has_null_column,
    "newline_split_row": has_newline_split_row,
}


def flags_for_rows(rows) -> set:
    if not rows:
        return set()
    return {name for name, fn in _PREDICATES.items() if fn(rows)}


def repair_stats(records: list) -> dict:
    broken = 0
    repaired = 0
    regressions = []
    per_pred = {name: {"broken": 0, "repaired": 0} for name in _PREDICATES}

    for rec in records:
        a_flags = flags_for_rows(rec.get("arm_a_rows"))
        b_entries = rec.get("arm_b_entries")
        is_failure = not b_entries
        b_rows = entries_to_rows(b_entries or [])
        b_flags = flags_for_rows(b_rows)

        if a_flags:
            broken += 1
            for name in a_flags:
                per_pred[name]["broken"] += 1
            if not is_failure and not (a_flags & b_flags):  # none of A's predicates persist
                repaired += 1
                for name in a_flags:
                    per_pred[name]["repaired"] += 1

        if not is_failure and (b_flags - a_flags):  # arm B trips something arm A did not
            regressions.append(rec["file_url"])

    return {
        "broken": broken,
        "repaired": repaired,
        "repair_rate": round(repaired / broken, 3) if broken else 0.0,
        "regressions": regressions,
        "per_predicate": per_pred,
    }


def norm_value(v) -> str:
    if v is None:
        return ""
    return " ".join(str(v).split())


def _ref_key(entry: dict) -> str:
    return norm_value(entry.get("foi_reference_id")).lower()


def _fallback_key(entry: dict) -> tuple:
    return (
        norm_value(entry.get("date_received")).lower(),
        norm_value(entry.get("request_description")).lower()[:40],
    )


def match_rows(arm_b: list, gt: list) -> list:
    """Deterministically align arm-B rows to ground-truth rows."""
    unmatched_b = set(range(len(arm_b)))
    pairs = []
    matched_gt = set()

    # Pass 1: exact non-empty reference id.
    for gi, g in enumerate(gt):
        gk = _ref_key(g)
        if not gk:
            continue
        for bi in sorted(unmatched_b):
            if _ref_key(arm_b[bi]) == gk:
                pairs.append((bi, gi))
                unmatched_b.discard(bi)
                matched_gt.add(gi)
                break

    # Pass 2: (date, description-prefix) fallback for still-unmatched GT.
    for gi, g in enumerate(gt):
        if gi in matched_gt:
            continue
        gk = _fallback_key(g)
        if gk == ("", ""):
            continue
        for bi in sorted(unmatched_b):
            if _fallback_key(arm_b[bi]) == gk:
                pairs.append((bi, gi))
                unmatched_b.discard(bi)
                matched_gt.add(gi)
                break

    for gi in range(len(gt)):
        if gi not in matched_gt:
            pairs.append((None, gi))
    for bi in sorted(unmatched_b):
        pairs.append((bi, None))
    return pairs


def fidelity_scores(arm_b: list, gt: list) -> dict:
    per_field = {
        f: {"tp": 0, "fp": 0, "fn": 0} for f in CANONICAL_FIELDS
    }
    violations = 0
    invented = 0
    dropped = 0

    for bi, gi in match_rows(arm_b, gt):
        if bi is None:  # dropped GT row: every non-empty GT field is a miss.
            dropped += 1
            for f in CANONICAL_FIELDS:
                if norm_value(gt[gi].get(f)):
                    per_field[f]["fn"] += 1
            continue
        if gi is None:  # invented arm-B row: every non-empty field is a false +.
            invented += 1
            for f in CANONICAL_FIELDS:
                if norm_value(arm_b[bi].get(f)):
                    per_field[f]["fp"] += 1
            continue
        for f in CANONICAL_FIELDS:
            gv = norm_value(gt[gi].get(f))
            bv = norm_value(arm_b[bi].get(f))
            if gv and bv and gv == bv:
                per_field[f]["tp"] += 1
            else:
                if gv:
                    per_field[f]["fn"] += 1
                if bv:
                    per_field[f]["fp"] += 1
                if gv and bv:  # both present but differ -> altered value
                    violations += 1

    for f in CANONICAL_FIELDS:
        c = per_field[f]
        denom_p = c["tp"] + c["fp"]
        denom_r = c["tp"] + c["fn"]
        c["precision"] = round(c["tp"] / denom_p, 3) if denom_p else 0.0
        c["recall"] = round(c["tp"] / denom_r, 3) if denom_r else 0.0

    return {
        "per_field": per_field,
        "value_fidelity_violations": violations,
        "invented_rows": invented,
        "dropped_rows": dropped,
    }


def cost_aggregate(records: list) -> dict:
    costed = [r for r in records if r.get("tokens") and r.get("cost_usd") is not None]
    n = len(costed)
    totals = {"prompt": 0, "completion": 0, "total": 0}
    total_cost = 0.0
    for r in costed:
        for k in totals:
            totals[k] += r["tokens"][k]
        total_cost += r["cost_usd"]
    total_cost = round(total_cost, 6)
    mean_cost = round(total_cost / n, 6) if n else 0.0
    mean_tokens = {k: round(totals[k] / n, 1) if n else 0.0 for k in totals}
    return {
        "files_costed": n,
        "total_tokens": totals,
        "mean_tokens_per_file": mean_tokens,
        "total_cost_usd": total_cost,
        "mean_cost_per_file_usd": mean_cost,
        "full_tail_files": FULL_TAIL_FILES,
        "extrapolated_full_tail_usd": round(mean_cost * FULL_TAIL_FILES, 2),
    }


def build_results(records: list, ground_truth: dict) -> dict:
    by_url = {r["file_url"]: r for r in records}

    fidelity_files = []
    totals = {"value_fidelity_violations": 0, "invented_rows": 0, "dropped_rows": 0}
    for file_url, gt_entries in ground_truth.items():
        rec = by_url.get(file_url)
        arm_b = (rec.get("arm_b_entries") if rec else None) or []
        scores = fidelity_scores(arm_b, gt_entries)
        fidelity_files.append({"file_url": file_url, "scores": scores})
        for k in totals:
            totals[k] += scores[k]

    failures = [
        {"file_url": r["file_url"], "error": r["error"]}
        for r in records if r.get("error")
    ]

    return {
        "structural": repair_stats(records),
        "cost": cost_aggregate(records),
        "fidelity": {"files": fidelity_files, "totals": totals},
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the llm-repair experiment")
    parser.add_argument("--arms", default=str(_ARMS))
    parser.add_argument("--ground-truth", default=str(_GROUND_TRUTH))
    args = parser.parse_args()

    records = json.loads(Path(args.arms).read_text())["records"]
    gt_raw = json.loads(Path(args.ground_truth).read_text())
    ground_truth = gt_raw.get("files", gt_raw) if isinstance(gt_raw, dict) else {}

    results = build_results(records, ground_truth)
    _RESULTS.write_text(json.dumps(results, indent=2))

    s = results["structural"]
    c = results["cost"]
    t = results["fidelity"]["totals"]
    print(f"Structural: {s['repaired']}/{s['broken']} repaired "
          f"(rate={s['repair_rate']}), {len(s['regressions'])} regressions")
    print(f"Cost: ${c['total_cost_usd']} over {c['files_costed']} files; "
          f"full-tail extrapolation ${c['extrapolated_full_tail_usd']}")
    print(f"Fidelity: {t['value_fidelity_violations']} altered values, "
          f"{t['invented_rows']} invented, {t['dropped_rows']} dropped rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
