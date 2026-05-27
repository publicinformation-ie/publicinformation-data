# PDF Extraction — transform_disclosure_files

**Date:** 2026-05-27
**Step:** `foi_pipeline/steps/transform_disclosure_files`

## Summary

Extend the `transform_disclosure_files` pipeline step to extract tabular data from PDF disclosure logs using `pdfplumber`, outputting JSON in the same structure as the existing XLSX/XLS transformation. Post-processing (header detection, normalisation) remains the responsibility of downstream steps.

## Architecture

A new private function `_extract_pdf(file_bytes)` is added to `process.py`, following the same signature and return shape as the existing `_extract_xlsx` and `_extract_xls` functions:

```python
def _extract_pdf(file_bytes) -> tuple[str, list, list, bool]:
    """Returns (sheet_name, rows, fallback_cells, has_multiple_tables)."""
```

- `pdfplumber` is a lazy import inside `_extract_pdf`, matching how `openpyxl` and `xlrd` are imported inside their functions.
- The existing PDF early-continue branch in `process()` (currently at the `file_type == "pdf"` check) is replaced with the same `try/except` block used for Excel files, calling `_extract_pdf`.

## Extraction Logic

**Per-page extraction with concatenation (Approach A):**

1. Open the PDF with `pdfplumber`.
2. Iterate all pages; for each page call `page.extract_tables()`.
3. Flatten all tables from all pages into a single `rows` list (concatenate in page order).
4. If no tables are found across all pages, raise `ValueError("no tables found")`.

Page-spanning tables (a table whose rows continue across a page boundary) are handled correctly by this approach: each page yields complete rows, and concatenation joins them seamlessly. A single data row physically split mid-row at a page break is not supported (extremely rare in structured government disclosure PDFs).

Repeated header rows on subsequent pages are passed through raw — header de-duplication is left to downstream steps.

## Output Fields

| Field | PDF value |
|---|---|
| `sheet_name` | `"page 1"` (single page) or `"pages 1-N"` (multi-page) |
| `rows` | Flat 2D array — concatenation of all tables from all pages |

pdfplumber always yields string or `None` cell values, so `serialise_cell` is called for consistency but will never trigger the `str()` fallback. `fallback_cells` is always empty for PDFs and kept only for signature uniformity.

## Error Handling

| Case | Behaviour |
|---|---|
| No tables found | `_extract_pdf` raises `ValueError("no tables found")` — caught by existing `except`, logged to `errors.json`, record skipped |
| Multiple tables (total table objects summed across all pages > 1) | Non-fatal `MultipleTableWarning` logged to `errors.json`; extraction continues with concatenated rows |
| Corrupt or encrypted PDF | Caught by existing `except` block — logged to `errors.json`, record skipped |
| Download failure | Existing behaviour unchanged |

`MultipleTableWarning` mirrors the existing `MultipleSheetWarning` pattern (non-fatal, record still written).

## Testing

### Helper function

A new `_make_pdf(tables_per_page)` helper builds minimal in-memory PDF bytes using `reportlab`. `tables_per_page` is a list of pages; each page is a list of tables; each table is a list of rows. The helper renders tables as bordered grids so pdfplumber can detect them reliably. Single-page single-table PDFs are the common case: `_make_pdf([[table_rows]])`.

### New unit tests for `_extract_pdf`

- Single-page, single table → correct `rows`, `sheet_name = "page 1"`, `has_multiple_tables = False`
- Single-page, two tables → rows concatenated, `has_multiple_tables = True`
- Multi-page PDF (table spanning two pages) → all rows concatenated, `sheet_name = "pages 1-2"`
- PDF with no tables → raises `ValueError`

### New `process()` integration tests

- Happy path: PDF with one table → `rows` populated, `sheet_name` set, no errors written
- `MultipleTableWarning`: PDF with 2+ tables → record written, warning in `errors.json`
- No tables found: logged as error, record skipped (same assertions as `test_process_parse_failure_logs_error`)
- Corrupt PDF: caught, logged to `errors.json`, record skipped

### Adding new integration tests

Integration tests for `process()` follow this pattern:

1. **Build file bytes** using one of the `_make_*` helpers (`_make_xlsx`, `_make_xls`, `_make_pdf`).
2. **Mock the HTTP fetch** with `requests_mock.get(url, content=bytes)`.
3. **Create a writer** with the `make_writer` fixture.
4. **Call `process(input_data, tmp_path, writer)`** where `input_data` is a dict matching the `find_disclosure_files/output.json` structure (see `PDF_INPUT`, `XLSX_INPUT`, `XLS_INPUT` fixtures at the top of the test file).
5. **Assert on `writer.results`** and `(tmp_path / "errors.json").read_text()`.

To add a new file format or error case: add a `_make_<format>` helper if needed, add a `<FORMAT>_INPUT` fixture, and write tests following the existing naming convention (`test_process_<format>_<scenario>`).

### Updated existing tests

- `test_process_pdf_passthrough` and `test_process_pdf_no_errors_written` — replaced by the new integration tests above (the old stub behaviour no longer applies).

## Documentation

The step `README.md` is updated to:
- Document PDF extraction behaviour (page range as `sheet_name`, concatenated `rows`).
- Add `MultipleTableWarning` to the warnings list.
- Add a "Testing" section describing the helper pattern for adding new integration tests.

## Dependencies

`pdfplumber` added to project dependencies. `reportlab` added as a dev/test dependency for the `_make_pdf` helper.
