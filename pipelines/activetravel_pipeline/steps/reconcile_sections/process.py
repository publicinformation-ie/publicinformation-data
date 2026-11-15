#!/usr/bin/env python3
"""Publish a recipient's funding stream only when the document's arithmetic confirms it.

For each recipient *and* funding stream, the rows that would be published must
add up to the total the document declares for that stream. A block whose own
subtotal is printed must add up to that subtotal too. Any difference — one euro
is a difference — withholds that stream's rows and reports the recipient, the
stream, both sums and the delta.

That buys one guarantee instead of a partial one: **anything published is
complete for its recipient, year and stream, and adds up.** A recipient whose
active-travel block reconciles keeps it even when the document's other-NTA-
funding-streams block is short of printed rows; only the stream that failed is
withheld.

A blocked stream is recovered by a committed `row_repairs.json` entry, keyed by
document, page and row. `set_amount` repairs are applied by the amount step;
`drop_row` repairs are applied here, for a row the source really prints twice
(or prints as a duplicate of a row it already carries). Every applied repair is
reported.
"""
import argparse
import sys
from pathlib import Path

from allocations import carried, load_row_repairs, make_error, now_iso, scope
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "reconcile_sections"
STEP_DIR = Path(__file__).parent


def _sum(rows: list[dict]) -> int:
    return sum(row.get("amount_eur") or 0 for row in rows)


def _declared(anchor: dict | None):
    if anchor is None:
        return None
    return anchor.get("amount_eur")


def split_streams(section: dict, rows: list[dict]) -> dict:
    """Work out what the document declares for each funding stream.

    A block's own subtotal is the declared figure when it is printed; a block
    with no printed subtotal takes what is left of the section total after the
    blocks that were declared. If more than one block is undeclared, or the
    declared blocks already exceed the section total, the Section cannot be
    split and the whole section is withheld.
    """
    blocks = []
    for block in section["blocks"]:
        block_rows = [r for r in rows
                      if r.get("block_index") == block["block_index"]]
        blocks.append({
            "block_index": block["block_index"],
            "funding_stream": block["funding_stream"],
            "row_count": len(block_rows),
            "extracted_eur": _sum(block_rows),
            "declared_eur": _declared(block.get("declared")),
            "declared_page": (block.get("declared") or {}).get("page"),
        })

    section_total = _declared(section.get("section_total"))
    problems: list[str] = []
    if section.get("section_total") is None:
        problems.append("section has no declared total")
    elif section_total is None:
        problems.append("declared section total could not be read")

    undeclared = [b for b in blocks if b["declared_eur"] is None]
    if section_total is not None:
        if len(undeclared) > 1:
            problems.append(
                f"{len(undeclared)} blocks have no printed subtotal, so the section "
                "total cannot be split between them"
            )
        elif len(undeclared) == 1:
            remainder = section_total - sum(
                b["declared_eur"] for b in blocks if b["declared_eur"] is not None)
            if remainder < 0:
                problems.append(
                    "the declared subtotals exceed the declared section total"
                )
            else:
                undeclared[0]["declared_eur"] = remainder
                undeclared[0]["derived"] = True
        else:
            declared_sum = sum(b["declared_eur"] for b in blocks)
            if declared_sum > section_total:
                problems.append(
                    f"the declared subtotals add up to {declared_sum:,} but the "
                    f"document declares {section_total:,} for the section"
                )
            elif declared_sum < section_total:
                # Money declared for a stream with no printed project rows: the
                # remainder belongs to the other-NTA-streams block and is
                # withheld on its own rather than taking the section with it.
                blocks.append({
                    "block_index": len(blocks),
                    "funding_stream": "other_nta_streams",
                    "row_count": 0,
                    "extracted_eur": 0,
                    "declared_eur": section_total - declared_sum,
                    "declared_page": (section.get("section_total") or {}).get("page"),
                    "derived": True,
                })

    streams: dict[str, dict] = {}
    for block in blocks:
        stream = streams.setdefault(block["funding_stream"], {
            "funding_stream": block["funding_stream"],
            "extracted_eur": 0,
            "declared_eur": 0 if block["declared_eur"] is not None else None,
        })
        stream["extracted_eur"] += block["extracted_eur"]
        if block["declared_eur"] is None:
            stream["declared_eur"] = None
        elif stream["declared_eur"] is not None:
            stream["declared_eur"] += block["declared_eur"]

    for stream in streams.values():
        stream["delta_eur"] = (None if stream["declared_eur"] is None
                               else stream["extracted_eur"] - stream["declared_eur"])

    return {
        "blocks": blocks,
        "streams": list(streams.values()),
        "section_total_eur": section_total,
        "extracted_eur": sum(b["extracted_eur"] for b in blocks),
        "problems": problems,
    }


def run(input_data: dict, document: str | None = None,
        repairs: list[dict] | None = None) -> tuple[dict, list[dict]]:
    repairs = load_row_repairs() if repairs is None else repairs
    rows = scope(input_data.get("rows", []), document)
    sections = [s for s in input_data.get("sections", [])
                if document is None or s["document_id"] == document]
    withheld: list[dict] = list(input_data.get("withheld_rows", []))
    errors: list[dict] = []

    rows, dropped, applied = _apply_drop_repairs(rows, sections, repairs)
    for entry in applied:
        row = entry["row"]
        errors.append(make_error(
            STEP_NAME, "RowRepairApplied",
            f"{row['document_id']} page {row['page']} row {row['row_index']}: "
            "row dropped from the allocation table per row_repairs.json",
            document_id=row["document_id"], year=row["year"], page=row["page"],
            row_index=row["row_index"], cells=row["cells"],
            reason=entry["repair"]["reason"],
        ))

    merged_sections: list[dict] = []
    withheld_streams: set[tuple[str, str]] = set()

    for section in sections:
        section_rows = [r for r in rows if r.get("section_id") == section["section_id"]]
        if not section_rows and "recipient_name" not in section:
            continue
        verdict = split_streams(section, section_rows)
        section = {**section, **verdict}
        merged_sections.append(section)

        if verdict["problems"]:
            for row in section_rows:
                withheld.append({**row, "withheld_reason": "SectionReconciliationMismatch"})
                withheld_streams.add((section["section_id"], row["funding_stream"]))
            errors.append(make_error(
                STEP_NAME, "SectionReconciliationMismatch",
                f"{section['document_id']} {section.get('recipient_name') or section.get('heading')}: "
                + "; ".join(verdict["problems"]),
                document_id=section["document_id"], year=section["year"],
                recipient=section.get("recipient_name") or section.get("heading"),
                public_body_id=section.get("public_body_id"),
                extracted_eur=verdict["extracted_eur"],
                declared_eur=verdict["section_total_eur"],
                delta_eur=(None if verdict["section_total_eur"] is None
                           else verdict["extracted_eur"] - verdict["section_total_eur"]),
                reasons=verdict["problems"],
                first_page=section.get("first_page"),
            ))
            continue

        for stream in verdict["streams"]:
            if stream["declared_eur"] is None:
                reasons = [
                    f"no declared total for {stream['funding_stream']} "
                    "could be read, so its rows cannot be confirmed"
                ]
            elif stream["extracted_eur"] == stream["declared_eur"]:
                continue
            else:
                reasons = [
                    f"{stream['funding_stream']} rows add up to "
                    f"{stream['extracted_eur']:,} but the document declares "
                    f"{stream['declared_eur']:,}"
                ]
            stream["reconciled"] = False
            stream["reasons"] = reasons
            withheld_streams.add((section["section_id"], stream["funding_stream"]))
            for row in section_rows:
                if row["funding_stream"] != stream["funding_stream"]:
                    continue
                withheld.append({**row, "withheld_reason": "SectionReconciliationMismatch"})
            errors.append(make_error(
                STEP_NAME, "SectionReconciliationMismatch",
                f"{section['document_id']} {section.get('recipient_name') or section.get('heading')}: "
                + "; ".join(reasons),
                document_id=section["document_id"], year=section["year"],
                recipient=section.get("recipient_name") or section.get("heading"),
                public_body_id=section.get("public_body_id"),
                funding_stream=stream["funding_stream"],
                extracted_eur=stream["extracted_eur"],
                declared_eur=stream["declared_eur"],
                delta_eur=stream["delta_eur"],
                reasons=reasons,
                first_page=section.get("first_page"),
            ))

    for section in merged_sections:
        streams = section["streams"]
        for stream in streams:
            stream.setdefault("reconciled", True)
            stream.setdefault("reasons", [])
        section["withheld_streams"] = [
            stream["funding_stream"] for stream in streams
            if (section["section_id"], stream["funding_stream"]) in withheld_streams
        ]
        section["withheld"] = bool(section["withheld_streams"])

    withheld_ids = {id(row) for row in withheld}
    kept = [row for row in rows
            if id(row) not in withheld_ids
            and (row.get("section_id"), row.get("funding_stream")) not in withheld_streams]

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "rows": len(kept),
            "withheld_rows": len(withheld),
            "sections": len(merged_sections),
            "sections_published": sum(1 for s in merged_sections if not s["withheld"]),
            "sections_withheld": sum(1 for s in merged_sections if s["withheld"]),
            "streams_withheld": len(withheld_streams),
            "drop_repairs_applied": len(applied),
        },
        **carried(input_data),
        "rows": kept,
        "withheld_rows": withheld,
        "sections": merged_sections,
    }
    return output, errors


def _apply_drop_repairs(rows: list[dict], sections: list[dict],
                        repairs: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Apply `drop_row` repairs. Returns (kept rows, dropped rows, applied)."""
    by_key = {(r["document_id"], r["page"], r["row_index"]): r
              for r in repairs if r["action"] == "drop_row"}
    if not by_key:
        return rows, [], []
    kept, dropped, applied = [], [], []
    for row in rows:
        repair = by_key.get((row["document_id"], row["page"], row["row_index"]))
        if repair is None:
            kept.append(row)
            continue
        dropped.append(row)
        applied.append({"row": row, "repair": repair})
    return kept, dropped, applied


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile sections against their declared totals")
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
    print(f"Published {output['metadata']['sections_published']} of "
          f"{output['metadata']['sections']} sections "
          f"({output['metadata']['streams_withheld']} streams withheld, "
          f"{len(output['rows'])} rows)")


if __name__ == "__main__":
    main()
