#!/usr/bin/env python3
"""Print comparison table from experiment result files.

Run from minutes_pipeline/:
    uv run python experiments/2026-09-15-minutes-page-discovery/report.py
"""
import json
from pathlib import Path

_HERE = Path(__file__).parent
_RESULTS = _HERE / "results"
APPROACHES = ["baseline", "one_hop", "two_hop", "apify_rerank"]


def _latest(approach):
    files = sorted(_RESULTS.glob(f"{approach}_*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text())


def main():
    results = {a: _latest(a) for a in APPROACHES}
    if all(v is None for v in results.values()):
        print("No result files found in results/. Run run_experiment.py first.")
        raise SystemExit(1)
    baseline = results.get("baseline")
    print(f"  {'Approach':<12}  {'P':>6}  {'R':>6}  {'F1':>6}  "
          f"{'TP':>4}  {'FP':>4}  {'FN':>4}  {'TN':>4}  {'ΔF1':>7}")
    print("  " + "-" * 70)
    for approach in APPROACHES:
        data = results[approach]
        if data is None:
            print(f"  {approach:<12}  (no results)")
            continue
        m = data["metrics"]
        delta = ""
        if baseline and approach != "baseline":
            delta = f"  Δf1={m['f1'] - baseline['metrics']['f1']:+.3f}"
        c = m["counts"]
        print(f"  {approach:<12}  {m['precision']:.3f}  {m['recall']:.3f}  "
              f"{m['f1']:.3f}  {c['TP']:4d}  {c['FP']:4d}  {c['FN']:4d}  "
              f"{c['TN']:4d}{delta}")


if __name__ == "__main__":
    main()
