#!/usr/bin/env python3
"""Extract the three-column project tables from every cached document.

Each page is gated structurally before any of its rows are used: a page whose
table has the wrong number of columns, or rows that vary in width beyond the
tolerance this document family needs, yields no rows and is recorded as an
error naming the page and the failed checks. A single imperfect cell never
rejects a page — cell text is repaired (or reported) further down the chain.

Pages belong to one of two parts of a document: the per-recipient summary in
the front matter (`recipient_summary`) or the project tables (`project_table`).
A page with no header of its own keeps the part of the page before it, which is
how a table that runs over a page break stays whole.
"""
import argparse
import sys
from pathlib import Path

import pdfplumber
from allocations import (
    PIPELINE_DIR, PROJECT_TABLE_HEADER, SUMMARY_TABLE_HEADER,
    alnum, carried, classify_row, make_error, normalise, now_iso, scope,
)
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status
from lib.table_structure import Thresholds, score_table

STEP_NAME = "extract_grant_tables"
STEP_DIR = Path(__file__).parent

# The structural gate. Width uniformity is deliberately loose: this document
# family legitimately has pages where a total row ends a block (two cells) next
# to full three-column rows. The column count is the check that catches a
# layout change, because it is what the rest of the pipeline is written against.
GATE_THRESHOLDS = Thresholds(
    min_width_uniformity=0.4,
    max_fragment_share=1.0,
    min_column_type_purity=0.0,
    max_split_word_rate=1.0,
    min_rows=1,
    max_role_contamination=1.0,
    min_anchored_row_share=0.0,
)


def gate_page(raw_rows: list[list]) -> dict:
    """Apply the structural gate to one page's raw table rows."""
    rows = [[normalise(cell) for cell in row] for row in raw_rows]
    checks = {"rows": len(rows)}
    if not rows:
        return {"accepted": False, "failed_checks": ["no_table"], "checks": checks}

    widths = [len(row) for row in rows]
    checks["max_columns"] = max(widths)
    checks["min_columns"] = min(widths)
    failed = []
    if checks["max_columns"] > 3 or checks["min_columns"] < 2:
        failed.append("column_count")

    score = score_table([list(row) for row in rows])
    checks["width_uniformity"] = round(score.width_uniformity, 3)
    checks["modal_width"] = score.modal_width
    checks["composite"] = round(score.composite, 3)
    if len(rows) >= 2 and score.width_uniformity < GATE_THRESHOLDS.min_width_uniformity:
        failed.append("width_uniformity")

    return {"accepted": not failed, "failed_checks": failed, "checks": checks}


def page_part(raw_rows: list[list]) -> str | None:
    """`project_table`, `recipient_summary`, or None when the page has no header."""
    for row in raw_rows:
        kind, detail = classify_row([normalise(cell) for cell in row])
        if kind != "column_header":
            continue
        label = alnum(detail["label"])
        if label == PROJECT_TABLE_HEADER:
            return "project_table"
        if label == SUMMARY_TABLE_HEADER:
            return "recipient_summary"
    return None


def extract_document(entry: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (page records, project-table rows, summary rows) for one document."""
    pages: list[dict] = []
    rows: list[dict] = []
    summary_rows: list[dict] = []
    path = PIPELINE_DIR / entry["cache_file"]
    part: str | None = None

    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                pages.append({
                    "document_id": entry["document_id"], "year": entry["year"],
                    "page": page_number, "part": part, "accepted": False,
                    "failed_checks": ["no_text"],
                })
                continue

            raw_rows = page.extract_table() or []
            gate = gate_page(raw_rows)
            declared_part = page_part(raw_rows)
            if declared_part is not None:
                part = declared_part

            pages.append({
                "document_id": entry["document_id"], "year": entry["year"],
                "page": page_number, "part": part,
                "accepted": gate["accepted"],
                "failed_checks": gate["failed_checks"],
                **gate["checks"],
            })
            if not gate["accepted"]:
                continue

            for row_index, raw in enumerate(raw_rows):
                cells = [normalise(cell) for cell in raw][:3]
                cells += [""] * (3 - len(cells))
                row = {
                    "document_id": entry["document_id"],
                    "year": entry["year"],
                    "page": page_number,
                    "row_index": row_index,
                    "part": part,
                    "cells": cells,
                }
                if part == "recipient_summary":
                    summary_rows.append(row)
                else:
                    rows.append(row)
    return pages, rows, summary_rows


def run(input_data: dict, document: str | None = None) -> tuple[dict, list[dict]]:
    documents = scope(input_data.get("documents", []), document)
    pages: list[dict] = []
    rows: list[dict] = []
    summary_rows: list[dict] = []
    errors: list[dict] = []

    for entry in documents:
        if not entry.get("available"):
            continue  # fetch_grant_documents already reported why
        if "project_table" not in entry["kinds"] and "recipient_summary" not in entry["kinds"]:
            continue  # a programme_summary is cached, never extracted as project rows
        document_pages, document_rows, document_summary_rows = extract_document(entry)
        pages.extend(document_pages)
        rows.extend(document_rows)
        summary_rows.extend(document_summary_rows)

        for page in document_pages:
            if page["accepted"]:
                continue
            if page["failed_checks"] == ["no_text"]:
                errors.append(make_error(
                    STEP_NAME, "PageHasNoText",
                    f"{entry['document_id']} page {page['page']} has no text layer",
                    document_id=entry["document_id"], year=entry["year"],
                    page=page["page"],
                ))
            else:
                errors.append(make_error(
                    STEP_NAME, "TableStructureUnreliable",
                    f"{entry['document_id']} page {page['page']} failed the structural gate",
                    document_id=entry["document_id"], year=entry["year"],
                    page=page["page"], failed_checks=page["failed_checks"],
                ))

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "documents": len(documents),
            "pages": len(pages),
            "pages_accepted": sum(1 for p in pages if p["accepted"]),
            "rows": len(rows),
            "summary_rows": len(summary_rows),
        },
        **carried(input_data),
        "documents": input_data.get("documents", []),
        "pages": pages,
        "rows": rows,
        "summary_rows": summary_rows,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract the NTA allocation project tables")
    add_common_args(parser)
    add_doc_arg(parser)
    args = parser.parse_args()

    try:
        input_data = read_json(args.input)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Fatal: could not read input: {exc}")

    output, errors = run(input_data, document=args.doc)

    errors_path = STEP_DIR / "errors.json"
    if errors_path.exists():
        errors_path.unlink()
    if errors:
        append_errors(STEP_DIR, errors)

    write_json(args.output, output)
    write_status(STEP_DIR, len(output["rows"]))
    print(f"Extracted {len(output['rows'])} rows from "
          f"{output['metadata']['pages_accepted']}/{output['metadata']['pages']} pages")


if __name__ == "__main__":
    main()
