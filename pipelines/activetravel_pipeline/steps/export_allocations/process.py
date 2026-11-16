#!/usr/bin/env python3
"""Export the flat, publishable allocation records.

One record per project allocation: a project listed under one recipient in one
funding stream in one annual document. The field set is fixed here, so the
publisher and the JSON Schema cannot drift apart. Withholding already happened
upstream; this step only decides shape and order.
"""
import argparse
import sys
from pathlib import Path

from allocations import carried, now_iso, scope
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "export_allocations"
STEP_DIR = Path(__file__).parent

RECORD_FIELDS = (
    "@id",
    "@type",
    "year",
    "public_body",
    "public_body_id",
    "recipient_name",
    "funding_stream",
    "project_code",
    "project_code_provisional",
    "project_name",
    "allocation_eur",
    "source_document_url",
    "source_document_sha256",
    "source_page",
)


def build_record(row: dict, documents: dict[str, dict]) -> dict:
    document = documents[row["document_id"]]
    return {
        "@id": row["@id"],
        "@type": "Allocation",
        "year": row["year"],
        "public_body": row.get("public_body"),
        "public_body_id": row.get("public_body_id"),
        "recipient_name": row["recipient_name"],
        "funding_stream": row["funding_stream"],
        "project_code": row["project_code"],
        "project_code_provisional": row["project_code_provisional"],
        "project_name": row["project_name"],
        "allocation_eur": row["amount_eur"],
        "source_document_url": document["url"],
        "source_document_sha256": document["sha256"],
        "source_page": row["page"],
    }


def run(input_data: dict, document: str | None = None) -> tuple[dict, list[dict]]:
    documents = {d["document_id"]: d for d in input_data.get("documents", [])}
    rows = scope(input_data.get("results", []), document)

    records = [build_record(row, documents) for row in rows]
    counts: dict[str, dict] = {}
    for record in records:
        year = str(record["year"])
        bucket = counts.setdefault(year, {
            "records": 0, "allocations_eur": 0,
            "recipients": set(), "active_travel_eur": 0, "other_nta_streams_eur": 0,
        })
        bucket["records"] += 1
        bucket["allocations_eur"] += record["allocation_eur"]
        bucket["recipients"].add(record["recipient_name"])
        bucket[f"{record['funding_stream']}_eur"] += record["allocation_eur"]
    for bucket in counts.values():
        bucket["recipients"] = len(bucket["recipients"])

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "total_records": len(records),
            "total_allocations_eur": sum(r["allocation_eur"] for r in records),
            "counts_by_year": counts,
        },
        "results": records,
        "withheld_rows": input_data.get("withheld_rows", []),
        "sections": input_data.get("sections", []),
    }
    return output, []


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the published allocation records")
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
    write_status(STEP_DIR, len(output["results"]))
    print(f"Exported {output['metadata']['total_records']} allocations "
          f"(€{output['metadata']['total_allocations_eur']:,})")


if __name__ == "__main__":
    main()
