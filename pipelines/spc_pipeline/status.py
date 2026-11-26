#!/usr/bin/env python3
"""Per-meeting funnel for spc_pipeline.

Shows how many records each step produced (in the order `pipeline.json`
declares, including the cross-pipeline local-authority list), the errors each
step recorded, and — for every meeting — which stages it reached and which
errors belong to it. Early steps key on `file_url`; header and later steps key
on `meeting_id`, so the funnel joins them through the header's `source_url`.
A file that never reaches the header stays in the list under its file URL, so
a stall is visible rather than dropped. Read-only: it stats the step outputs
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

STAGE_LABELS = {
    "find_local_authorities": "authorities",
    "find_spc_minutes_files": "discovered",
    "fetch_spc_minutes": "fetched",
    "parse_meeting_header": "header",
    "resolve_attendees": "attendance",
    "render_spc_minutes": "rendered",
    "extract_spc_items": "extracted",
    "export_spc_meetings": "exported",
}


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def step_name(step: str) -> str:
    return step.rstrip("/").rsplit("/", 1)[-1]


def steps_for(pipeline_dir: Path) -> list[tuple[str, str]]:
    """(step reference, stage label) in the order `pipeline.json` declares."""
    config = json.loads((Path(pipeline_dir) / "pipeline.json").read_text())
    return [
        (step, STAGE_LABELS.get(step_name(step), step_name(step)))
        for step in config["steps"]
    ]


def step_dir(pipeline_dir: Path, step: str) -> Path:
    """A step's directory; a leading `/` is repo-relative, as the runner reads it."""
    if step.startswith("/"):
        repo_root = Path(pipeline_dir).resolve().parent.parent
        return repo_root / step.lstrip("/")
    return Path(pipeline_dir) / "steps" / step


def records_for(pipeline_dir: Path, step: str):
    data = load_json(step_dir(pipeline_dir, step) / "output.json")
    if data is None:
        return None
    results = data.get("results", data)
    if isinstance(results, dict):  # export stores its tables in a dict
        return results.get("meetings", [])
    return results or []


def errors_for(pipeline_dir: Path, step: str) -> list[dict]:
    data = load_json(step_dir(pipeline_dir, step) / "errors.json")
    return data if isinstance(data, list) else []


def _url_index(loaded: list[tuple]) -> dict[str, str]:
    """Map every printed source URL to the meeting id the header assigned it."""
    index: dict[str, str] = {}
    for _step, _label, records, _errors in loaded:
        for record in records:
            meeting_id = record.get("meeting_id")
            if not meeting_id:
                continue
            for field in ("source_url", "file_url"):
                url = record.get(field)
                if url:
                    index[url] = meeting_id
    return index


def _entry(meetings: dict[str, dict], key: str,
           meeting_ids: set[str]) -> dict:
    entry = meetings.setdefault(key, {
        "meeting_id": key if key in meeting_ids else None,
        "file_url": None if key in meeting_ids else key,
        "stages": [],
        "last_stage": None,
        "errors": [],
        "error_count": 0,
    })
    return entry


def _record_key(record: dict, url_to_meeting: dict[str, str]):
    meeting_id = record.get("meeting_id")
    if meeting_id:
        return meeting_id
    for field in ("file_url", "source_url", "page_url"):
        url = record.get(field)
        if url:
            return url_to_meeting.get(url, url)
    return None


def _error_key(error: dict, url_to_meeting: dict[str, str]):
    context = error.get("context") or {}
    meeting_id = context.get("meeting_id") or error.get("meeting_id")
    if meeting_id:
        return meeting_id
    for field in ("file_url", "source_url", "page_url"):
        url = context.get(field) or error.get(field)
        if url:
            return url_to_meeting.get(url, url)
    return None


def funnel(pipeline_dir: Path = PIPELINE_DIR) -> dict:
    pipeline_dir = Path(pipeline_dir)
    try:
        steps = steps_for(pipeline_dir)
    except (OSError, ValueError, KeyError):
        return {"error": "pipeline.json is missing or unreadable", "rows": []}

    loaded: list[tuple[str, str, list[dict], list[dict]]] = []
    rows: list[dict] = []
    for step, label in steps:
        records = records_for(pipeline_dir, step)
        if records is None:
            return {
                "error": f"{step_name(step)} output.json is missing or unreadable",
                "rows": rows,
            }
        errors = errors_for(pipeline_dir, step)
        loaded.append((step, label, records, errors))
        rows.append({"step": step_name(step), "stage": label,
                     "count": len(records), "errors": len(errors)})

    url_to_meeting = _url_index(loaded)
    meeting_ids = {record["meeting_id"] for _s, _l, records, _e in loaded
                   for record in records if record.get("meeting_id")}

    meetings: dict[str, dict] = {}
    for step, label, records, errors in loaded:
        for record in records:
            key = _record_key(record, url_to_meeting)
            if key is None:
                continue  # the authority list is not a meeting
            entry = _entry(meetings, key, meeting_ids)
            url = record.get("file_url") or record.get("source_url")
            if url and entry["file_url"] is None:
                entry["file_url"] = url
            if label not in entry["stages"]:
                entry["stages"].append(label)
            entry["last_stage"] = label
        for error in errors:
            key = _error_key(error, url_to_meeting)
            if key is None:
                continue
            entry = _entry(meetings, key, meeting_ids)
            entry["errors"].append({
                "step": step_name(step),
                "error_type": error.get("error_type"),
                "error_message": error.get("error_message"),
            })
            entry["error_count"] = len(entry["errors"])

    return {"rows": rows, "meetings": list(meetings.values())}


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
        rows = [[row["step"], row["stage"], str(row["count"]), str(row["errors"])]
                for row in status["rows"]]
        widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
        for cells in [headers, *rows]:
            print("  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip())
        print()
        for line in status["verdict"]:
            print(line)
        warnings = [meeting for meeting in status["meetings"] if meeting["errors"]]
        if warnings:
            print()
            for meeting in warnings:
                name = meeting["meeting_id"] or meeting["file_url"]
                rendered = ", ".join(sorted({error["error_type"] for error in meeting["errors"]}))
                print(f"  {name}: {meeting['error_count']} error(s) — {rendered}")
    return 0 if status["rows"] and status["rows"][-1]["count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
