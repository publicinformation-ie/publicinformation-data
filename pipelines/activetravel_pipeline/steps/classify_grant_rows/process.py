#!/usr/bin/env python3
"""Give every extracted row exactly one kind from the closed vocabulary.

The column roles in this document family are fixed (code, name, amount); what
varies from row to row is the *kind* of row: running title, column header,
recipient heading, funding-stream divider, project row, subtotal/total anchor,
footnote, or blank. A row that fits no kind is not guessed at: it is recorded
as an error with its raw cells and never reaches the project stage.
"""
import argparse
import sys
from pathlib import Path

from allocations import (
    carried, classify_row, make_error, now_iso, scope,
)
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "classify_grant_rows"
STEP_DIR = Path(__file__).parent


def run(input_data: dict, document: str | None = None) -> tuple[dict, list[dict]]:
    rows = scope(input_data.get("rows", []), document)
    classified: list[dict] = []
    unknown: list[dict] = []
    errors: list[dict] = []

    for row in rows:
        kind, detail = classify_row(row["cells"])
        if kind == "unknown":
            unknown.append({**row, "detail": detail})
            errors.append(make_error(
                STEP_NAME, "UnknownRowKind",
                f"{row['document_id']} page {row['page']} row {row['row_index']} "
                "matches no known row kind",
                document_id=row["document_id"], year=row["year"],
                page=row["page"], row_index=row["row_index"], cells=row["cells"],
            ))
            continue
        classified.append({**row, "kind": kind, "detail": detail})

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "rows": len(classified),
            "unknown_rows": len(unknown),
            "kinds": {
                kind: sum(1 for row in classified if row["kind"] == kind)
                for kind in sorted({row["kind"] for row in classified})
            },
        },
        **carried(input_data),
        "rows": classified,
        "unknown_rows": unknown,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify the extracted allocation rows")
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
    print(f"Classified {len(output['rows'])} rows ({len(output['unknown_rows'])} unknown)")


if __name__ == "__main__":
    main()
