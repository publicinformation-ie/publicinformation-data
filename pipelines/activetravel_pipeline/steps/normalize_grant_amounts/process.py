#!/usr/bin/env python3
"""Read every printed amount as whole euro, and record every repair.

The currency symbol, thousands separators and incidental whitespace inside the
number are formatting. Anything else — letters, a bare `-`, an empty cell, an
inconsistent grouping — is an unreadable amount: the row is withheld and named
in errors.json rather than published with a substituted value.

A committed `row_repairs.json` entry of action `set_amount` is applied here,
before the value is read, so a confirmed correction flows through the rest of
the chain exactly like a printed amount. Every applied repair is reported.
"""
import argparse
import sys
from pathlib import Path

from allocations import (
    carried, load_row_repairs, make_error, now_iso, parse_amount, scope,
)
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "normalize_grant_amounts"
STEP_DIR = Path(__file__).parent


def _repair_index(repairs: list[dict]) -> dict[tuple, dict]:
    return {
        (r["document_id"], r["page"], r["row_index"]): r
        for r in repairs
        if r["action"] == "set_amount"
    }


def run(input_data: dict, document: str | None = None,
        repairs: list[dict] | None = None) -> tuple[dict, list[dict]]:
    rows = scope(input_data.get("rows", []), document)
    applied = _repair_index(load_row_repairs() if repairs is None else repairs)

    kept: list[dict] = []
    withheld: list[dict] = []
    errors: list[dict] = []
    repair_count = 0

    for row in rows:
        kind = row["kind"]
        if kind not in ("project", "anchor"):
            kept.append({**row, "amount_eur": None})
            continue

        cell = (row["detail"].get("amount_cell") if kind == "anchor"
                else row["cells"][2])
        parsed = parse_amount(cell)

        key = (row["document_id"], row["page"], row["row_index"])
        repair = applied.get(key)
        if repair is not None:
            parsed = {
                "value": repair["value"], "raw": parsed["raw"],
                "error": None, "repair": None, "detail": "",
            }
            repair_count += 1
            errors.append(make_error(
                STEP_NAME, "RowRepairApplied",
                f"{row['document_id']} page {row['page']} row {row['row_index']}: "
                f"amount set to {repair['value']} from row_repairs.json",
                document_id=row["document_id"], year=row["year"],
                page=row["page"], row_index=row["row_index"],
                raw_cell=parsed["raw"], value_used=repair["value"],
                reason=repair["reason"],
            ))

        row = {**row, "amount_eur": parsed["value"], "amount_raw": parsed["raw"]}

        if parsed["error"] is None:
            if parsed["repair"] is not None:
                row["amount_repair"] = parsed["repair"]
            kept.append(row)
            continue

        if kind == "anchor":
            # A control total whose amount cannot be read stays in the stream so
            # segmentation can still bracket the block; reconciliation reports
            # that the declared figure is unknown rather than dropping the anchor.
            row["amount_unreadable"] = True
            kept.append(row)
        else:
            row["withheld_reason"] = "UnreadableAmount"
            row["amount_error"] = parsed["error"]
            withheld.append(row)
        errors.append(make_error(
            STEP_NAME, "UnreadableAmount",
            f"{row['document_id']} page {row['page']} row {row['row_index']}: "
            f"{parsed['detail']}",
            document_id=row["document_id"], year=row["year"],
            page=row["page"], row_index=row["row_index"],
            row_kind=kind, raw_cell=parsed["raw"], reason=parsed["error"],
        ))

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "rows": len(kept),
            "withheld_rows": len(withheld),
            "repairs_applied": repair_count,
            "amount_repairs": sum(1 for row in kept if row.get("amount_repair")),
        },
        **carried(input_data),
        "rows": kept,
        "withheld_rows": withheld,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalise the printed euro amounts")
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
    print(f"Read {len(output['rows'])} amounts "
          f"({len(output['withheld_rows'])} withheld, "
          f"{output['metadata']['repairs_applied']} manual repairs)")


if __name__ == "__main__":
    main()
