#!/usr/bin/env python3
"""report.py — print comparison table from experiment result files.

Run from foi_pipeline/:
    uv run python experiments/2026-06-09-disclosure-page-discovery/report.py
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_RESULTS = _HERE / "results"


def _latest(approach: str) -> dict | None:
    """Return the most recent result JSON for an approach, or None."""
    files = sorted(_RESULTS.glob(f"{approach}_*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text())


def _row(approach: str, data: dict | None, baseline_metrics: dict | None, slice_key: str) -> str:
    if data is None:
        return f"  {approach:<10}  {'(no results)':>55}"
    m = data["metrics"][slice_key]
    delta = ""
    if baseline_metrics:
        bm = baseline_metrics[slice_key]
        df1 = m["f1"] - bm["f1"]
        delta = f"  Δf1={df1:+.3f}"
    c = m["counts"]
    return (
        f"  {approach:<10}  "
        f"P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}  "
        f"TP={c['TP']:3d}  FP={c['FP']:3d}  FN={c['FN']:3d}  TN={c['TN']:3d}"
        f"{delta}"
    )


def main():
    approaches = ["baseline", "a", "c1", "c2", "ac1", "ac2"]
    results = {a: _latest(a) for a in approaches}

    if all(v is None for v in results.values()):
        print("No result files found in results/. Run run_experiment.py first.")
        sys.exit(1)

    baseline = results.get("baseline")

    for slice_key, label in [
        ("target_slice", "13-council target slice"),
        ("all_labelled", "All labelled bodies"),
    ]:
        print(f"\n── {label} ──")
        print(
            f"  {'Approach':<10}  "
            f"{'Precision':>9}  {'Recall':>7}  {'F1':>6}  "
            f"{'TP':>5}  {'FP':>5}  {'FN':>5}  {'TN':>5}  {'Delta':>8}"
        )
        print("  " + "-" * 75)
        for approach in approaches:
            print(_row(approach, results[approach], baseline, slice_key))


if __name__ == "__main__":
    main()
