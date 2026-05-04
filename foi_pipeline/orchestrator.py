#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def is_stale(step_out, prev_out):
    if not step_out.exists():
        return True
    if prev_out is not None and prev_out.exists():
        return prev_out.stat().st_mtime > step_out.stat().st_mtime
    return False


def main():
    parser = argparse.ArgumentParser(description="FOI pipeline orchestrator")
    parser.add_argument("pipeline_dir", help="Path to foi_pipeline/ directory")
    parser.add_argument("--force", action="store_true", help="Re-run all steps regardless of staleness")
    parser.add_argument("--from", dest="from_step", metavar="STEP", help="Resume from this step; earlier steps are skipped")
    parser.add_argument("--stop-on-error", action="store_true", help="Halt pipeline on first non-zero exit code")
    args = parser.parse_args()

    pipeline_dir = Path(args.pipeline_dir)
    config = json.loads((pipeline_dir / "pipeline.json").read_text())
    steps = config["steps"]

    skip_until = args.from_step
    prev_out = None

    for step_name in steps:
        step_dir = pipeline_dir / "steps" / step_name
        step_out = step_dir / "output.json"

        if skip_until:
            if step_name == skip_until:
                skip_until = None
            else:
                print(f"Skipping {step_name} (before --from {args.from_step})")
                prev_out = step_out
                continue

        if not args.force and not is_stale(step_out, prev_out):
            print(f"Skipping {step_name} (up to date)")
            prev_out = step_out
            continue

        cmd = [
            sys.executable,
            str(step_dir / "process.py"),
            "--input", str(prev_out) if prev_out is not None else str(step_dir),
            "--output", str(step_out),
        ]
        if args.force:
            cmd.append("--force")

        env = {**os.environ, "PYTHONPATH": str(pipeline_dir)}
        result = subprocess.run(cmd, env=env)

        if result.returncode != 0:
            print(f"Step {step_name} failed with exit code {result.returncode}", file=sys.stderr)
            if args.stop_on_error:
                sys.exit(result.returncode)

        prev_out = step_out


if __name__ == "__main__":
    main()
