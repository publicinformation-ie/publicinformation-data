#!/usr/bin/env python3
"""Trace a single disclosure file through the FOI pipeline steps."""

import argparse
import sys

from src.lib.pipeline_steps import (
    STEP_NAMES,
    STEP_CONFIG,
    get_step_path,
    load_json,
)


def find_file_record(data: dict, file_url: str, step_name: str) -> dict | None:
    """Find the record for a given file URL in step output.
    
    For file-based steps (steps 1-5): look in results array for file_url match.
    For record-based steps (steps 6-8): filter results array by file_url field.
    """
    if data is None:
        return None
    
    output_key, _, is_record_based = STEP_CONFIG[step_name]
    results = data.get(output_key, [])
    
    if not isinstance(results, list):
        return None
    
    if is_record_based:
        # For record-based steps, filter by file_url field
        matching_records = [r for r in results if r.get("file_url") == file_url]
        if matching_records:
            # Return a wrapper with the records for consistency
            return {"records": matching_records, "file_url": file_url}
        return None
    else:
        # For file-based steps, find exact match on file_url
        for record in results:
            if record.get("file_url") == file_url:
                return record
        return None


def calculate_metric(step_name: str, record: dict, errors_data: dict | None) -> int:
    """Calculate percentage metric for a step based on its rules.
    
    Returns: percentage (0-100)
    """
    if record is None:
        return 0
    
    if step_name in ("normalize_disclosure_cells", "filter_phantom_rows",
                     "extract_disclosures_split_combined_columns"):
        # These intermediary steps preserve the file record; their detailed
        # changes are audited separately from the trace percentage.
        return 100
    
    if step_name == "transform_disclosure_files":
        # rows is not null -> 100%, else 0%
        rows = record.get("rows")
        return 100 if rows is not None else 0
    
    if step_name == "extract_disclosures_detect_header_row":
        # header_row_idx is not null -> 100%, else 0%
        header_row_idx = record.get("header_row_idx")
        return 100 if header_row_idx is not None else 0
    
    if step_name == "extract_disclosures_normalize_header":
        # File record exists -> 100%, else 0%
        return 100 if record else 0
    
    if step_name == "extract_disclosures_normalize_rows":
        # (rows_without_errors / total_rows) * 100 using errors.json
        total_rows = record.get("total_rows", 0)
        if total_rows == 0:
            return 0
        
        # Count errors for this file from errors.json
        error_count = 0
        if errors_data and isinstance(errors_data, dict):
            for error_record in errors_data.get("results", []):
                if error_record.get("file_url") == record.get("file_url"):
                    error_count += len(error_record.get("errors", []))
        
        rows_without_errors = total_rows - error_count
        percentage = int((rows_without_errors / total_rows) * 100)
        return max(0, min(100, percentage))
    
    if step_name in ("extract_disclosures_canonicalize", "extract_disclosures_canonicalize_rows", "extract_disclosures_deduplicate"):
        # Records with matching file_url exist -> 100%, else 0%
        # For record-based steps, check if we have records
        if isinstance(record, dict) and "records" in record:
            return 100 if record["records"] else 0
        return 100 if record else 0
    
    return 0


def determine_status(percentage: int) -> str:
    """Determine status string based on percentage."""
    if percentage == 100:
        return "SUCCESS"
    elif percentage > 0:
        return "PARTIAL"
    else:
        return "FAILED"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Trace a disclosure file URL through the FOI pipeline"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="The exact file URL to trace through the pipeline",
    )
    return parser.parse_args()


def format_output_line(step_name: str, percentage: int, status: str) -> str:
    """Format a single output line with proper alignment."""
    step_padded = step_name.ljust(42)
    percent_padded = f"{percentage}%".rjust(4)
    return f"{step_padded}{percent_padded} {status}"


def trace_file(file_url: str) -> int:
    """Trace a file URL through all pipeline steps.
    
    Returns: exit code (0 = success, 1 = file not found in first step)
    """
    file_found = True
    
    for step_name in STEP_NAMES:
        # Load step output
        output_path = get_step_path(step_name, "output")
        output_data = load_json(output_path)
        
        # Load errors if applicable
        errors_data = None
        _, has_errors, _ = STEP_CONFIG[step_name]
        if has_errors:
            errors_path = get_step_path(step_name, "errors")
            errors_data = load_json(errors_path)
        
        # Find the file record
        if file_found:
            record = find_file_record(output_data, file_url, step_name)
            if record is None:
                file_found = False
        
        # If file was not found in previous step, mark as FAILED
        if not file_found:
            percentage = 0
            status = "FAILED"
        else:
            # Calculate metric and status
            percentage = calculate_metric(step_name, record, errors_data)
            status = determine_status(percentage)
            
            # If percentage is 0, file is effectively lost from pipeline
            if percentage == 0 and step_name != "normalize_disclosure_cells":
                file_found = False
        
        # Print output line
        print(format_output_line(step_name, percentage, status))
    
    # Check if file was found in first step
    first_step_output = load_json(get_step_path(STEP_NAMES[0], "output"))
    first_record = find_file_record(first_step_output, file_url, STEP_NAMES[0])
    
    if first_record is None:
        print(f"Error: File URL not found in {STEP_NAMES[0]}/output.json", file=sys.stderr)
        return 1
    
    return 0


def main():
    try:
        args = parse_args()
        file_url = args.url
        exit_code = trace_file(file_url)
        sys.exit(exit_code)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
