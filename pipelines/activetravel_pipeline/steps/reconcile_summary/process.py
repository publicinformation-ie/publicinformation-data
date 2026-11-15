#!/usr/bin/env python3
"""Check extracted totals against the document's own per-recipient summary.

The 2025 and 2026 editions open with a table listing one total per recipient.
Each of those totals is compared with the active-travel total the project tables
yielded for the same recipient; a recipient that disagrees has its active-travel
records withheld and is reported. The 2022 Annex 1 is a *programme* budget view
(€289.0m across A3.1–A3.4 by GDA/regional/rural split) and has no per-recipient
counterpart in the project tables, so it is skipped rather than compared —
comparing the two would produce a permanent false failure.

The 2026 BSEP column is excluded: it is a body-level allocation with no
project-level counterpart in the table, so it cannot be reconciled and is not
published as a project allocation.
"""
import argparse
import sys
from pathlib import Path

from allocations import (
    alias_key, carried, classify_row, load_recipient_aliases, make_error, now_iso,
    parse_amount, scope,
)
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "reconcile_summary"
STEP_DIR = Path(__file__).parent

SKIP_ANCHOR_KINDS = ("blank", "column_header", "anchor")
COMPARED_STREAM = "active_travel"


def parse_summary(summary_rows: list[dict], aliases: dict) -> tuple[dict, list[dict]]:
    """Return (declared per recipient, excluded lines) for one document."""
    declared: dict[str, dict] = {}
    excluded: list[dict] = []

    for row in summary_rows:
        cells = row["cells"]
        kind, detail = classify_row(cells)
        if kind in SKIP_ANCHOR_KINDS:
            continue
        label = cells[0]
        recipient = aliases.get(alias_key(label)) if label else None
        if recipient is None:
            excluded.append({
                "label": label, "page": row["page"],
                "reason": "not a recipient section (aggregate or non-tabulated line)",
            })
            continue
        if recipient["kind"] != "local_authority":
            excluded.append({
                "label": label, "page": row["page"], "recipient": recipient["canonical"],
                "reason": "non-local-authority line aggregates blocks with no "
                          "project-level counterpart; not comparable",
            })
            continue
        parsed = parse_amount(cells[1])
        declared[recipient["canonical"]] = {
            "amount_eur": parsed["value"],
            "error": parsed["error"],
            "label": label,
            "page": row["page"],
        }
    return declared, excluded


def run(input_data: dict, document: str | None = None,
        aliases: dict | None = None) -> tuple[dict, list[dict]]:
    aliases = load_recipient_aliases() if aliases is None else aliases
    documents = scope(input_data.get("documents", []), document)
    rows = scope(input_data.get("rows", []), document)
    sections = [s for s in input_data.get("sections", [])
                if document is None or s["document_id"] == document]
    summary_rows = scope(input_data.get("summary_rows", []), document)
    withheld: list[dict] = list(input_data.get("withheld_rows", []))
    errors: list[dict] = []
    comparisons: list[dict] = []
    skipped: list[dict] = []
    withheld_streams: set[tuple[str, str]] = set()

    for entry in documents:
        document_id = entry["document_id"]
        if "recipient_summary" not in entry["kinds"]:
            skipped.append({
                "document_id": document_id,
                "reason": ("programme budget view, not a per-recipient summary"
                           if "programme_summary" in entry["kinds"]
                           else "document carries no per-recipient summary"),
            })
            continue

        doc_summary_rows = [r for r in summary_rows if r["document_id"] == document_id]
        declared, excluded = parse_summary(doc_summary_rows, aliases)

        for recipient_name, item in declared.items():
            section = next((s for s in sections
                            if s["document_id"] == document_id
                            and s.get("recipient_name") == recipient_name), None)
            if section is None:
                errors.append(make_error(
                    STEP_NAME, "SummaryMismatch",
                    f"{document_id}: summary lists {recipient_name} but no project table was extracted",
                    document_id=document_id, year=entry["year"], recipient=recipient_name,
                    declared_eur=item["amount_eur"],
                ))
                continue

            active = next((s for s in section.get("streams", [])
                           if s["funding_stream"] == COMPARED_STREAM), None)
            if active is None:
                continue  # the section failed section reconciliation and was reported there
            if COMPARED_STREAM in section.get("withheld_streams", []):
                continue  # already reported by reconcile_sections

            extracted = active["extracted_eur"]
            if item["error"] is not None:
                reasons = [f"summary amount for {recipient_name} could not be read"]
            else:
                comparisons.append({
                    "document_id": document_id, "recipient": recipient_name,
                    "declared_eur": item["amount_eur"], "extracted_eur": extracted,
                })
                if extracted == item["amount_eur"]:
                    continue
                reasons = [
                    f"summary declares {item['amount_eur']:,} for {recipient_name} "
                    f"but the extracted active-travel rows add up to {extracted:,}"
                ]

            withheld_streams.add((section["section_id"], COMPARED_STREAM))
            for row in rows:
                if (row.get("section_id") == section["section_id"]
                        and row.get("funding_stream") == COMPARED_STREAM):
                    withheld.append({**row, "withheld_reason": "SummaryMismatch"})
            errors.append(make_error(
                STEP_NAME, "SummaryMismatch",
                f"{document_id}: " + "; ".join(reasons),
                document_id=document_id, year=entry["year"], recipient=recipient_name,
                declared_eur=item["amount_eur"], extracted_eur=extracted,
                reasons=reasons,
            ))

    withheld_row_ids = {id(row) for row in withheld}
    kept = [row for row in rows
            if id(row) not in withheld_row_ids
            and (row.get("section_id"), row.get("funding_stream")) not in withheld_streams]

    sections_out = []
    for section in sections:
        extra = [stream for (section_id, stream) in withheld_streams
                 if section_id == section["section_id"]]
        withheld_here = list(section.get("withheld_streams", []))
        for stream in extra:
            if stream not in withheld_here:
                withheld_here.append(stream)
        for stream in section.get("streams", []):
            if stream["funding_stream"] in extra:
                stream["reconciled"] = False
                stream["reasons"] = [
                    "per-recipient summary disagrees with the extracted active-travel rows"
                ]
        sections_out.append({**section, "withheld_streams": withheld_here,
                             "withheld": bool(withheld_here)})

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "rows": len(kept),
            "withheld_rows": len(withheld),
            "comparisons": len(comparisons),
            "documents_skipped": len(skipped),
        },
        **carried(input_data),
        "rows": kept,
        "withheld_rows": withheld,
        "sections": sections_out,
        "summary_comparisons": comparisons,
        "summary_skipped": skipped,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile the per-recipient summary tables")
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
    print(f"Checked {output['metadata']['comparisons']} summary totals, "
          f"{len(output['rows'])} rows remain")


if __name__ == "__main__":
    main()
