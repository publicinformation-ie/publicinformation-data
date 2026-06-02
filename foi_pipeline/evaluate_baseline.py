#!/usr/bin/env python3
"""Baseline recording and regression gate.

A primary metric is a regression only if it drops more than `tolerance` below
baseline AND the current input_hash matches the baseline's (else we are not
comparing the same data, so the gate stays silent). Headline numbers must hold
or rise — they are the anchor of truth.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TOLERANCE = 0.02


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "unknown"


def collect_current(pipeline_dir: Path, steps: list[str]) -> dict:
    """Read each step's cached eval_results.json -> {step: {name, value, input_hash}}."""
    steps_dir = Path(pipeline_dir) / "steps"
    current = {}
    for step in steps:
        rp = steps_dir / step / "eval" / "eval_results.json"
        if not rp.exists():
            continue
        data = json.loads(rp.read_text())
        primary = next((m for m in data["metrics"] if m.get("is_primary")), None)
        if primary:
            current[step] = {"name": primary["name"], "value": primary["value"],
                             "input_hash": data["input_hash"]}
    return current


def find_regressions(baseline: dict, current: dict, tolerance=DEFAULT_TOLERANCE):
    """Return [(step, metric, baseline_value, current_value)] for true regressions."""
    out = []
    base_steps = baseline.get("steps", {})
    for step, cur in current.items():
        bstep = base_steps.get(step, {}).get(cur["name"])
        if not bstep:
            continue
        if bstep["input_hash"] != cur["input_hash"]:
            continue  # different data -> not comparable
        if bstep["value"] - cur["value"] > tolerance:
            out.append((step, cur["name"], bstep["value"], cur["value"]))
    return out


def headline_regressed(baseline: dict, current_headline: dict) -> bool:
    base = baseline.get("headline", {})
    for key in ("valid_records", "bodies_with_record"):
        if key in base and key in current_headline and current_headline[key] < base[key]:
            return True
    return False


def handle_baseline(pipeline_dir: Path, steps: list[str], args) -> int:
    pipeline_dir = Path(pipeline_dir)
    baseline_path = pipeline_dir / "baseline.json"
    current = collect_current(pipeline_dir, steps)

    from evaluate_headline import print_headline
    current_headline, current_funnel = print_headline(pipeline_dir)

    if args.update_baseline:
        baseline = {
            "steps": {s: {c["name"]: {"value": c["value"], "input_hash": c["input_hash"],
                                      "recorded_at": datetime.now(timezone.utc).isoformat(),
                                      "commit": _git_commit()}}
                      for s, c in current.items()},
            "headline": {"valid_records": current_headline["valid_records"],
                         "bodies_with_record": current_headline["bodies_with_record"]},
            "funnel": current_funnel,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2))
        print(f"Baseline updated -> {baseline_path}")
        return 0

    if args.check:
        baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
        regressions = find_regressions(baseline, current)
        h_reg = headline_regressed(baseline, current_headline)
        for step, metric, was, now in regressions:
            print(f"REGRESSION {step}.{metric}: {was:.3f} -> {now:.3f}")
        if h_reg:
            print("REGRESSION headline numbers dropped below baseline")
        return 1 if (regressions or h_reg) else 0
    return 0
