# transform_disclosure_files

Downloads each disclosure log file and converts spreadsheet and PDF data into JSON row arrays for downstream processing.

## What it does

For each file record:
- **XLSX** — parsed with `openpyxl` (first sheet only). Cell values are serialised to JSON-safe types (dates to ISO strings, decimals to floats, other types to strings with a warning).
- **XLS** — parsed with `xlrd` (first sheet only). Same serialisation logic.
- **PDF** — parsed with `pdfplumber`. All tables from all pages are concatenated into a single flat `rows` list. `sheet_name` is set to `"page 1"` for single-page PDFs, or `"pages 1-N"` for multi-page PDFs.

Warnings are appended to `errors.json` (not fatal) when:
- A file has multiple non-empty sheets (only the first is used). (`MultipleSheetWarning`)
- A PDF has multiple table objects across its pages (all rows are still concatenated). (`MultipleTableWarning`)
- Any cell required a `str()` fallback for serialisation. (`CellSerializationWarning`)

Supports **incremental resumption** keyed on `file_url` and propagates upstream `dirty_ids`.

## Input

`find_disclosure_files/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Passes through all input fields and adds:

| Field | Description |
|---|---|
| `sheet_name` | Name of the extracted sheet, page range (e.g. `"page 1"`, `"pages 1-3"`), or `null` on error |
| `rows` | 2D array of cell values (list of rows, each row a list of cells), or `null` on error |

## Notable files

- `errors.json` — download failures, multi-sheet/table warnings, and cell serialisation warnings.

## Testing

### Helper pattern for adding new format tests

Integration tests for `process()` follow this pattern:

1. **Build file bytes** using one of the `_make_*` helpers in the test file (`_make_xlsx`, `_make_xls`, `_make_pdf`).
2. **Mock the HTTP fetch** with `requests_mock.get(url, content=bytes)`.
3. **Create a writer** with the `make_writer` fixture.
4. **Call `process(input_data, tmp_path, writer)`** where `input_data` is a dict matching the `find_disclosure_files/output.json` structure (see `PDF_INPUT`, `XLSX_INPUT`, `XLS_INPUT` at the top of the test file).
5. **Assert on `writer.results`** and `(tmp_path / "errors.json").read_text()`.

To add a new file format or error case: add a `_make_<format>` helper if needed, add a `<FORMAT>_INPUT` fixture, and write tests following the existing naming convention (`test_process_<format>_<scenario>`).

### `_make_pdf` helper

`_make_pdf(tables_per_page)` builds minimal in-memory PDF bytes using `reportlab`. `tables_per_page` is a list of pages; each page is a list of tables; each table is a list of rows. The helper renders tables as bordered grids so pdfplumber can detect them reliably. Single-page single-table PDFs are the common case: `_make_pdf([[table_rows]])`.

## Parallel Processing and Caching

As of 2025-06, this step uses parallel processing and persistent caching to improve performance:

### Parallel Processing
- Files are processed in parallel using `ThreadPoolExecutor`
- Default: 4 workers (configurable via `--workers N` CLI argument)
- Threading parallelises network I/O (file downloads) effectively, since I/O releases the GIL
- **PDF parsing (pdfplumber) is pure Python and does NOT release the GIL** — CPU-bound PDF work runs serially even with multiple workers; the speedup comes from overlapping downloads with parsing of already-cached files
- For workloads that are predominantly cached PDFs, increasing `--workers` beyond 1 provides minimal benefit

### Caching
- Downloaded files are cached in `cache/` directory (ignored via `.gitignore`)
- Cache key: SHA256 hash of URL, stored with `.bytes` extension
- Files are downloaded once and reused on subsequent runs
- Cache is thread-safe with file locking for concurrent access
- Atomic writes via temp file + rename prevent partial/corrupted cache files
- Corrupted cache files are detected and re-downloaded

### Performance
- ~4x speedup on 4-core machines (with ThreadPoolExecutor and GIL-releasing operations)
- 900 files: reduced from 5+ minutes to ~75-90 seconds

### CLI Options
- `--workers N`: Number of parallel workers (default: 4)

### Thread Safety
- `ThreadPoolExecutor` is used instead of `ProcessPoolExecutor` to avoid pickling issues
- Results are collected and appended sequentially to maintain thread safety with `IncrementalWriter`
