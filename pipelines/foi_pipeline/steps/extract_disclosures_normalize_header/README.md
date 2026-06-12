# extract_disclosures_normalize_header

**Step Number:** 14 (after `extract_disclosures_detect_header_row`, before `extract_disclosures_normalize_rows`)

## What This Step Does

Repairs null cells in the detected header row of each disclosure spreadsheet. Two repairs are applied in order:

1. **Continuation-row merge**: rows immediately after the header that are mostly null (> 50% null cells, up to 3 rows) are treated as header continuation rows. Their non-null cells are joined onto the corresponding header cell with a space, then the continuation rows are removed.
2. **Forward-fill**: remaining null cells in the header are replaced with the nearest preceding non-null value, repairing merged-cell spans common in PDF-extracted tables.

`header_row_idx` is preserved unchanged; only the header row content and row list change.

## Input

**File:** `steps/extract_disclosures_detect_header_row/output.json`

**Structure:**
```json
{
  "results": [
    {
      "public_body_id": 123,
      "file_url": "https://...",
      "file_type": "xlsx",
      "rows": [
        [null, "Date Received", null],
        ["Ref", null, "Decision"],
        ...
      ],
      "header_row_idx": 0
    }
  ]
}
```

## Output

**File:** `steps/extract_disclosures_normalize_header/output.json`

Same structure as input, with `rows` modified: the detected header row has null cells repaired and continuation rows merged in. All other rows are unchanged.

**Errors File:** `steps/extract_disclosures_normalize_header/errors.json` — reset to `[]` on each run (no per-record errors produced by this step).

## Notable Files

| File | Purpose |
|------|---------|
| `process.py` | Main processing script |
| `output.json` | Generated output with repaired headers |
| `errors.json` | Error log (always empty; reset on each run) |
| `override.json` | Manual overrides (never overwritten) |
| `pipeline-status.json` | Execution metadata |

## Running This Step

From the `foi_pipeline` directory:

```bash
# Run as part of full pipeline
python process.py --force

# Run this step only
PYTHONPATH=. python steps/extract_disclosures_normalize_header/process.py \
  --input steps/extract_disclosures_detect_header_row/output.json \
  --output steps/extract_disclosures_normalize_header/output.json \
  --force

# Run for a specific public body
python process.py --from extract_disclosures_normalize_header --public-body 1001 --force
```

## Tuning Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `_CONTINUATION_NULL_THRESHOLD` | 0.5 | A row is a continuation row if > 50% of its cells are null |
| `_MAX_CONTINUATION_ROWS` | 3 | Maximum number of rows after the header to consider as continuations |
