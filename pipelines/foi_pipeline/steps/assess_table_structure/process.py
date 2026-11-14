#!/usr/bin/env python3
"""Fail-closed gate on PDF table structure.

Scores every record's rows with lib.table_structure. A PDF whose best table is
still structurally unreliable is emptied (rows -> []) and flagged, so malformed
tables never reach downstream status/decision parsing. xlsx/xls are scored for
information only and never emptied.
"""
import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import IncrementalWriter, append_errors, read_json, write_json, write_status
from lib.table_structure import DEFAULT_THRESHOLDS, StructureScore, failed_checks, passes, score_table

STEP_NAME = "assess_table_structure"
ERROR_MESSAGE = "no extractor produced a structurally reliable table"


def _error_for(record) -> dict:
    score = record["table_structure"]
    return {
        "step": STEP_NAME,
        "error_type": "TableStructureUnreliable",
        "error_message": ERROR_MESSAGE,
        "context": {
            "public_body_id": record.get("public_body_id"),
            "file_url": record["file_url"],
            "pdf_extractor": record.get("pdf_extractor"),
            "failed_checks": failed_checks(StructureScore(**score), DEFAULT_THRESHOLDS),
            "score": score,
        },
    }


def _rebuild_errors(step_dir, results):
    """Rewrite errors.json from the final results: one entry per excluded file.

    Derived from state rather than appended, so resume/force/scoped reruns can
    never duplicate or orphan an entry.
    """
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])
    append_errors(step_dir, [_error_for(r) for r in results if r.get("table_structure_unreliable")])


def process(input_data, writer, step_dir=None, verbose=False):
    for item in input_data["results"]:
        file_url = item["file_url"]
        if writer.is_processed(file_url):
            continue

        rows = item.get("rows")
        if rows is None or rows == []:
            writer.append([{**item}])
            continue

        score = score_table(rows)
        out = {**item, "table_structure": asdict(score)}
        if item.get("file_type") == "pdf" and not passes(score, DEFAULT_THRESHOLDS):
            out["rows"] = []
            out["table_structure_unreliable"] = True
        writer.append([out])
        if verbose:
            print(".", end="", flush=True)

    if step_dir is not None:
        _rebuild_errors(step_dir, writer.results)


def main():
    parser = argparse.ArgumentParser(
        description="Fail closed on PDF tables whose extracted structure is unreliable"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (
        input_data.get("results") or input_data.get("public_bodies")
    ):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(
        output_path, STEP_NAME, key_field="file_url", force=args.force,
        upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
        target_public_body=args.public_body,
    )
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, writer, step_dir=step_dir, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
