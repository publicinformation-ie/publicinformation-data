# Design Spec: extract_disclosures_normalize_rows

**Date:** 2025-06-05  
**Author:** Mistral Vibe (with user input)  
**Status:** Draft  
**Target Step Location:** After `extract_disclosures_normalize_header`, before `extract_disclosures_canonicalize`

---

## Problem Statement

The FOI disclosure data currently contains date values in multiple inconsistent formats:
- `DD/MM/YYYY` (e.g., `01/02/2023`)
- `DD-MM-YYYY` (e.g., `01-02-2023`)
- `DD.MM.YYYY` (e.g., `01.02.2023`)
- `DD Month YYYY` (e.g., `01 February 2023`)
- `YYYY-MM-DD` (ISO 8601, e.g., `2023-02-01`)
- Ordinal formats (e.g., `14th July 2016`)
- Short formats (e.g., `30-Jul-25`)
- Non-date text in date columns (e.g., "N/A", "Decision Date")

This inconsistency creates rendering problems for downstream users, particularly the publicinformation-web site.

## Solution Overview

Add a new pipeline step `extract_disclosures_normalize_rows` that:
1. Normalizes all date values to ISO 8601 format (`YYYY-MM-DD`)
2. Identifies date columns using the existing canonical column mapping
3. Handles unparseable values by replacing with `null` and logging errors
4. Follows existing pipeline patterns for incremental processing

## Step Placement

**Location in pipeline.json:** Between `extract_disclosures_canonicalize` and `extract_disclosures_canonicalize_rows`

```json
{
  "steps": [
    ...
    "extract_disclosures_canonicalize",
    "extract_disclosures_normalize_rows",  // NEW
    "extract_disclosures_canonicalize_rows",
    ...
  ]
}
```

## Input

**File:** `steps/extract_disclosures_normalize_header/output.json`

**Structure:**
```json
{
  "results": [
    {
      "public_body_id": 123,
      "name": "Body Name",
      "file_url": "https://...",
      "file_type": "xlsx",
      "rows": [
        ["Header 1", "Header 2", "Date Received", ...],
        ["Value 1", "Value 2", "01/02/2023", ...],
        ...
      ],
      "header_row_idx": 0
    },
    ...
  ]
}
```

## Output

**File:** `steps/extract_disclosures_normalize_rows/output.json`

**Structure:** Same as input, but with:
- Date cell values replaced with ISO 8601 strings (`YYYY-MM-DD`)
- Non-date values in date columns replaced with `null`

**Errors File:** `steps/extract_disclosures_normalize_rows/errors.json`

**Error Types:**
1. `UnparseableDate` - Value could not be parsed as any known date format
2. `AmbiguousDate` - Date format was ambiguous (e.g., `01/02/2023` parsed as DD/MM/YYYY)

## Components

### 1. normalize_date_value(raw_value: str | None) -> str | None

Normalizes a single date string to ISO 8601 format.

**Algorithm:**
1. If value is None or empty string, return None
2. Try regex patterns for known formats:
   - `DD/MM/YYYY` or `D/M/YYYY` variants
   - `DD-MM-YYYY` or `D-M-YYYY` variants  
   - `DD.MM.YYYY` or `D.M.YYYY` variants
   - `DD Month YYYY` or `D Month YYYY` (e.g., "01 February 2023", "1 Feb 2023")
   - `Month DD, YYYY` (e.g., "February 01, 2023")
   - `YYYY-MM-DD` (already ISO, validate and pass through)
   - Ordinal formats (e.g., "14th July 2016")
   - Short year formats (e.g., "30-Jul-25" → "2025-07-30")
3. If regex fails, try `dateutil.parser.parse()` with `dayfirst=True` (DD/MM/YYYY assumption)
4. Validate the parsed date:
   - Year must be between 1900 and 2100
   - If validation fails, return None
5. Return ISO 8601 string (`YYYY-MM-DD`)

**Assumptions:**
- All dates use DD/MM/YYYY convention (Irish standard)
- Short years (2-digit) in the range 00-29 are treated as 2000-2029, 30-99 as 1930-1999

### 2. is_date_column(header: str) -> bool

Determines if a column header represents a date field.

**Implementation:** Uses the existing `canonicalize_header()` function from `steps/extract_disclosures_canonicalize/column_map.py`. Returns True if the canonical header is `date_received` or `decision_date`.

### 3. process_file(item: dict) -> tuple[dict, list[dict]]

Processes a single file record.

**Algorithm:**
1. Extract header row using `header_row_idx`
2. For each header, determine if it's a date column using `is_date_column()`
3. Build a list of date column indices
4. For each data row (rows after `header_row_idx`):
   - For each date column index:
     - Get the cell value
     - Call `normalize_date_value()` on it
     - Replace cell value with result (ISO string or None)
5. Return the updated item and any errors collected

### 4. Main process() function

Orchestrates the full step execution.

**Algorithm:**
1. Load input data from previous step
2. Initialize `IncrementalWriter` with:
   - `key_field="file_url"`
   - `force` flag from CLI
   - `override_path` and `upstream_dirty_path` for incremental processing
3. For each item in input:
   - If already processed and not forced, skip
   - Call `process_file()` on the item
   - Append results to writer
   - Collect errors
4. Write errors to `errors.json`
5. Finalize writer and write status

## Error Handling

### Error Types and When They're Raised

| Error Type | Condition | Action |
|------------|-----------|--------|
| `UnparseableDate` | Value cannot be parsed by regex or dateutil | Replace with `null`, log error |
| `AmbiguousDate` | Date format is ambiguous (e.g., could be MM/DD or DD/MM) | Parse as DD/MM/YYYY, log warning |
| `InvalidDate` | Parsed date fails validation (year out of range) | Replace with `null`, log error |

### Error Context

All errors include context for debugging:
```json
{
  "error_type": "UnparseableDate",
  "error_message": "Could not parse date value",
  "context": {
    "file_url": "https://example.com/file.xlsx",
    "public_body_id": 123,
    "public_body_name": "Body Name",
    "column_header": "Date Received",
    "canonical_column": "date_received",
    "original_value": "Not a date"
  }
}
```

## Incremental Processing

The step uses `IncrementalWriter` with `key_field="file_url"` to support:
- Resuming from interrupted runs
- Scoping to a single public body (`--public-body <ID>`)
- Override system (manual records in `override.json` are never overwritten)

## File Structure

```
steps/extract_disclosures_normalize_rows/
├── __init__.py
├── process.py          # Main entry point
├── README.md           # Step documentation
├── output.json         # Generated output
├── errors.json         # Generated errors
├── override.json       # Manual overrides (optional, initially empty)
└── pipeline-status.json # Execution metadata
```

## Testing Strategy

### Unit Tests (in tests/test_extract_disclosures_normalize_rows.py)

1. **test_normalize_date_value_known_formats:**
   - `01/02/2023` → `2023-02-01`
   - `2023-01-02` → `2023-01-02` (already ISO)
   - `01.02.2023` → `2023-02-01`
   - `01-02-2023` → `2023-02-01`
   - `01 February 2023` → `2023-02-01`
   - `1 Feb 2023` → `2023-02-01`
   - `February 01, 2023` → `2023-02-01`
   - `14th July 2016` → `2016-07-14`
   - `30-Jul-25` → `2025-07-30`

2. **test_normalize_date_value_non_dates:**
   - `N/A` → None
   - `Decision Date` → None
   - `Part Granted` → None
   - `""` → None
   - `None` → None

3. **test_normalize_date_value_edge_cases:**
   - `01/02/23` → `2023-02-01` (2-digit year)
   - `1/2/2023` → `2023-02-01` (single-digit day/month)

4. **test_is_date_column:**
   - `Date Received` → True
   - `date received` → True
   - `Decision Date` → True
   - `Description` → False
   - `Request Details` → False

5. **test_process_file:**
   - Verify date columns are correctly identified
   - Verify only date columns are modified
   - Verify non-date columns pass through unchanged
   - Verify errors are collected correctly

### Integration Test

Run the step on a sample input file and verify:
- Output structure matches input structure
- All valid dates are normalized
- Errors are properly collected

### Regression Test

Run the step on current `extract_disclosures_normalize_header/output.json` and verify:
- No existing valid dates are broken
- Reasonable number of errors (expect many from current data)
- Performance is acceptable (should process thousands of records quickly)

## Dependencies

### Python Packages

- `dateutil` - For parsing complex date formats (already in project dependencies)
- Standard library: `re`, `datetime`

### Internal Dependencies

- `lib.cli_utils` - For `add_common_args`, `filter_by_public_body`, `merge_replacing_body`
- `lib.file_utils` - For `read_json`, `write_json`, `write_status`, `IncrementalWriter`
- `steps.extract_disclosures_canonicalize.column_map` - For `canonicalize_header()`

## Success Criteria

1. All recognizable date formats are normalized to `YYYY-MM-DD`
2. Non-date values in date columns are replaced with `null` and logged
3. Step integrates seamlessly with existing pipeline (no breaking changes)
4. Step supports incremental processing and public body scoping
5. Unit tests pass with >90% coverage of date parsing logic

## Open Questions

None at this time. All design decisions have been validated with user.

## Appendix: Known Date Formats in Current Data

Based on analysis of `extract_disclosures_canonicalize/output.json`:

| Format | Count | Example |
|--------|-------|---------|
| DD/MM/YYYY | 29,256 | 01/02/2023 |
| DD Month YYYY | 2,242 | 01 February 2023 |
| D Month YYYY | 77 | 1 February 2023 |
| DD-MM-YYYY | 33 | 01-02-2023 |
| YYYY-MM-DD | 36 | 2023-02-01 |
| DD.MM.YYYY | 891 | 01.02.2023 |
| D.MM.YYYY | 10 | 1.02.2023 |
| DD.M.YYYY | 0 | - |
| D/MM/YYYY | 238 | 1/02/2023 |
| DD/M/YYYY | 46 | 01/2/2023 |
| D/M/YYYY | 106 | 1/2/2023 |
| Ordinal | ~1,300 | 14th July 2016 |
| Short | ~17 | 30-Jul-25 |
| Non-date | ~14,700 | N/A, Decision Date |

Note: Some values categorized as "non-date" may actually be dates in unrecognized formats.

---

*Generated by Mistral Vibe.*
*Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
