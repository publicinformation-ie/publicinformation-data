#!/usr/bin/env python3
"""Normalize decision_status field values to canonical status values."""

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body, merge_replacing_body
from lib.column_map import canonicalize_header
from lib.file_utils import read_json, write_json, write_status
from lib.requester_type_map import canonicalize_requester_type
from lib.status_map import (
    CANONICAL_STATUSES,
    canonicalize_status,
)

STEP_NAME = "extract_disclosures_canonicalize_rows"

_DATE_PATTERN = re.compile(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}')


def _classify_unrecognized(raw_status: str) -> str:
    """Return the most specific error type for an unrecognised decision_status value."""
    header_match = canonicalize_header(raw_status)
    if header_match == 'requester_type':
        return 'StatusValueIsRequesterType'
    if header_match is not None:
        return 'StatusValueIsColumnHeader'
    if _DATE_PATTERN.search(raw_status):
        return 'StatusValueIsDate'
    return 'UnrecognizedDecisionStatus'


def process_records(input_data, results_out, errors_out, verbose=False):
    """Process input records, normalizing decision_status values.
    
    Args:
        input_data: Dict with 'results' key containing list of records
        results_out: List to append normalized records to
        errors_out: List to append error records to
        verbose: If True, print progress indicators
    """
    for record in input_data.get("results", []):
        # Copy once at top of loop to avoid mutating input
        record = dict(record)

        # Normalise requester_type
        raw_requester_type = record.get("requester_type")
        if raw_requester_type and isinstance(raw_requester_type, str) and raw_requester_type.strip():
            canonical_rt = canonicalize_requester_type(raw_requester_type)
            if canonical_rt is not None:
                record["requester_type"] = canonical_rt
            else:
                errors_out.append({
                    "error_type": "UnrecognizedRequesterType",
                    "error_message": f"requester_type '{raw_requester_type}' not in canonical mapping",
                    "context": {
                        "public_body_id": record.get("public_body_id"),
                        "file_url": record.get("file_url"),
                        "foi_reference_id": record.get("foi_reference_id"),
                        "raw_requester_type": raw_requester_type,
                    },
                })
                # Leave record["requester_type"] unchanged

        raw_status = record.get("decision_status")

        # If status is None or empty, pass through unchanged
        if raw_status is None or not isinstance(raw_status, str) or not raw_status.strip():
            results_out.append(record)
            if verbose:
                print(".", end="", flush=True)
            continue

        # Try to canonicalize
        canonical = canonicalize_status(raw_status)

        if canonical is not None:
            # Normalized successfully
            record["decision_status"] = canonical
            if canonical == 'Personal':
                if record.get("request_description") == raw_status:
                    record["request_description"] = "Redacted: Personal request"
                if record.get("requester_type") == raw_status:
                    record["requester_type"] = "Other"
            results_out.append(record)
        else:
            # Unrecognised status: never reconstructed or silently nulled.
            # Classify for the reviewer, write an error, and let a human decide.
            error_type = _classify_unrecognized(raw_status)
            errors_out.append({
                "error_type": error_type,
                "error_message": f"Status '{raw_status}' not in canonical status mapping",
                "context": {
                    "public_body_id": record.get("public_body_id"),
                    "file_url": record.get("file_url"),
                    "foi_reference_id": record.get("foi_reference_id"),
                    "raw_status": raw_status,
                }
            })
            # Confirmed contamination: drop the record entirely
            if error_type in ("StatusValueIsDate", "StatusValueIsRequesterType", "StatusValueIsColumnHeader"):
                if verbose:
                    print("X", end="", flush=True)
                continue
            # Merely unrecognized: pass through with original status
            results_out.append(record)
        
        if verbose:
            print(".", end="", flush=True)


def count_status_distribution(records):
    """Count the distribution of decision_status values in records.
    
    Args:
        records: List of record dicts
        
    Returns:
        Dict mapping status value to count
    """
    counts = defaultdict(int)
    for record in records:
        status = record.get("decision_status")
        if status:
            counts[status] += 1
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize decision_status field values to canonical statuses"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    # Read input
    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Apply public body filter if specified
    input_data = filter_by_public_body(input_data, args.public_body)
    
    # Process records
    results: list = []
    errors: list = []
    
    input_records = input_data.get("results", [])
    total_input = len(input_records)
    
    process_records(input_data, results, errors, verbose=args.verbose)
    
    # Handle merge-back for --public-body scoping (Shape b)
    if args.public_body is not None and not args.force and output_path.exists():
        existing = read_json(output_path).get("results", [])
        results = merge_replacing_body(existing, results, args.public_body)
    
    # Calculate statistics
    total_normalized = sum(1 for r in results if r.get("decision_status") in CANONICAL_STATUSES)
    total_unrecognized = len(errors)
    
    # Count distribution of canonical statuses in output
    status_distribution = count_status_distribution(results)
    # Filter to only canonical statuses for metadata
    canonical_distribution = {
        status: status_distribution.get(status, 0)
        for status in CANONICAL_STATUSES
    }
    
    # Write output
    write_json(
        output_path,
        {
            "metadata": {
                "step": STEP_NAME,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "total_records_input": total_input,
                "total_records_output": len(results),
                "total_records_normalized": total_normalized,
                "total_records_unrecognized": total_unrecognized,
                "canonical_status_distribution": canonical_distribution,
            },
            "results": results,
        },
    )

    # Write errors
    errors_path = step_dir / "errors.json"
    write_json(errors_path, errors)

    # Write pipeline status
    write_status(step_dir, len(results))

    # Print summary
    if args.verbose:
        print()
    print(f"Processed {total_input} records")
    print(f"  Normalized: {total_normalized}")
    print(f"  Unrecognized: {total_unrecognized}")
    print(f"  Output: {len(results)} records")
    print(f"  Errors written to {errors_path}")
    print(f"Wrote output to {output_path}")


if __name__ == "__main__":
    main()
