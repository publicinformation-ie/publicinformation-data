#!/usr/bin/env python3
"""Per-meeting funnel for spc_pipeline.

Shows how many meetings survive each stage (discovered → fetched → header →
attendance → rendered → extracted → exported), the errors recorded per step,
and a verdict naming the first dry step. Read-only: it stats the step outputs
and never imports or runs a step.

Usage (from the repo root):
    uv run python pipelines/spc_pipeline/status.py
    uv run python pipelines/spc_pipeline/status.py --json

Exit codes: 0 = at least one meeting exported, 1 = the pipeline runs dry,
2 = a step output is missing or unreadable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent

STEPS = [
    ("find_spc_minutes_files", "discovered"),
    ("fetch_spc_minutes", "fetched"),
    ("parse_meeting_header", "header"),
    ("resolve_attendees", "attendance"),
    ("render_spc_minutes", "rendered"),
    ("extract_spc_items", "extracted"),
    ("export_spc_meetings", "exported"),
]


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def records_for(pipeline_dir: Path, step: str):
    data = load_json(pipeline_dir / "steps" / step / "output.json")
    if data is None:
        return None
    results = data.get("results", data)
    if isinstance(results, dict):  # export stores its tables in a dict
        return results.get("meetings", [])
    return results or []


def errors_for(pipeline_dir: Path, step: str) -> list[dict]:
    data = load_json(pipeline_dir / "steps" / step / "errors.json")
    return data if isinstance(data, list) else []


def meeting_key(step: str, record: dict) -> str:
    return record.get("meeting_id") or record.get("file_url") or "?"


def funnel(pipeline_dir: Path = PIPELINE_DIR) -> dict:
    rows = []
    active: dict[str, dict] = {}
    for step, label in STEPS:
        records = records_for(pipeline_dir, step)
        errors = errors_for(pipeline_dir, step)
        if records is None:
            return {"error": f"{step}/output.json is missing or unreadable", "rows": rows}
        rows.append({"step": step, "label": label, "count": len(records),
                     "errors": len(errors)})
        for record in records:
            key = meeting_key(step, record)
            entry = active.setdefault(key, {"meeting": key, "stages": {},
                                            "errors": 0})
            entry["stages"][label] = True

    # A meeting is identified by its id from parse_meeting_header onward; the
    # earlier steps carry file URLs, so match them by prefix in the id.
    return {"rows": rows, "meetings": list(active.values())}


def verdict(status: dict) -> list[str]:
    rows = status["rows"]
    lines = []
    previous = None
    for row in rows:
        if row["count"] == 0 and (previous is None or previous > 0):
            lines.append(f"Runs dry at: {row['step']} (0 records — fix here first)")
            break
        previous = row["count"]
    else:
        exported = rows[-1]["count"] if rows else 0
        if exported:
            lines.append(f"Flowing end to end: {exported} meeting(s) exported.")
    errors = [(row["step"], row["errors"]) for row in rows if row["errors"]]
    for step, count in errors:
        lines.append(f"Errors: {step} has {count} entr{'y' if count == 1 else 'ies'} in errors.json")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-meeting funnel for spc_pipeline")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    status = funnel(PIPELINE_DIR)
    if "error" in status:
        print(f"error: {status['error']}", file=sys.stderr)
        return 2
    status["verdict"] = verdict(status)

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        headers = ["STEP", "STAGE", "RECORDS", "ERRORS"]
        rows = [[row["step"], row["label"], str(row["count"]), str(row["errors"])]
                for row in status["rows"]]
        widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
        for cells in [headers, *rows]:
            print("  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip())
        print()
        for line in status["verdict"]:
            print(line)
    return 0 if status["rows"] and status["rows"][-1]["count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
