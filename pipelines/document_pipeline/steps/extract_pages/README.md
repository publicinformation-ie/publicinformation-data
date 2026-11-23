# extract_pages

It is the only step in `document_pipeline` that interprets PDF content. Every downstream step reads only the JSON that this step writes. There are two exceptions. `ocr_pages` reopens the source PDF to OCR the image-only pages that the curator lists. `extract_figures` reopens it purely as a rasterizer (a tool that turns a page into an image). It is the second step in `document_pipeline`.

## What it does

For each document in `fetch_pdfs/output.json`:

1. Resolves the PDF as `Path(fetch_pdfs_dir) / record["pdf_path"]` and opens it once with `pymupdf`. It closes the file in a `finally` block, so a 400-page document is never reopened for each page.
2. Walks every page and extracts:
   - Spans: one entry for each non-whitespace text run, with `text`, `font`, `size`, `bbox`, and its `block`/`line`/`span` indices.
   - Drawings: vector shapes (`get_drawings()`), with any shape that has an empty rect skipped.
   - Images: raster images (`get_images(full=True)`), one entry for each placement rect.
   - Tables: through `find_tables()`, with `bbox`, `rows`, `cols`, `cells`, and the extracted `text` grid. If `find_tables()` cannot parse a page, the page contributes no table entries, and the page does not fail. Sometimes the true header of a table has no fill rectangle that ties it to the grid that `find_tables()` detected. Row 0 of the grid is then already a data row, and the header text sits just above it, unenclosed. In that case the step reconstructs the header from column-aligned text spans in a small gap directly above the grid and prepends it as row 0. The scope is narrow. The vertical gap must be tight. The spans must align with the existing column boundaries and cover most columns. They must not belong to another table on the page. An unrelated caption or paragraph above a table is therefore never mistaken for its header.
3. Reads the outline or table of contents of the document (`get_toc(simple=False)`).
4. If the spans list of every page is empty, the document has no text layer anywhere, which is a hallmark of a scanned PDF. The step then logs one `NoTextLayer` error and skips the document entirely, and it writes no partial record or page files for that document. OCR is out of scope for this step. `ocr_pages` handles the image-only pages that the curator lists, in documents that have text elsewhere.
5. Otherwise the step writes one `pages/<doc_slug>/NNN.json` file for each page (zero-padded to 3 digits, 4 past 999 pages) and appends a summary record that indexes them to `output.json`.

Every coordinate (bbox values, table cells, drawing and image rects) is rounded to 2 decimal places on write. Diffs in `pages/*.json` then stay small and hand-readable, and later tasks treat these files as an intermediate representation that is meant to be inspected, not only consumed.

Nothing here is process-fatal except a malformed `documents.yml`, which `documents.py` catches upstream. A PDF can pass the shallow open and inspect test that `fetch_pdfs` applies. It can still have a content stream that is malformed enough that `pymupdf` raises deep inside `get_text`, `get_drawings`, `get_images` or `find_tables`. The step catches that failure for each document, because opening the PDF is inside the same guarded block. The file is still closed in the `finally` block if it was opened. It logs the failure to `errors.json` as `PageExtractionFailed` and skips the document. One bad PDF therefore cannot abort the rest of the batch.

The step supports incremental resumption (a later run continues from earlier work and does not redo it) via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`). You can also scope by calling `process(..., doc_slug=...)` directly.

## Input

`fetch_pdfs/output.json`, via `--input` (required). The step resolves PDFs relative to the parent directory of that file, using the `pdf_path` of each record.

## Output

`output.json` has the shape `{ metadata, results: [...] }`. Each record has these fields:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `fetch_pdfs` |
| `doc_title` | Carried through from `fetch_pdfs`'s `title` |
| `page_count` | Number of pages in the PDF |
| `outline` | `[{level, title, page, y}]` from the PDF's table of contents (`[]` if none) |
| `pages` | `[{number, file, width, height, rotation, span_count}]`, one entry for each page, `file` relative to this step's directory |

The step also produces `pages/<doc_slug>/NNN.json` for each page of each document that it extracts successfully:

| Field | Description |
|---|---|
| `number` | 1-indexed page number |
| `width`, `height` | Page dimensions in points |
| `rotation` | Page rotation in degrees |
| `spans` | `[{text, font, size, bbox, block, line, span}]` |
| `drawings` | `[{bbox, fill, width}]` |
| `images` | `[{xref, bbox, width, height}]` |
| `tables` | `[{bbox, rows, cols, cells, text}]` |

## Notable files

- `errors.json` has one entry for each skipped document. It is truncated to `[]` at the start of every run.

  | `error_type` | Cause |
  |---|---|
  | `NoTextLayer` | The extracted text of every page is empty or whitespace, so the document appears to be scanned |
  | `PageExtractionFailed` | `pymupdf` raised an error while it opened the PDF or extracted the spans, drawings, images or outline of a page |
- `pages/<doc_slug>/` holds one `NNN.json` for each page of every document that the step extracts successfully.

## Ligatures in table text

PyMuPDF expands a ligature glyph (ff, tt, ti, ft) into one full-width character plus zero-width ones. Kerning can then make a table cell read "batet ry" or "staf.f". Only `tables[].text` was affected, and spans were always correct. `extract_tables` now calls `repair_ligature_widths` (`ligatures.py`) before `table.extract()`, and it spreads the width of each glyph over its components. See `docs/superpowers/plans/2026-11-08-table-ligature-repair.md`.

## Flags

- `--doc SLUG`: scope processing to one document.
- `--force`: re-extract every document instead of skipping already-processed ones.
