# extract_disclosures_normalize_rows

**Step Number:** 15 (after `extract_disclosures_normalize_header`, before `extract_disclosures_canonicalize`)

## What This Step Does

Normalizes all date values in disclosure log rows to ISO 8601 format (`YYYY-MM-DD`). This step:

1. Identifies date columns using canonical column mapping (`date_received` and `decision_date`)
2. Parses date values in various formats (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, Month names, ordinals, etc.)
3. Replaces unparseable values with `null` and logs errors
4. Preserves all non-date column values unchanged

## Input

**File:** `steps/extract_disclosures_normalize_header/output.json`

> Input comes from `extract_disclosures_normalize_header` (step 14), which repairs null cells in the header row before this step processes the row values.

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
        ["Header 1", "Date Received", "Header 3"],
        ["Value 1", "01/02/2023", "Value 3"],
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
- Metadata updated with step name and completion timestamp

**Errors File:** `steps/extract_disclosures_normalize_rows/errors.json`

Contains error records for unparseable date values with full context for debugging.

## Notable Files

| File | Purpose |
|------|---------|
| `process.py` | Main processing script |
| `output.json` | Generated output data |
| `errors.json` | Error log for unparseable dates |
| `override.json` | Manual overrides (never overwritten) |
| `pipeline-status.json` | Execution metadata |

## Running This Step

From the `foi_pipeline` directory:

```bash
# Run as part of full pipeline
python process.py --force

# Run this step only
PYTHONPATH=. python steps/extract_disclosures_normalize_rows/process.py \
  --input steps/extract_disclosures_normalize_header/output.json \
  --output steps/extract_disclosures_normalize_rows/output.json \
  --force

# Run for a specific public body
python process.py --from extract_disclosures_normalize_rows --public-body 1001 --force
```

## Date Formats Handled

The step recognizes and normalizes the following date formats:

- `DD/MM/YYYY` (e.g., `01/02/2023`) -> `2023-02-01`
- `DD-MM-YYYY` (e.g., `01-02-2023`) -> `2023-02-01`
- `DD.MM.YYYY` (e.g., `01.02.2023`) -> `2023-02-01`
- `D/M/YYYY` variants (single-digit day/month)
- `DD Month YYYY` (e.g., `01 February 2023`) -> `2023-02-01`
- `D Month YYYY` (e.g., `1 February 2023`) -> `2023-02-01`
- `Month DD, YYYY` (e.g., `February 01, 2023`) -> `2023-02-01`
- Ordinal formats (e.g., `14th July 2016`) -> `2016-07-14`
- Short year formats (e.g., `30-Jul-25`) -> `2025-07-30`
- `YYYY-MM-DD` (ISO 8601) -> pass through validated

Non-date values (e.g., `N/A`, `Decision Date`, `Part Granted`) are replaced with `null`.

## Assumptions

- All dates use DD/MM/YYYY convention (Irish standard)
- Short years (2-digit) in the range 00-29 are treated as 2000-2029, 30-99 as 1930-1999
- Years outside 1900-2100 are rejected as invalid
- Date columns are identified using canonical column mapping from `extract_disclosures_canonicalize`

## Dependencies

- `python-dateutil` - For parsing complex date formats
- Standard library: `re`, `datetime`
- Internal: `lib.cli_utils`, `lib.file_utils`, `steps.extract_disclosures_canonicalize.column_map`
