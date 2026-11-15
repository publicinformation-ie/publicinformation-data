#!/usr/bin/env python3
"""Per-document pipeline status — funnel view for troubleshooting dry documents.

Walks one annual document through every step and reports how many project rows
survive each stage, plus that document's errors per step. The goal is to
pinpoint rapidly where the pipeline runs dry for a document (no cached PDF, a
page rejected by the structural gate, unreadable amounts, unresolved recipients,
a section withheld at reconciliation, ...). `--all` prints a documents x steps
matrix.

Usage (from the repo root):
    uv run python pipelines/activetravel_pipeline/status.py --all
    uv run python pipelines/activetravel_pipeline/status.py --document 2026
    uv run python pipelines/activetravel_pipeline/status.py --all --csv

Exit codes: 0 = the document flows end to end (at least one allocation
exported), 1 = the pipeline runs dry for it, 2 = usage/data error.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STEP_DIR_KEYS = {
    "fetch_grant_documents": "documents",
    "extract_grant_tables": "rows",
    "classify_grant_rows": "rows",
    "normalize_grant_amounts": "rows",
    "segment_funding_streams": "rows",
    "resolve_recipients": "rows",
    "reconcile_sections": "rows",
    "reconcile_summary": "rows",
    "canonicalize_allocations": "results",
    "export_allocations": "results",
}

SHORT_LABELS = {
    "fetch_grant_documents": "fetch",
    "extract_grant_tables": "extract",
    "classify_grant_rows": "classify",
    "normalize_grant_amounts": "amounts",
    "segment_funding_streams": "streams",
    "resolve_recipients": "recipient",
    "reconcile_sections": "reconcile",
    "reconcile_summary": "summary",
    "canonicalize_allocations": "canon",
    "export_allocations": "export",
}


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


def _project_rows(output: dict) -> list[dict]:
    """The project rows a step carried, ignoring structural rows."""
    rows = output.get("results") or output.get("rows") or []
    return [r for r in rows if isinstance(r, dict) and r.get("kind", "project") == "project"]


def _document_of(record: dict, year_to_document: dict[int, str]) -> str | None:
    if record.get("document_id"):
        return record["document_id"]
    year = record.get("year")
    if isinstance(year, int):
        return year_to_document.get(year)
    return None


def document_errors(errors, document_id: str) -> list[dict]:
    out = []
    for error in errors if isinstance(errors, list) else []:
        context = error.get("context") or {}
        if context.get("document_id") == document_id:
            out.append(error)
    return out


def summarize_step(step_name: str, output: dict | None, document_id: str,
                   year_to_document: dict[int, str]) -> tuple[int, str]:
    """Return (count, detail) of one step's records for one document."""
    if output is None:
        return 0, ""
    if step_name == "fetch_grant_documents":
        entry = next((d for d in output.get("documents", [])
                      if d.get("document_id") == document_id), None)
        if entry is None:
            return 0, "not declared in publications.json"
        if not entry.get("available"):
            return 0, f"unavailable: {entry.get('error') or 'fetch failed'}"
        return 1, f"{entry.get('source')}, {entry.get('byte_size')} bytes"
    if step_name == "extract_grant_tables":
        rows = [r for r in output.get("rows", []) if r.get("document_id") == document_id]
        summary_rows = [r for r in output.get("summary_rows", [])
                        if r.get("document_id") == document_id]
        pages = [p for p in output.get("pages", []) if p.get("document_id") == document_id]
        accepted = sum(1 for p in pages if p.get("accepted"))
        return len(rows), (f"pages={len(pages)}, accepted={accepted}, "
                           f"summary_rows={len(summary_rows)}")
    if step_name == "export_allocations":
        results = [r for r in output.get("results", [])
                   if _document_of(r, year_to_document) == document_id]
        total = sum(r.get("allocation_eur") or 0 for r in results)
        return len(results), f"€{total:,}"

    rows = [r for r in _project_rows(output)
            if _document_of(r, year_to_document) == document_id]
    detail = ""
    if step_name == "classify_grant_rows":
        unknown = [r for r in output.get("unknown_rows", [])
                   if r.get("document_id") == document_id]
        detail = f"unknown_rows={len(unknown)}" if unknown else ""
    elif step_name == "normalize_grant_amounts":
        withheld = [r for r in output.get("withheld_rows", [])
                    if r.get("document_id") == document_id]
        detail = f"amount_withheld={len(withheld)}" if withheld else ""
    elif step_name in ("segment_funding_streams", "resolve_recipients", "reconcile_sections"):
        sections = [s for s in output.get("sections", [])
                    if s.get("document_id") == document_id]
        withheld = sum(1 for s in sections if s.get("withheld"))
        detail = f"sections={len(sections)}, withheld={withheld}" if sections else ""
    elif step_name == "reconcile_summary":
        compared = [c for c in output.get("summary_comparisons", [])
                    if c.get("document_id") == document_id]
        detail = f"summary_compared={len(compared)}" if compared else ""
    elif step_name == "canonicalize_allocations":
        provisional = sum(1 for r in rows if r.get("project_code_provisional"))
        detail = f"provisional={provisional}" if provisional else ""
    return len(rows), detail


def _load_pipeline(pipeline_dir: Path):
    config = load_json(pipeline_dir / "pipeline.json")
    if not config or "steps" not in config:
        raise ValueError(f"Cannot read steps from {pipeline_dir / 'pipeline.json'}")

    fetch = load_json(pipeline_dir / "steps/fetch_grant_documents/output.json")
    if not fetch:
        raise ValueError("Missing steps/fetch_grant_documents/output.json; run the pipeline first.")
    documents = [{"document_id": d["document_id"], "year": d["year"],
                  "kinds": d.get("kinds", [])} for d in fetch.get("documents", [])]
    # Published records carry the year, not the document id. The extractable
    # document is the one with project tables (the 2022 Annex shares its year).
    year_to_document = {
        document["year"]: document["document_id"] for document in documents
        if "project_table" in document["kinds"]
    }

    step_data = {}
    for step_name in config["steps"]:
        step_dir = pipeline_dir / "steps" / step_name
        output = load_json(step_dir / "output.json")
        status = load_json(step_dir / "pipeline-status.json")
        errors = load_json(step_dir / "errors.json")
        step_data[step_name] = {
            "output": output,
            "completed": (status or {}).get("completed_at"),
            "errors": errors if isinstance(errors, list) else [],
        }
    return config["steps"], step_data, documents, year_to_document


def rows_for_document(steps, step_data, document_id, year_to_document) -> list[dict]:
    rows = []
    for step_name in steps:
        data = step_data[step_name]
        count, detail = summarize_step(step_name, data["output"], document_id, year_to_document)
        rows.append({
            "name": step_name,
            "has_output": data["output"] is not None,
            "count": count,
            "detail": detail,
            "completed": data["completed"],
            "errors": document_errors(data["errors"], document_id),
        })
    return rows


def dry_step(rows: list[dict]) -> str | None:
    """Short label of the first zero-record step, 'flowing', or None."""
    for row in rows:
        if row["has_output"] and row["count"] == 0 and row["name"] != "reconcile_summary":
            return SHORT_LABELS.get(row["name"], row["name"])
    if any(row["has_output"] for row in rows):
        return "flowing"
    return None


def error_breakdown(errors: list[dict], limit: int = 3) -> list[str]:
    by_type: dict[str, list[dict]] = {}
    for error in errors:
        by_type.setdefault(error.get("error_type", "?"), []).append(error)
    lines = []
    for error_type, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        example = (items[0].get("context") or {}).get("page")
        message = items[0].get("error_message", "")[:110]
        lines.append(f"{error_type} x{len(items)} e.g. page {example}: {message}")
        for extra in items[1:limit]:
            lines.append(f"    e.g. page {(extra.get('context') or {}).get('page')}")
    return lines


def print_document(document_id: str, rows: list[dict]) -> None:
    print(f"\nDocument {document_id}")
    width = max(len(row["name"]) for row in rows)
    print(f"\n{'STEP':<{width}}  {'RECORDS':>8}  {'COMPLETED':<16}  {'ERRORS':>6}  DETAIL")
    print("-" * (width + 8 + 16 + 6 + 8 + 40))
    for row in rows:
        completed = fmt_time(row["completed"]) if row["completed"] else "—"
        count = str(row["count"]) if row["has_output"] else "no output"
        errors = str(len(row["errors"])) if row["errors"] else ""
        print(f"{row['name']:<{width}}  {count:>8}  {completed:<16}  {errors:>6}  {row['detail']}")

    with_errors = [row for row in rows if row["errors"]]
    if with_errors:
        print("\nErrors for this document:")
        for row in with_errors:
            print(f"  {row['name']}:")
            for line in error_breakdown(row["errors"]):
                print(f"    {line}")


def print_matrix(steps, documents, all_rows, csv: bool = False) -> None:
    labels = [SHORT_LABELS.get(step, step) for step in steps]
    if csv:
        print("document," + ",".join(labels) + ",errs,dry_at")
        for document, rows in all_rows:
            counts = {row["name"]: row for row in rows}
            cells = [str(counts[step]["count"]) if counts[step]["has_output"] else "-"
                     for step in steps]
            errs = sum(len(row["errors"]) for row in rows)
            print(f"{document['document_id']}," + ",".join(cells) + f",{errs},{dry_step(rows)}")
        return

    document_width = max([10] + [len(document["document_id"]) for document, _ in all_rows])
    column_widths = [max(len(label), 7) for label in labels]
    header = (f"{'DOCUMENT':<{document_width}}  "
              + "  ".join(f"{label:>{width}}" for label, width in zip(labels, column_widths))
              + f"  {'ERRS':>4}  DRY_AT")
    print(header)
    print("-" * len(header))
    for document, rows in all_rows:
        if not document["extractable"]:
            print(f"{document['document_id']:<{document_width}}  "
                  + "  ".join(f"{'-':>{width}}" for width in column_widths)
                  + f"  {sum(len(row['errors']) for row in rows):>4}  "
                  "not extracted (programme summary)")
            continue
        counts = {row["name"]: row for row in rows}
        cells = [str(counts[step]["count"]) if counts[step]["has_output"] else "-"
                 for step in steps]
        errs = sum(len(row["errors"]) for row in rows)
        print(f"{document['document_id']:<{document_width}}  "
              + "  ".join(f"{cell:>{width}}" for cell, width in zip(cells, column_widths))
              + f"  {errs:>4}  {dry_step(rows)}")
    print(f"\n{len(all_rows)} documents. Column labels: "
          + ", ".join(f"{label}={step}" for label, step in zip(labels, steps)))


def main(argv=None, pipeline_dir=None) -> int:
    parser = argparse.ArgumentParser(description="Active Travel allocations pipeline status")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--document", help="Document id or year (e.g. 2026)")
    group.add_argument("--all", action="store_true",
                       help="Matrix of all documents x steps with record counts")
    parser.add_argument("--csv", action="store_true", help="With --all: emit CSV")
    args = parser.parse_args(argv)

    if pipeline_dir is None:
        pipeline_dir = Path(__file__).parent

    try:
        steps, step_data, documents, year_to_document = _load_pipeline(pipeline_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    for document in documents:
        document["extractable"] = ("project_table" in document["kinds"]
                                   or "recipient_summary" in document["kinds"])

    if args.all:
        all_rows = [(document, rows_for_document(
            steps, step_data, document["document_id"], year_to_document))
            for document in documents]
        print_matrix(steps, documents, all_rows, csv=args.csv)
        return 0

    wanted = args.document.strip()
    match = next((document for document in documents
                  if document["document_id"] == wanted or str(document["year"]) == wanted), None)
    if match is None:
        known = ", ".join(f"{document['document_id']} ({document['year']})"
                          for document in documents)
        print(f"Error: unknown document {wanted!r}. Known: {known}", file=sys.stderr)
        return 2

    if not match["extractable"]:
        print(f"\nDocument {match['document_id']} is a programme summary "
              f"({', '.join(match['kinds'])}): cached for provenance, never extracted "
              "as project rows and never compared with the project tables.")
        return 0

    rows = rows_for_document(steps, step_data, match["document_id"], year_to_document)
    print_document(match["document_id"], rows)

    dry = any(row["has_output"] and row["count"] == 0 and row["name"] != "reconcile_summary"
              for row in rows)
    print()
    verdict = dry_step(rows)
    if dry:
        print(f"Runs dry at: {verdict} (0 records for this document — fix here first)")
    elif verdict == "flowing":
        exported = next(row for row in rows if row["name"] == "export_allocations")
        print(f"Flowing end to end: {exported['count']} allocation(s) exported.")
    print()
    return 1 if dry else 0


if __name__ == "__main__":
    sys.exit(main())
