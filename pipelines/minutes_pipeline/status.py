#!/usr/bin/env python3
"""Per-public-body pipeline status — funnel view for troubleshooting dry bodies.

Walks one authority through every minutes_pipeline step and reports how many
of its records survive each stage, plus that body's errors per step. The goal
is to pinpoint rapidly where the pipeline runs dry for a body so it can be
fixed (missing minutes page, no files found, empty text extraction, null
motions, unresolved dates, ...). `--all` instead prints a bodies x steps
matrix to evaluate a rollout across all authorities.

Usage (from the repo root):
    uv run python pipelines/minutes_pipeline/status.py --public-body 1456
    uv run python pipelines/minutes_pipeline/status.py --all
    uv run python pipelines/minutes_pipeline/status.py --all --csv

Exit codes: 0 = body flows end to end (>=1 motion exported; always 0 for
--all unless a data error occurs), 1 = pipeline runs dry for the body,
2 = usage/data error.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return "—"


def resolve_body(authorities, ref: str):
    """Match a --public-body ref (id or slug) to (id, name, slug)."""
    ref = ref.strip()
    for a in authorities:
        if not isinstance(a, dict):
            continue
        if str(a.get("public_body_id")) == ref or (a.get("slug") or "").lower() == ref.lower():
            return a.get("public_body_id"), a.get("name"), a.get("slug")
    return None


def body_records(results, body_id) -> list:
    if not isinstance(results, list):
        return []
    return [r for r in results
            if isinstance(r, dict) and str(r.get("public_body_id")) == str(body_id)]


def body_errors(errors, body_id) -> list:
    if not isinstance(errors, list):
        return []
    out = []
    for e in errors:
        if not isinstance(e, dict):
            continue
        ctx = e.get("context") or {}
        if str(ctx.get("public_body_id")) == str(body_id):
            out.append(e)
    return out


def non_empty_text(rec: dict) -> bool:
    return bool((rec.get("text") or "").strip())


def summarize_step(step_name: str, records: list) -> tuple:
    """Return (count, detail) for one step's body records."""
    n = len(records)
    if step_name == "find_local_authorities":
        detail = ""
        if records:
            r = records[0]
            districts = r.get("municipal_districts") or []
            detail = f"website={'set' if r.get('official_website_url') else 'MISSING'}, districts={len(districts)}"
        return n, detail
    if step_name == "find_meeting_minutes_pages":
        return n, ""
    if step_name == "find_minutes_files":
        return n, ""
    if step_name == "transform_minutes_files":
        empty = sum(1 for r in records if not non_empty_text(r))
        return n, f"empty_text={empty}" if n else ""
    if step_name == "ocr_minutes_files":
        return n, ""
    if step_name == "extract_motions":
        nulls = sum(1 for r in records if r.get("motions") is None)
        total = sum(len(r["motions"]) for r in records if isinstance(r.get("motions"), list))
        return n, f"motions_null={nulls}, motions_extracted={total}" if n else ""
    if step_name == "resolve_meeting_date":
        unresolved = sum(1 for r in records if not r.get("meeting_date"))
        return n, f"date_unresolved={unresolved}" if n else ""
    if step_name in ("canonicalize_motions", "export_motions"):
        return n, "motions" if n else ""
    return n, ""


def diagnose(rows: list) -> list:
    """Verdict lines: first dry step plus notable drop-offs between stages."""
    verdicts = []
    counts = {r["name"]: r["count"] for r in rows if r["has_output"]}
    for r in rows:
        if r["has_output"] and r["count"] == 0:
            verdicts.append(f"Runs dry at: {r['name']} "
                            f"(0 records for this body — fix here first)")
            break
    else:
        if counts.get("export_motions", 0) > 0:
            verdicts.append(f"Flowing end to end: "
                            f"{counts['export_motions']} motion(s) exported.")
    drops = [
        ("find_minutes_files", "transform_minutes_files", "files never transformed"),
        ("transform_minutes_files", "extract_motions", "transformed files never motion-extracted"),
        ("extract_motions", "canonicalize_motions", "extracted files yielding zero canonical motions"),
        ("canonicalize_motions", "export_motions", "canonical motions never exported"),
    ]
    for upstream, downstream, label in drops:
        if upstream in counts and downstream in counts:
            lost = counts[upstream] - counts[downstream]
            # extract_motions counts files while canonicalize counts motions,
            # so only flag a total wipeout there, not a partial drop.
            if lost > 0 and (upstream != "extract_motions" or counts[downstream] == 0):
                verdicts.append(f"Drop-off: {upstream}={counts[upstream]} -> "
                                f"{downstream}={counts[downstream]} ({label})")
    return verdicts


def collect_status(pipeline_dir: Path, body_ref: str):
    """Gather per-step rows for a body. Returns (header, rows) or raises ValueError."""
    steps, step_data, authorities = _load_pipeline(pipeline_dir)
    match = resolve_body(authorities, body_ref)
    if match is None:
        known = [f"{a.get('public_body_id')}/{a.get('slug')}"
                 for a in authorities if isinstance(a, dict)]
        raise ValueError(f"Unknown public body '{body_ref}'. Known: {', '.join(known)}")
    body_id, name, slug = match
    return (body_id, name, slug), _rows_for_body(steps, step_data, body_id)


def _load_pipeline(pipeline_dir: Path):
    """Load step names, each step's output/errors (once), and the authority list.

    Returns (steps, step_data, authorities). step_data maps step name to
    {"results": [...], "completed": iso|None, "has_output": bool, "errors": [...]}.
    Raises ValueError when pipeline.json or the authority list is unreadable.
    """
    pipeline_json = pipeline_dir / "pipeline.json"
    config = load_json(pipeline_json)
    if not config or "steps" not in config:
        raise ValueError(f"Cannot read steps from {pipeline_json}")
    steps = config["steps"]
    repo_root = pipeline_dir.parent.parent

    auth_path = pipeline_dir / "steps" / "find_local_authorities" / "output.json"
    auth_data = load_json(auth_path)
    if not auth_data:
        raise ValueError(f"Missing {auth_path}; run find_local_authorities first.")
    authorities = auth_data.get("results", [])

    step_data = {}
    for step_name in steps:
        step_dir = (repo_root / step_name.lstrip("/")) if step_name.startswith("/") \
            else (pipeline_dir / "steps" / step_name)
        out = load_json(step_dir / "output.json")
        ps = load_json(step_dir / "pipeline-status.json")
        errors = load_json(step_dir / "errors.json")
        step_data[step_name] = {
            "results": (out or {}).get("results", []),
            "completed": (ps or {}).get("completed_at"),
            "has_output": out is not None,
            "errors": errors if isinstance(errors, list) else [],
        }
    return steps, step_data, authorities


def _rows_for_body(steps: list, step_data: dict, body_id) -> list:
    rows = []
    for step_name in steps:
        data = step_data[step_name]
        records = body_records(data["results"], body_id)
        count, detail = summarize_step(step_name, records)
        rows.append({
            "name": step_name,
            "has_output": data["has_output"],
            "count": count,
            "detail": detail,
            "completed": data["completed"],
            "errors": body_errors(data["errors"], body_id),
        })
    return rows


def collect_all(pipeline_dir: Path):
    """Gather per-step rows for every authority. Returns (steps, [(header, rows), ...])."""
    steps, step_data, authorities = _load_pipeline(pipeline_dir)
    bodies = []
    for a in authorities:
        if not isinstance(a, dict) or a.get("public_body_id") is None:
            continue
        header = (a.get("public_body_id"), a.get("name"), a.get("slug"))
        bodies.append((header, _rows_for_body(steps, step_data, a.get("public_body_id"))))
    return steps, bodies


# Short column labels for --all matrix mode (full names in single-body mode).
SHORT_LABELS = {
    "find_local_authorities": "auth",
    "find_meeting_minutes_pages": "pages",
    "find_minutes_files": "files",
    "transform_minutes_files": "text",
    "ocr_minutes_files": "ocr",
    "extract_motions": "extract",
    "resolve_meeting_date": "dates",
    "canonicalize_motions": "canon",
    "export_motions": "export",
}


def short_label(step_name: str) -> str:
    return SHORT_LABELS.get(step_name, step_name)


def dry_step(rows: list):
    """Short label of the first zero-record step, 'flowing', or None if undetermined."""
    for r in rows:
        if r["has_output"] and r["count"] == 0:
            return short_label(r["name"])
    if any(r["has_output"] for r in rows):
        return "flowing"
    return None


def error_breakdown(errors: list, limit: int = 3) -> list:
    by_type: dict = {}
    for e in errors:
        by_type.setdefault(e.get("error_type", "?"), []).append(e)
    lines = []
    for etype, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        example = (items[0].get("context") or {}).get("file_url") \
            or (items[0].get("context") or {}).get("url") \
            or items[0].get("error_message", "")[:100]
        lines.append(f"{etype} x{len(items)} e.g. {example}")
        for extra in items[1:limit]:
            ctx = extra.get("context") or {}
            lines.append(f"    e.g. {ctx.get('file_url') or ctx.get('url') or ''}")
    return lines


def matrix_rows(steps: list, bodies: list) -> list:
    """Flatten collect_all output to matrix rows: (id, slug, [counts], errs, dry)."""
    out = []
    for (body_id, _name, slug), rows in bodies:
        by_name = {r["name"]: r for r in rows}
        counts = [str(by_name[s]["count"]) if by_name[s]["has_output"] else "-"
                  for s in steps]
        errs = sum(len(r["errors"]) for r in rows)
        out.append((body_id, slug, counts, errs, dry_step(rows)))
    return out


def print_matrix(steps: list, bodies: list, csv: bool = False) -> None:
    labels = [short_label(s) for s in steps]
    rows = matrix_rows(steps, bodies)
    if csv:
        print("id,slug," + ",".join(labels) + ",errs,dry_at")
        for body_id, slug, counts, errs, dry in rows:
            print(f"{body_id},{slug}," + ",".join(counts) + f",{errs},{dry}")
        return
    id_w = max([2] + [len(str(b[0])) for b in rows])
    slug_w = max([4] + [len(str(b[1] or "")) for b in rows])
    col_w = [max(len(lb), max((len(c[i]) for _, _, c, _, _ in rows), default=1))
             for i, lb in enumerate(labels)]
    header = (f"{'ID':>{id_w}}  {'SLUG':<{slug_w}}  "
              + "  ".join(f"{lb:>{w}}" for lb, w in zip(labels, col_w))
              + f"  {'ERRS':>4}  DRY_AT")
    print(header)
    print("-" * len(header))
    for body_id, slug, counts, errs, dry in rows:
        line = (f"{body_id:>{id_w}}  {(slug or ''):<{slug_w}}  "
                + "  ".join(f"{c:>{w}}" for c, w in zip(counts, col_w))
                + f"  {errs:>4}  {dry}")
        print(line)
    print(f"\n{len(rows)} bodies. Column labels: "
          + ", ".join(f"{short_label(s)}={s}" for s in steps))


def main(argv=None, pipeline_dir=None) -> int:
    parser = argparse.ArgumentParser(description="Minutes pipeline status")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--public-body",
                       help="Public body id (or slug) to inspect")
    group.add_argument("--all", action="store_true",
                       help="Matrix of all bodies x steps with record counts")
    parser.add_argument("--csv", action="store_true",
                        help="With --all: emit CSV instead of a table")
    args = parser.parse_args(argv)

    if pipeline_dir is None:
        pipeline_dir = Path(__file__).parent

    if args.all:
        try:
            steps, bodies = collect_all(pipeline_dir)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print_matrix(steps, bodies, csv=args.csv)
        return 0

    try:
        (body_id, name, slug), rows = collect_status(pipeline_dir, args.public_body)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"\nBody {body_id} — {name} ({slug})")
    name_w = max(len(r["name"]) for r in rows)
    print(f"\n{'STEP':<{name_w}}  {'BODY_RECS':>9}  {'COMPLETED':<16}  {'BODY_ERRS':>9}  DETAIL")
    print("-" * (name_w + 9 + 16 + 9 + 8 + 30))
    for r in rows:
        completed = fmt_time(r["completed"]) if r["completed"] else "—"
        count = str(r["count"]) if r["has_output"] else "no output"
        errs = str(len(r["errors"])) if r["errors"] else ""
        print(f"{r['name']:<{name_w}}  {count:>9}  {completed:<16}  {errs:>9}  {r['detail']}")

    with_errors = [r for r in rows if r["errors"]]
    if with_errors:
        print("\nErrors for this body:")
        for r in with_errors:
            print(f"  {r['name']}:")
            for line in error_breakdown(r["errors"]):
                print(f"    {line}")

    print()
    verdicts = diagnose(rows)
    dry = any(r["has_output"] and r["count"] == 0 for r in rows)
    for v in verdicts:
        print(v)
    print()
    return 1 if dry else 0


if __name__ == "__main__":
    sys.exit(main())
