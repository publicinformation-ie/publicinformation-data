#!/usr/bin/env python3
"""Deduplicate FOI disclosure records by reference ID per public body."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body, merge_replacing_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "extract_disclosures_deduplicate"

# Canonical content fields used to fingerprint null-ref records
_CONTENT_FIELDS = (
    "date_received",
    "decision_date",
    "requester_type",
    "decision_status",
    "review_status",
    "related_request",
    "request_description",
)


def _content_key(record):
    """Composite key for content-based dedup of null-ref records.

    Scoped to (public_body_id, file_url) so the same description appearing in
    two different disclosure log files is not collapsed (they may be distinct
    re-publications or corrections).
    """
    return (
        record.get("public_body_id"),
        record.get("file_url", ""),
        *tuple(str(record.get(f) or "").strip() for f in _CONTENT_FIELDS),
    )


def deduplicate_records(records):
    """Deduplicate records by reference ID, or by content for null-ref records.

    Records with a foi_reference_id are deduplicated by
    (public_body_id, foi_reference_id).  Records without one are deduplicated
    by full content within the same file, which removes repeated page-header
    rows and blank separator rows that PDF extraction produces.

    Args:
        records: List of canonical FOI record dicts

    Returns:
        Tuple of (deduplicated_records, duplicate_count, null_id_count)
        where null_id_count counts null-ref records kept (after dedup).
    """
    seen_ref = set()
    seen_content = set()
    deduplicated = []
    duplicate_count = 0
    null_id_count = 0

    for record in records:
        body_id = record.get("public_body_id")
        ref_id = record.get("foi_reference_id")

        if ref_id is None or ref_id == "":
            key = _content_key(record)
            if key in seen_content:
                duplicate_count += 1
                continue
            seen_content.add(key)
            null_id_count += 1
            deduplicated.append(record)
            continue

        # Create composite key: (public_body_id, normalized_foi_reference_id)
        key = (body_id, str(ref_id).strip())

        if key in seen_ref:
            duplicate_count += 1
            continue

        seen_ref.add(key)
        deduplicated.append(record)

    return deduplicated, duplicate_count, null_id_count


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate FOI disclosure records by reference ID"
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

    # Extract records from input
    records = input_data.get("results", [])
    total_before = len(records)

    # Deduplicate
    deduplicated, duplicates_removed, null_ids = deduplicate_records(records)

    if args.public_body is not None and not args.force and output_path.exists():
        existing = read_json(output_path).get("results", [])
        deduplicated = merge_replacing_body(existing, deduplicated, args.public_body)

    total_after = len(deduplicated)

    # Write output with enhanced metadata
    write_json(
        output_path,
        {
            "metadata": {
                "step": STEP_NAME,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "total_records_before": total_before,
                "total_records_after": total_after,
                "duplicate_records_removed": duplicates_removed,
                "records_with_null_id_kept": null_ids,
            },
            "results": deduplicated,
        },
    )

    write_status(step_dir, len(deduplicated))

    if args.verbose:
        print(f"Deduplication complete:")
        print(f"  Before: {total_before} records")
        print(f"  After:  {total_after} records")
        print(f"  Removed: {duplicates_removed} duplicates")
        print(f"  Null IDs: {null_ids} records (kept)")


if __name__ == "__main__":
    main()
