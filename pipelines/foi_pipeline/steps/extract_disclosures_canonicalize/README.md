# extract_disclosures_canonicalize

Maps raw spreadsheet column headers to canonical field names and emits flat, structured FOI request records.

## What it does

Each spreadsheet uses its own column naming conventions (`Our Ref`, `Reference Number`, `Case ID`, etc.). This step normalises them to a fixed set of canonical column names using a synonym dictionary defined in `column_map.py`.

For each file record with row data:
1. Reads the header row at `header_row_idx`.
2. Maps each header to a canonical key via the synonym lookup (case-insensitive, whitespace-normalised). Headers with a trailing year suffix (e.g. `Request 2023`) are also matched after stripping the suffix.
3. Checks that the two required columns (`foi_reference_id`, `request_description`) are present. Records missing either are logged to `errors.json` and skipped.
4. Emits one flat record per data row (rows after the header), with all canonical column values extracted.

### Row-length realignment

PDF table extraction (pdfplumber) sometimes splits a row into a different
number of cells than the header row has, most often because a wrapped
multi-line text cell (usually the description field) gets fragmented into
extra spurious columns. `canonicalize_file()` handles five shapes, in this
order:

1. **Repeated header row** (any length) — a page-break header reprint,
   detected by 2+ cells matching known header synonyms. Dropped before any
   length-based realignment runs (counted in `header_rows_dropped`).
2. **One cell short** (`len(row) == len(headers) - 1`) — a dropped spacer
   column is reinserted at its known position.
3. **One cell long** (`len(row) == len(headers) + 1`) — the first blank cell
   is removed.
4. **More than one cell long, blank-collapse recoverable** — if stripping all
   blank cells leaves exactly `len(headers)` non-blank values, the blanks are
   collapsed and the row is processed normally. Every real value is intact
   and in original order; only spurious blanks were injected.
5. **More than one cell long, unrecoverable** — anything else. Rows with ≤2
   non-blank cells are a stray continuation fragment of a wrapped line from a
   neighbouring row and are dropped silently. Everything else is logged to
   `errors.json` as `RowLengthMismatch` and dropped, since the field values
   cannot be reliably realigned.

Files with `rows: null` (PDFs) are silently skipped.

## Canonical columns

| Column | Description |
|---|---|
| `foi_reference_id` | The body's internal FOI reference number |
| `decision_date` | Date the request was decided |
| `requester_type` | Category of requester (journalist, business, etc.) |
| `decision_status` | Outcome of the request |
| `review_status` | Internal review / appeal status |
| `related_request` | Reference to a related FOI request |
| `request_description` | Summary of what was requested |

## Input

`extract_disclosures_detect_header_row/output.json`

## Output

`output.json` — `{ metadata, results: [...] }` — a flat list of canonical FOI request records, one per spreadsheet data row.

## Column Mapping Overrides

When a file's headers cannot be mapped automatically (for example, bilingual Irish/English PDFs where pdfplumber merges header cells in ways the synonym dictionary cannot resolve), you can add a manual override to `column_mappings.json`.

Each entry maps a `file_url` to an object with:
- `source_method` — typically `"manual"`
- `overridden` — `true`
- `column_mapping` — an object whose keys are **string column indices** (`"0"`, `"1"`, …) and whose values are:
  - A **string** canonical field name — the cell value is assigned directly to that field.
  - An **array** of canonical field names — the cell is split by whitespace and each token is assigned to the corresponding field. Use this when a single column contains combined values (e.g. `"05/01/2016 FOI/2016/0001"` → `["date_received", "foi_reference_id"]`).
  - **`null`** — the column is skipped entirely.

**When to add an entry:** when `errors.json` reports `InsufficientColumns` for a file and the headers are in a format the synonym dictionary cannot handle (e.g. bilingual Irish PDFs, heavily OCR-corrupted PDFs, or PDFs where date and reference are merged into one column).

**Example:** The Fingal 2016 PDF entry uses array syntax for column 0 because pdfplumber merges the date and FOI reference number into a single cell (`"05/01/2016 FOI/2016/0001"`). Splitting by whitespace separates them into `date_received` and `foi_reference_id`.

## Notable files

- `column_map.py` — the synonym dictionary and `canonicalize_headers()` function.
- `column_mappings.json` — file-level manual column mapping overrides for files that fail automated canonicalization.
- `column_swaps.json` — per-file pair swaps applied after automated canonicalization (fixes transposed columns).
- `errors.json` — files where required columns could not be found.
