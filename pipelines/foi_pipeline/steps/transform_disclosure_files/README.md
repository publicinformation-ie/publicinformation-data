# transform_disclosure_files

Downloads each disclosure log file and converts spreadsheet and PDF data into JSON row arrays for downstream processing.

## What it does

For each file record:
- XLSX files: the step parses the file with `openpyxl` (first sheet only). Cell values are serialized to JSON-safe types (dates to ISO strings, decimals to floats, other types to strings).
- XLS files: the step parses the file with `xlrd` (first sheet only). The serialization logic is the same.
- PDF files: measured table structure chooses the extractor (`select_pdf_table`). `pdfplumber` runs first. If its table passes the structure thresholds in `lib/table_structure.py`, the step keeps it and nothing else runs. Otherwise the step also runs `camelot_lattice`, `pymupdf`, `mistral_cache` and `camelot_stream`. A candidate that raises is skipped. The best passing candidate wins. Candidates are ranked by lowest worst-column role contamination (unmeasured counts as 1.0), then highest anchored-row share, then composite score, then header-mapping score, then that order. If no candidate passes, the step keeps the best-ranked candidate unchanged (same key), because gating is a later step's job. If no candidate produced a table, the file fails with `no tables found`. With `--allow-paid-ocr`, the pre-emptive Mistral OCR call runs first. When it returns tables, the step uses its `mistral_ocr` rows directly: selection is skipped and the rows go straight to the structure gate (`assess_table_structure`). Every file with a `column_mappings.json` entry (manual override) bypasses selection and uses the pre-selection extraction (pdfplumber, then the `camelot_stream` fallback when fewer than 2 header columns map). Entries with `skip_camelot_fallback` skip that fallback too. `skip_mistral` excludes `mistral_cache`. `sheet_name` is `"page 1"` for single-page PDFs, or `"pages 1-N"` otherwise.

Non-fatal extraction conditions are recorded as flags on the output record, not in `errors.json`:
- A file has multiple non-empty sheets, and the step uses only the first one. The record gets `multiple_sheets: true`.
- A PDF has multiple table objects across its pages. The step still concatenates all rows. The record gets `pdf_multiple_tables: true`.
- A manual-override PDF tried the `camelot_stream` fallback. The record gets `pdf_camelot_attempted: true`.

`errors.json` holds only real failures: download errors, file-level parse errors (the exception class as `error_type`, e.g. `ValueError` for `no tables found`), and the two Mistral warnings below.

The step supports incremental resumption (it skips records that it already processed) keyed on `file_url`. It also propagates upstream `dirty_ids`.

## Input

`find_disclosure_files/output.json`

## Output

`output.json` is `{ metadata, results: [...] }`. It passes through all input fields and adds:

| Field | Description |
|---|---|
| `sheet_name` | Name of the extracted sheet, page range (e.g. `"page 1"`, `"pages 1-3"`), or `null` on error. Mistral OCR results always record `"page 1"` |
| `rows` | 2D array of cell values (list of rows, each row a list of cells), or `null` on error |
| `pdf_extractor` | PDF only. The chosen extractor: `"mistral_ocr"` (live Mistral call), or a selection candidate: `"pdfplumber"`, `"camelot_lattice"`, `"pymupdf"`, `"mistral_cache"`, `"camelot_stream"` |
| `pdf_table_selection` | PDF only, absent for manual-override files and Mistral live results. `{"chosen", "kept_incumbent", "scores": {name: structure score \| {"error"} \| null}}` |
| `pdf_merge_stats` | PDF only. `{"page_split_merges": N, "header_rows_stripped": N}` (every candidate goes through `_merge_page_splits`). |
| `pdf_multiple_tables` | PDF only, present as `true` when the PDF holds more than one table object (rows are concatenated). |
| `multiple_sheets` | XLSX/XLS only, present as `true` when the workbook has more than one non-empty sheet (only the first is extracted). |
| `pdf_camelot_attempted` | PDF only, present as `true` when a manual-override file's extraction tried the `camelot_stream` fallback. |

## Notable files

- `errors.json`: download failures, file-level parse failures, and Mistral warnings.
- `ocr_cache/`: Mistral markdown responses, committed with Git LFS (see [Mistral OCR](#mistral-ocr)).

## Testing

### Helper pattern for adding new format tests

Integration tests for `process()` follow this pattern:

1. Build file bytes with one of the `_make_*` helpers in the test file (`_make_xlsx`, `_make_xls`, `_make_pdf`).
2. Mock the HTTP fetch with `requests_mock.get(url, content=bytes)`.
3. Create a writer with the `make_writer` fixture.
4. Call `process(input_data, tmp_path, writer)`, where `input_data` is a dict that matches the `find_disclosure_files/output.json` structure (see `PDF_INPUT`, `XLSX_INPUT`, `XLS_INPUT` at the top of the test file).
5. Assert on `writer.results` and `(tmp_path / "errors.json").read_text()`.

If you add a new file format or error case, add a `_make_<format>` helper when one is needed. Add a `<FORMAT>_INPUT` fixture and write tests that follow the existing naming convention (`test_process_<format>_<scenario>`).

### `_make_pdf` helper

`_make_pdf(tables_per_page)` builds minimal in-memory PDF bytes with `reportlab`. `tables_per_page` is a list of pages. Each page is a list of tables. Each table is a list of rows. The helper renders tables as bordered grids, so pdfplumber can detect them reliably. Single-page single-table PDFs are the common case: `_make_pdf([[table_rows]])`.

## Evaluation (`eval/`)

`eval/evaluate.py` measures extraction quality of successfully converted PDF files. It does not re-evaluate extraction success (that is implicit, because only PDFs where `rows is not None` are included).

### Primary metric: `clean_extraction_rate`

Fraction of PDFs with no detected quality issues. Supplementary metrics track each issue type:

| Metric | What it detects |
|---|---|
| `null_first_row_rate` | The first row contains one or more null cells. This can indicate a header detection problem upstream |
| `null_column_rate` | An entire column is null across all data rows (structural extraction alignment issue) |
| `newline_split_row_rate` | A data row has exactly 1 non-null value in a 3+-column table (PDF cell with embedded newline split across rows) |
| `camelot_fallback_rate` | Fraction of PDFs whose manual-override extraction tried the `camelot_stream` fallback (`pdf_camelot_attempted`) |
| `camelot_win_rate` | camelot stream extraction was used in the final output |
| `mistral_ocr_rate` | Fraction of PDFs extracted via the Mistral OCR path |

### Predicates

`has_null_column` skips newline-split rows before it checks for always-null columns. This prevents false positives. Without the skip, a split row's structural nulls can flag a column as always-null.

### Running

```bash
cd pipelines/foi_pipeline
uv run python steps/transform_disclosure_files/eval/evaluate.py
```

Output: `eval/eval_results.json`, `eval/issues.json`, `eval/quality_by_body.json`.

## Parallel Processing and Caching

As of 2025-06, this step uses parallel processing and persistent caching:

### Parallel Processing
- Files are processed in parallel with threads by default (`ThreadPoolExecutor`)
- Default: 8 workers (configurable via `--workers N` CLI argument)
- Threads parallelize network I/O (file downloads) well, because I/O releases the GIL
- PDF parsing (pdfplumber) is pure Python and does NOT release the GIL. With threads, CPU-bound PDF work runs serially. The speedup comes from overlapping downloads with parsing of already-cached files
- If most of the work is cached PDFs, a `--workers` value above 1 gives little benefit. Use `--processes N` instead
- `--processes N` runs a `ProcessPoolExecutor`, so parsing spreads across cores. It cannot be combined with `--allow-paid-ocr` (the Mistral semaphore is thread-only)

### Caching
- Downloaded files are cached in `verify_disclosure_files/cache/` (gitignored, shared with the verify step)
- Cache key: SHA256 hash of URL, stored with `.bytes` extension
- Files are downloaded once and reused on subsequent runs
- The cache is thread-safe, with file locking for concurrent access
- Atomic writes through a temp file and rename prevent partial or corrupted cache files
- The step detects corrupted cache files and downloads them again

### Performance
- ~4x speedup on 4-core machines (with ThreadPoolExecutor and GIL-releasing operations)
- 900 files: reduced from 5+ minutes to ~75-90 seconds

### CLI Options
- `--workers N`: Number of parallel workers (default: 8)
- `--mistral-workers N`: Number of concurrent Mistral OCR API calls, independent of `--workers` (default: 2)
- `--processes N`: Use N worker processes instead of threads (CPU-bound runs). The default 0 means threads. Not compatible with `--allow-paid-ocr`

### Thread Safety
- Threads are the default. `--processes N` opts into a process pool, and the step pins each worker process to one core, so native libraries do not oversubscribe the CPU
- The step collects results and appends them sequentially, to keep `IncrementalWriter` thread-safe

## Mistral OCR

With `--allow-paid-ocr`, PDF extraction tries Mistral OCR first. On failure it falls
back to the usual path: structure-based selection, or the manual-override extraction.

The step is cache-only by default (it reads the OCR cache and never calls the API).
Unless you pass `--allow-paid-ocr`, this step makes no Mistral calls and constructs
no Mistral client, whatever the env vars say. All PDFs go through structure-based
selection (manual overrides use their own extractor). The step consults the OCR cache
only as the scored `mistral_cache` candidate. `--allow-paid-ocr` makes paid Mistral
API calls (one per uncached PDF), so use it deliberately. With the flag, a missing
`MISTRAL_API_KEY` or `MISTRAL_OCR_PDF_BASE_URL` raises `MistralConfigError` instead
of silently falling back.

### Configuration

| Setting | Type | Behavior |
|---|---|---|
| `MISTRAL_API_KEY` | env var | Required with `--allow-paid-ocr`. If it is unset, the run fails with `MistralConfigError`. The step ignores it without the flag. |
| `MISTRAL_OCR_PDF_BASE_URL` | env var | Base URL that serves the cached PDF bytes (e.g. `https://<host>`, and the `.bytes` files live in `verify_disclosure_files/cache/`). Mistral fetches `{MISTRAL_OCR_PDF_BASE_URL}/{sha256}.bytes`. Providing this URL (ngrok, a file server, etc.) is an infrastructure concern outside this step. |
| `--allow-paid-ocr` | CLI flag | Opt in to live (paid) Mistral calls. Default off. |
| `--mistral-workers N` | CLI flag | Bounds concurrent Mistral API calls, independent of `--workers` (default: 2, conservative given Mistral's rate limits). |

### Caching

Raw Mistral markdown responses are cached in `ocr_cache/`, keyed by SHA256 of
`file_url`: `ocr_cache/{sha256}.json` =
`{"file_url": ..., "markdown": ..., "cached_at": <iso8601>}`. The cache is
tracked in git through Git LFS (`.gitattributes`), so adding or deleting an
entry is a repository change. The step checks the cache before every Mistral API
call, independent of the incremental writer's processed-keys skip, so a `--force`
rerun does not incur the OCR cost again for a file that already had OCR. There is
no expiry: delete the specific `ocr_cache/{sha256}.json` file to force a re-OCR.
The step also caches an OCR response with no tables (as `markdown: ""`), so it does
not retry that response automatically either.

### Manual overrides

`extract_disclosures_canonicalize/column_mappings.json` entries support a
`skip_mistral: true` flag. The flag is independent of `skip_camelot_fallback`, and
the two can coexist. Files with this flag go straight to the pdfplumber/camelot
path. This protects manual `column_mapping`s that were calibrated against
pdfplumber's row structure from breaking silently under Mistral's different row
structure.

An entry can also set `pdf_extractor: "<candidate>"` (one of `CANDIDATE_ORDER`).
The step then extracts the file with that candidate instead of `_extract_pdf`, and
the file skips live Mistral OCR even with `--allow-paid-ocr`.

### Errors

| Condition | error_type |
|---|---|
| Mistral API fails after 3 attempts (retries exhausted) | `MistralOCRWarning` (non-fatal, falls back) |
| Mistral returns no tables | `MistralOCREmptyWarning` (non-fatal, falls back) |
