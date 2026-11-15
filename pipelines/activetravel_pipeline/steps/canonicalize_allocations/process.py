#!/usr/bin/env python3
"""Give every allocation its stable identity.

The identity grammar is

    https://data.publicinformation.ie/allocation/
        <recipient-slug>/<year>/<funding-stream>/<key>

where `key` is the lowercased project code when the document prints a real
code, and the slugified project name when the code is a placeholder
(`WCC/26/XXXX`, `DCC/25/00xx`) — a provisional code is explicitly "to be
assigned", repeats within a section, and must never identify a record. Keys
that repeat within one recipient, year and stream are suffixed `-2`, `-3` in
document order, which keeps identity stable across re-runs because document
order is deterministic.

A local authority without a public body is fatal: publication stops rather than
emitting a record whose body link would be missing or invented.
"""
import argparse
import re
import sys
from pathlib import Path

from allocations import (
    carried, is_provisional_code, make_error, now_iso, scope, slugify,
)
from lib.body_refs import BASE_URI
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "canonicalize_allocations"
STEP_DIR = Path(__file__).parent

ALLOCATION_BASE = f"{BASE_URI}/allocation"


def identity_key(code: str, name: str) -> str:
    """The record-identifying part of the @id."""
    if is_provisional_code(code):
        return slugify(name) or "unnamed"
    return re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")


def run(input_data: dict, document: str | None = None) -> tuple[dict, list[dict]]:
    rows = scope(input_data.get("rows", []), document)
    errors: list[dict] = []
    seen: dict[tuple, int] = {}
    seen_content: dict[tuple, dict] = {}
    results: list[dict] = []
    duplicates: list[dict] = []

    for row in rows:
        if row.get("kind") != "project":
            continue
        if row.get("recipient_kind") == "local_authority" and not row.get("public_body_id"):
            raise ValueError(
                f"{row['document_id']} page {row['page']}: local authority "
                f"{row.get('recipient_name')!r} has no public body"
            )

        code = row["detail"]["code"]
        name = row["detail"]["name"]
        provisional = is_provisional_code(code)
        key = identity_key(code, name)

        content_key = (row["recipient_slug"], row["year"], row["funding_stream"],
                       code, name, row.get("amount_eur"))
        if content_key in seen_content:
            duplicates.append({
                "document_id": row["document_id"], "page": row["page"],
                "row_index": row["row_index"], "project_code": code,
                "project_name": name, "allocation_eur": row.get("amount_eur"),
                "kept_page": seen_content[content_key]["page"],
            })
            continue
        seen_content[content_key] = row

        stream_key = (row["recipient_slug"], row["year"], row["funding_stream"], key)
        seen[stream_key] = seen.get(stream_key, 0) + 1
        suffix = "" if seen[stream_key] == 1 else f"-{seen[stream_key]}"

        results.append({
            **row,
            "@id": (f"{ALLOCATION_BASE}/{row['recipient_slug']}/{row['year']}/"
                    f"{row['funding_stream']}/{key}{suffix}"),
            "project_code": code,
            "project_code_provisional": provisional,
            "project_name": name,
        })

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "result_count": len(results),
            "provisional_codes": sum(1 for r in results if r["project_code_provisional"]),
            "duplicates_dropped": len(duplicates),
            "documents": sorted({r["document_id"] for r in results}),
        },
        **carried(input_data),
        "results": results,
        "duplicates": duplicates,
        "withheld_rows": input_data.get("withheld_rows", []),
        "sections": input_data.get("sections", []),
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Build allocation identity")
    add_common_args(parser)
    add_doc_arg(parser)
    args = parser.parse_args()

    try:
        input_data = read_json(args.input)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Fatal: could not read input: {exc}")

    try:
        output, errors = run(input_data, document=args.doc)
    except ValueError as exc:
        sys.exit(f"Fatal: {exc}")

    errors_path = STEP_DIR / "errors.json"
    if errors_path.exists():
        errors_path.unlink()
    if errors:
        append_errors(STEP_DIR, errors)

    write_json(args.output, output)
    write_status(STEP_DIR, len(output["results"]))
    print(f"Canonicalised {output['metadata']['result_count']} allocations "
          f"({output['metadata']['duplicates_dropped']} duplicates dropped)")


if __name__ == "__main__":
    main()
