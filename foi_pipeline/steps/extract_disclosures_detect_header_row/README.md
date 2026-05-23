# extract_disclosures_detect_header_row

Identifies which row in each spreadsheet is the header row so that column names can be extracted correctly.

## What it does

Many disclosure log spreadsheets have one or more blank or metadata rows before the actual column headers. This step scans the first few rows (up to `max_look_ahead=5`) and returns the index of the first row that contains at least 2 non-null, non-empty cells — a reliable heuristic for the header row.

For files with `rows: null` (PDFs passed through from `transform_disclosure_files`), records `header_row_idx: null` and passes the record through unchanged.

Supports **incremental resumption** keyed on `file_url` and propagates upstream `dirty_ids`.

## Input

`transform_disclosure_files/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Passes through all input fields and adds:

| Field | Description |
|---|---|
| `header_row_idx` | Zero-based index of the detected header row, or `null` for PDFs |

## Notable files

- `errors.json` — initialised to empty on each run (this step does not currently generate errors).
