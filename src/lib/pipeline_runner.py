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
    parser = argparse.ArgumentParser(description="Pipeline runner")
    parser.add_argument("pipeline_dir", nargs="?", default=".",
                        help="Path to the pipeline directory")
    parser.add_argument("--force", action="store_true", help="Re-run all steps regardless of staleness")
    parser.add_argument("--from", dest="from_step", metavar="STEP", help="Resume from this step")
    parser.add_argument("--stop-on-error", action="store_true", help="Halt pipeline on first non-zero exit code")
    parser.add_argument("--verbose", action="store_true", help="Pass --verbose to each step")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body",
                        help="Scope all steps to this public body ID only")
    args = parser.parse_args()

    pipeline_dir = Path(args.pipeline_dir).resolve()
    config = json.loads((pipeline_dir / "pipeline.json").read_text())
    steps = config["steps"]
    always_run = set(config.get("always_run", []))

    if args.public_body is not None:
        bodies_path = pipeline_dir / "steps" / "find_public_bodies" / "output.json"
        if not bodies_path.exists():
            sys.exit("Error: --public-body requires find_public_bodies/output.json; "
                     "run find_public_bodies first.")
        bodies = json.loads(bodies_path.read_text()).get("public_bodies", [])
        if not any(b.get("public_body_id") == args.public_body for b in bodies):
            sys.exit(f"Error: public body {args.public_body} not found in "
                     f"find_public_bodies/output.json")

    # Pipelines live at <repo_root>/pipelines/<name>/, so repo_root is two levels up
    repo_root = pipeline_dir.parent.parent
    src_path = repo_root / "src"

    skip_until = args.from_step
    prev_out = None

    for step_name in steps:
        # Resolve output path first — needed for both skip_until and execution paths
        if step_name.startswith("/"):
            step_out = repo_root / step_name.lstrip("/") / "output.json"
        else:
            step_out = pipeline_dir / "steps" / step_name / "output.json"

        if skip_until:
            if step_name == skip_until:
                skip_until = None
            else:
                print(f"Skipping {step_name} (before --from {args.from_step})")
                prev_out = step_out
                continue

        # Absolute-path step: validate upstream output, set prev_out, no subprocess
        if step_name.startswith("/"):
            if not step_out.exists() or step_out.stat().st_size == 0:
                parts = Path(step_name).parts
                pipeline_name = parts[2] if len(parts) >= 3 else step_name
                sys.exit(
                    f"upstream step {step_name} has no output — run {pipeline_name} first"
                )
            print(f"Using upstream output from {step_name}")
            prev_out = step_out
            continue

        step_dir = pipeline_dir / "steps" / step_name
        is_from_step = args.from_step is not None and step_name == args.from_step
        if (not args.force and not is_from_step and step_name not in always_run
                and not is_stale(step_out, prev_out)):
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
        if args.verbose:
            cmd.append("--verbose")
        if args.public_body is not None:
            cmd += ["--public-body", str(args.public_body)]

        env = {**os.environ, "PYTHONPATH": f"{pipeline_dir}{os.pathsep}{src_path}"}
        result = subprocess.run(cmd, env=env)

        if result.returncode != 0:
            print(f"Step {step_name} failed with exit code {result.returncode}", file=sys.stderr)
            if args.stop_on_error:
                sys.exit(result.returncode)

        prev_out = step_out


if __name__ == "__main__":
    main()
