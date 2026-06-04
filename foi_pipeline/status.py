#!/usr/bin/env python3
"""Pipeline status report — shows completion times, record counts, staleness, and errors."""
import json
from datetime import datetime, timezone
from pathlib import Path


def fmt_time(iso: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M")


def fmt_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def main():
    pipeline_dir = Path(__file__).parent
    pipeline_json = pipeline_dir / "pipeline.json"
    steps = json.loads(pipeline_json.read_text())["steps"]

    rows = []
    prev_out_mtime = None

    for step_name in steps:
        step_dir = pipeline_dir / "steps" / step_name
        out = step_dir / "output.json"
        ps_path = step_dir / "pipeline-status.json"
        err_path = step_dir / "errors.json"

        completed_at = None
        record_count = None
        if ps_path.exists():
            ps = json.loads(ps_path.read_text())
            completed_at = ps.get("completed_at")
            record_count = ps.get("record_count")

        out_mtime = out.stat().st_mtime if out.exists() else None

        stale = False
        if out_mtime is not None and prev_out_mtime is not None:
            stale = prev_out_mtime > out_mtime

        error_count = 0
        if err_path.exists():
            try:
                errors = json.loads(err_path.read_text())
                error_count = len(errors) if isinstance(errors, list) else 0
            except Exception:
                pass

        rows.append({
            "name": step_name,
            "completed": completed_at,
            "records": record_count,
            "stale": stale,
            "has_output": out.exists(),
            "errors": error_count,
        })

        if out_mtime is not None:
            prev_out_mtime = out_mtime

    # Header
    name_w = max(len(r["name"]) for r in rows)
    print(f"\n{'STEP':<{name_w}}  {'COMPLETED':<16}  {'RECORDS':>9}  {'STALE':>5}  {'ERRORS':>6}")
    print("-" * (name_w + 2 + 16 + 2 + 9 + 2 + 5 + 2 + 6))

    stale_count = 0
    total_errors = 0
    missing_count = 0

    for r in rows:
        name = r["name"]
        completed = fmt_time(r["completed"]) if r["completed"] else "—"
        records = fmt_size(r["records"]) if r["records"] is not None else "—"
        stale_marker = " !!!" if r["stale"] else ""
        missing_marker = " (no output)" if not r["has_output"] else ""
        errors = str(r["errors"]) if r["errors"] else ""

        flags = stale_marker + missing_marker
        print(f"{name:<{name_w}}  {completed:<16}  {records:>9}  {'yes' if r['stale'] else 'no':>5}  {errors:>6}{flags}")

        if r["stale"]:
            stale_count += 1
        if not r["has_output"]:
            missing_count += 1
        total_errors += r["errors"]

    print()
    issues = []
    if stale_count:
        issues.append(f"{stale_count} stale step(s)")
    if missing_count:
        issues.append(f"{missing_count} step(s) missing output")
    if total_errors:
        issues.append(f"{total_errors} total errors across steps")

    if issues:
        print("Issues: " + ", ".join(issues))
    else:
        print("All steps up to date, no errors.")

    if total_errors > 0:
        print()
        print("Steps with errors:")
        for r in rows:
            if r["errors"]:
                print(f"  {r['name']}: {r['errors']} error(s)")

    print()


if __name__ == "__main__":
    main()
