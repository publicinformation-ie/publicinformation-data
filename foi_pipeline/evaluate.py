#!/usr/bin/env python3
"""Top-level pipeline evaluation runner and aggregator.

Discovers steps with eval/evaluate.py, runs only stale ones (mtime contract
identical to process.py), renders a summary table from cached results, and
aggregates upstream issue hypotheses. --headline and baseline gating live in
the same file (Tasks 9 & 10).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from eval import utils as eval_utils

EVAL_INPUT_NAMES = ["evaluate.py", "labels.csv", "judgments.json", "input.json"]


def discover_eval_steps(steps_dir: Path, pipeline_order: list[str]) -> list[str]:
    """Steps that have eval/evaluate.py, returned in pipeline order."""
    return [s for s in pipeline_order
            if (Path(steps_dir) / s / "eval" / "evaluate.py").exists()]


def eval_dependencies(eval_dir: Path) -> list[Path]:
    """Dependency files whose mtime invalidates the cached eval_results.json."""
    eval_dir = Path(eval_dir)
    return [eval_dir / n for n in EVAL_INPUT_NAMES if (eval_dir / n).exists()]


def load_primary_metric(eval_dir: Path):
    """Return (name, value) for the is_primary metric, or (None, None)."""
    results_path = Path(eval_dir) / "eval_results.json"
    if not results_path.exists():
        return None, None
    data = json.loads(results_path.read_text())
    for m in data["metrics"]:
        if m.get("is_primary"):
            return m["name"], m["value"]
    return None, None


def aggregate_issues(steps_dir: Path, steps: list[str]) -> dict:
    """Group issues with a suggested_upstream_step by that step name."""
    grouped: dict[str, list] = {}
    for step in steps:
        issues_path = Path(steps_dir) / step / "eval" / "issues.json"
        if not issues_path.exists():
            continue
        for issue in json.loads(issues_path.read_text()):
            target = issue.get("suggested_upstream_step")
            if target:
                grouped.setdefault(target, []).append({**issue, "_from": step})
    return grouped


def run_step_eval(steps_dir: Path, step: str, pipeline_dir: Path) -> int:
    """Invoke a step's eval/evaluate.py as a subprocess (like process.py)."""
    script = Path(steps_dir) / step / "eval" / "evaluate.py"
    env = {**os.environ, "PYTHONPATH": str(pipeline_dir)}
    return subprocess.run([sys.executable, str(script)], env=env).returncode


def _issue_count(steps_dir: Path, step: str) -> int:
    p = Path(steps_dir) / step / "eval" / "issues.json"
    return len(json.loads(p.read_text())) if p.exists() else 0


def _oldest_result_age(steps_dir: Path, evaluated: list[str]) -> str | None:
    """Return a human-readable age string for the stalest cached eval result."""
    import time
    mtimes = []
    for step in evaluated:
        p = Path(steps_dir) / step / "eval" / "eval_results.json"
        if p.exists():
            mtimes.append(p.stat().st_mtime)
    if not mtimes:
        return None
    oldest = min(mtimes)
    age_secs = time.time() - oldest
    if age_secs < 60:
        return "just now"
    if age_secs < 3600:
        return f"{int(age_secs // 60)}m ago"
    if age_secs < 86400:
        return f"{int(age_secs // 3600)}h ago"
    return f"{int(age_secs // 86400)}d ago"


def render_table(steps_dir: Path, all_steps: list[str], evaluated: list[str]):
    age = _oldest_result_age(steps_dir, evaluated)
    age_str = f"  (results as of: {age})" if age else ""
    print("Pipeline Evaluation  " + "─" * 40 + age_str)
    print(f"{'Step':<40}{'Score':>7}{'Issues':>8}  {'Metric'}")
    for step in all_steps:
        eval_dir = Path(steps_dir) / step / "eval"
        if step not in evaluated:
            print(f"{step:<40}{'—':>7}{'—':>8}  —")
            continue
        name, value = load_primary_metric(eval_dir)
        n_issues = _issue_count(steps_dir, step)
        score = f"{value:.3f}" if value is not None else "—"
        print(f"{step:<40}{score:>7}{n_issues:>8}  {name or '—'}")


def render_upstream(grouped: dict):
    if not grouped:
        return
    print("\nUpstream suggestions " + "─" * 40)
    for target, issues in grouped.items():
        froms = {i["_from"] for i in issues}
        print(f"→ {target} ({len(issues)} suggestions from {len(froms)} steps):")
        for i in issues:
            print(f"    [{i['_from']}]  {i['description']}  (conf {i['confidence']})")


def main(argv=None):
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Run pipeline evaluations")
    parser.add_argument("--force", action="store_true", help="Recompute all evals")
    parser.add_argument("--steps", nargs="+", help="Force just these steps")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--headline", action="store_true", help="Compute north-star metric")
    parser.add_argument("--check", action="store_true", help="Exit non-zero on regression")
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    steps_dir = here / "steps"
    pipeline_order = json.loads((here / "pipeline.json").read_text())["steps"]
    eval_steps = discover_eval_steps(steps_dir, pipeline_order)

    for step in eval_steps:
        eval_dir = steps_dir / step / "eval"
        results_path = eval_dir / "eval_results.json"
        if args.steps and step not in args.steps:
            continue
        forced = args.force or bool(args.steps)
        if not forced and not eval_utils.is_eval_stale(results_path, eval_dependencies(eval_dir)):
            print(f"Skipping {step} eval (up to date)")
            continue
        run_step_eval(steps_dir, step, here)

    render_table(steps_dir, pipeline_order, eval_steps)
    grouped = aggregate_issues(steps_dir, eval_steps)
    render_upstream(grouped)

    # Consolidated root issues.json, grouped by upstream target.
    (here / "eval").mkdir(exist_ok=True)
    (here / "eval" / "issues.json").write_text(json.dumps(grouped, indent=2))

    if args.headline:
        from eval.headline import print_headline  # Task 9
        print_headline(here)
    if args.check or args.update_baseline:
        from eval.baseline import handle_baseline  # Task 10
        return handle_baseline(here, eval_steps, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
