# transform_disclosure_files

Downloads each disclosure log file and converts spreadsheet data (XLSX/XLS) into JSON row arrays for downstream processing.

## What it does

For each file record:
- **PDF** — passed through as-is with `rows: null` and `sheet_name: null`. PDF parsing is not implemented here.
- **XLSX** — parsed with `openpyxl` (first sheet only). Cell values are serialised to JSON-safe types (dates to ISO strings, decimals to floats, other types to strings with a warning).
- **XLS** — parsed with `xlrd` (first sheet only). Same serialisation logic.

Warnings are appended to `errors.json` (not fatal) when:
- A file has multiple non-empty sheets (only the first is used).
- Any cell required a `str()` fallback for serialisation.

Supports **incremental resumption** keyed on `file_url` and propagates upstream `dirty_ids`.

## Input

`find_disclosure_files/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Passes through all input fields and adds:

| Field | Description |
|---|---|
| `sheet_name` | Name of the extracted sheet, or `null` for PDFs |
| `rows` | 2D array of cell values (list of rows, each row a list of cells), or `null` for PDFs |

## Notable files

- `errors.json` — download failures, multi-sheet warnings, and cell serialisation warnings.
