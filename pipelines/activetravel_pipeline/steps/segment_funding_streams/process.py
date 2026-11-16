#!/usr/bin/env python3
"""Group project rows into sections and funding-stream blocks.

A section is one recipient's table; it starts at a recipient heading and is
closed by its declared total. A repeated heading on a later page is that same
section continuing, not a new one. Rows that arrive with no heading at all (the
2024 Fingal and 2026 Galway City tables, whose heading page is missing from the
PDF) open a heading-less section that `resolve_recipients` attributes from the
project-code prefix — never from position alone.

Within a section, the money anchors decide the blocks, and the block index
decides the funding stream: the first block is the recipient's active-travel
allocation, every later block is an "other NTA funding streams" allocation.
The document's own divider row corroborates that. Position on the page is never
used. Rows that no declared anchor brackets are withheld as `UnbracketedBlock`.
"""
import argparse
import sys
from pathlib import Path

from allocations import (
    build_sections, carried, make_error, now_iso, scope,
)
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "segment_funding_streams"
STEP_DIR = Path(__file__).parent
STREAM_FOR_BLOCK = ("active_travel", "other_nta_streams")


def stream_for_block(block_index: int) -> str:
    return STREAM_FOR_BLOCK[0] if block_index == 0 else STREAM_FOR_BLOCK[1]


def anchor_record(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "label": row["detail"]["label"],
        "amount_eur": row.get("amount_eur"),
        "page": row["page"],
        "row_index": row["row_index"],
    }


def run(input_data: dict, document: str | None = None) -> tuple[dict, list[dict]]:
    rows = input_data.get("rows", [])
    scoped = scope(rows, document)
    withheld: list[dict] = list(input_data.get("withheld_rows", []))
    errors: list[dict] = []
    sections_out: list[dict] = []

    document_ids: list[str] = []
    for row in scoped:
        if row["document_id"] not in document_ids:
            document_ids.append(row["document_id"])

    for document_id in document_ids:
        doc_rows = [r for r in scoped if r["document_id"] == document_id]
        year = doc_rows[0]["year"]
        sections = build_sections(doc_rows)

        for section_index, section in enumerate(sections):
            all_rows = [row for block in section["blocks"] for row in block["rows"]]
            if not all_rows:
                continue
            section_id = f"{document_id}#{section_index}"
            unbracketed = section["section_total"] is None

            for block_index, block in enumerate(section["blocks"]):
                for row in block["rows"]:
                    if unbracketed:
                        row["withheld_reason"] = "UnbracketedBlock"
                        withheld.append(row)
                        errors.append(make_error(
                            STEP_NAME, "UnbracketedBlock",
                            f"{document_id} page {row['page']}: project row is not "
                            "bracketed by any declared total",
                            document_id=document_id, year=year, page=row["page"],
                            row_index=row["row_index"], cells=row["cells"],
                            section_heading=section["heading"],
                        ))
                        continue
                    row["section_id"] = section_id
                    row["section_heading"] = section["heading"]
                    row["block_index"] = block_index
                    row["funding_stream"] = stream_for_block(block_index)

            published_rows = [r for r in all_rows if "section_id" in r]
            if not published_rows:
                continue

            sections_out.append({
                "section_id": section_id,
                "document_id": document_id,
                "year": year,
                "heading": section["heading"],
                "title": section["title"],
                "first_page": section["first_page"],
                "block_count": len(section["blocks"]),
                "section_total": anchor_record(section["section_total"]),
                "blocks": [
                    {
                        "block_index": index,
                        "funding_stream": stream_for_block(index),
                        "row_count": len(block["rows"]),
                        "declared": anchor_record(block["declared"]),
                    }
                    for index, block in enumerate(section["blocks"])
                ],
            })

    withheld_ids = {id(row) for row in withheld}
    kept = [row for row in rows if id(row) not in withheld_ids]

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "rows": len(kept),
            "sections": len(sections_out),
            "withheld_rows": len(withheld),
        },
        **carried(input_data),
        "rows": kept,
        "withheld_rows": withheld,
        "sections": sections_out,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign funding streams from the money anchors")
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
    print(f"Segmented {output['metadata']['sections']} sections, {len(output['rows'])} rows")


if __name__ == "__main__":
    main()
