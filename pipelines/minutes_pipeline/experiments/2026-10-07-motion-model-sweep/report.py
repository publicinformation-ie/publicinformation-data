#!/usr/bin/env python3
"""Pareto report for the motion-model-sweep experiment.

Run from minutes_pipeline/ (FULLY OFFLINE - reads Task 5 `results.json`):
    uv run python experiments/2026-10-07-motion-model-sweep/report.py

Prints one row per combo: cost/file, extrapolated full-run $, text-F1,
field accuracy, failure rate, and ΔF1 vs the baseline arm. Combos above a
10% failure rate are flagged DISQUALIFIED regardless of F1 (spec section 8).
The baseline arm (null costs) is excluded from cost ranking, printed last,
and anchors the ΔF1 column. A null field accuracy (zero pairs matched)
renders as "n/a" - never 0.0.

Effort-gradient caveat (Ruling K): every row is `<model>@default` or
`<model>@none`. The effort gradient is not testable on the /go endpoint,
so only default vs thinking-disabled ran (Task 1 probes rounds 1-2 + 1b).
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_RESULTS_JSON = _HERE / "results.json"

#: Spec section 8: combos above this failure rate are disqualified.
FAILURE_DISQUALIFY_RATE = 0.10

#: Printed once per report: the effort gradient is not testable on /go.
GRADIENT_CAVEAT = (
    "Caveat: the effort gradient (low/medium/high/...) is not testable "
    'on the /go endpoint - only default vs thinking-disabled ("none") ran '
    "(Task 1 probes rounds 1-2 + 1b)."
)


def _fmt(value, *, places=4) -> str:
    """Fixed-decimal metric, or "n/a" for null (never 0.0-masquerading)."""
    if value is None:
        return "n/a"
    return f"{value:.{places}f}"


def _fmt_cost(value) -> str:
    if value is None:
        return "n/a"
    return f"${value:.6f}"


def _fmt_extrapolated(value) -> str:
    if value is None:
        return "n/a"
    return f"${value:.2f}"


def report(results: dict) -> None:
    """Print the Pareto table for a Task 5 `results.json` dict to stdout."""
    combos = (results or {}).get("combos") or {}
    if "baseline" not in combos:
        raise ValueError(
            "report: results.json has no 'baseline' combo (need it for ΔF1)")
    baseline = combos["baseline"]
    baseline_f1 = baseline["text_f1"]

    rows = [(key, combos[key]) for key in combos if key != "baseline"]
    # Cost ranking, cheapest first. A null-cost candidate (should not happen -
    # Task 5 raises on missing cost) sorts last, never ahead of a priced row.
    rows.sort(key=lambda kv: (kv[1].get("mean_cost") is None,
                              kv[1].get("mean_cost") or 0.0))

    header = (f"{'combo':<46}{'cost/file':>12}{'x2026 $':>10}"
              f"{'text-F1':>9}{'field-acc':>10}{'fail':>7}{'ΔF1':>9}  status")
    print(header)
    print("-" * len(header))
    for key, m in rows:
        fail = m["failure_rate"]
        status = ("DISQUALIFIED" if fail is not None
                  and fail > FAILURE_DISQUALIFY_RATE else "OK")
        delta = m["text_f1"] - baseline_f1
        print(f"{key:<46}{_fmt_cost(m.get('mean_cost')):>12}"
              f"{_fmt_extrapolated(m.get('extrapolated_2026')):>10}"
              f"{_fmt(m.get('text_f1')):>9}{_fmt(m.get('field_acc')):>10}"
              f"{_fmt(fail):>7}{delta:+.4f}  {status}")
    delta0 = "—"
    bfail = baseline["failure_rate"]
    bstatus = ("DISQUALIFIED" if bfail is not None
               and bfail > FAILURE_DISQUALIFY_RATE else "baseline")
    print(f"{'baseline':<46}{_fmt_cost(baseline.get('mean_cost')):>12}"
          f"{_fmt_extrapolated(baseline.get('extrapolated_2026')):>10}"
          f"{_fmt(baseline.get('text_f1')):>9}"
          f"{_fmt(baseline.get('field_acc')):>10}"
          f"{_fmt(bfail):>7}{delta0:>9}  {bstatus}")
    print(GRADIENT_CAVEAT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print the motion model sweep Pareto table (offline)")
    parser.add_argument("--results", default=str(_RESULTS_JSON))
    args = parser.parse_args()

    results = json.loads(Path(args.results).read_text())
    report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
