# extract_pages

The only step in `document_pipeline` that interprets PDF content. Every step downstream of this one reads only the JSON written here and never opens a PDF again — except `extract_figures`, which reopens the PDF purely as a rasteriser, never to ask what its content means. Second step in `document_pipeline`.

## What it does

For each document in `fetch_pdfs/output.json`:

1. Resolves the PDF as `Path(fetch_pdfs_dir) / record["pdf_path"]` and opens it once with `pymupdf`, closing it in a `finally` — a 400-page document is never reopened per page.
2. Walks every page, extracting:
   - **Spans** — one entry per non-whitespace text run, with `text`, `font`, `size`, `bbox`, and its `block`/`line`/`span` indices.
   - **Drawings** — vector shapes (`get_drawings()`), skipping any with an empty rect.
   - **Images** — raster images (`get_images(full=True)`), one entry per placement rect.
   - **Tables** — via `find_tables()`, with `bbox`, `rows`, `cols`, `cells`, and the extracted `text` grid. A page `find_tables()` can't parse contributes no table entries rather than failing the page. If a table's true header has no fill-rectangle tying it to `find_tables()`'s detected grid (so the grid's row 0 is already a data row, and the header text sits just above it, unenclosed), it is reconstructed from column-aligned text spans in a small gap directly above the grid and prepended as row 0 — narrowly scoped (tight vertical gap, spans must align with existing column boundaries, must cover most columns, and must not belong to another table on the page) so an unrelated caption or paragraph above a table is never mistaken for its header.
3. Reads the document's outline/TOC (`get_toc(simple=False)`).
4. If every page's spans list is empty — i.e. the document has no text layer anywhere, a hallmark of a scanned PDF — logs one `NoTextLayer` error and skips the document entirely: **no partial record or page files are written for it**. OCR is out of scope for this pipeline.
5. Otherwise writes one `pages/<doc_slug>/NNN.json` file per page (zero-padded to 3 digits, 4 past 999 pages) and appends a summary record indexing them to `output.json`.

Every coordinate (bbox values, table cells, drawing/image rects) is rounded to 2 decimal places on write, so `pages/*.json` diffs stay small and hand-readable — later tasks treat these files as an intermediate representation meant to be inspected, not just consumed.

Nothing here is process-fatal except a malformed `documents.yml` (caught upstream, in `documents.py`). A PDF can pass `fetch_pdfs`'s shallow open()-and-inspect check yet have a content stream malformed enough that `pymupdf` raises deep inside `get_text`, `get_drawings`, `get_images`, or `find_tables`; that failure is caught per document (opening the PDF is inside the same guarded block, and it is still closed in the `finally` if it was opened), logged to `errors.json` as `PageExtractionFailed`, and the document is skipped — one bad PDF can't abort the rest of the batch.

Supports **incremental resumption** via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`); scoping is also available by calling `process(..., doc_slug=...)` directly.

## Input

`fetch_pdfs/output.json`, via `--input` (required). PDFs are resolved relative to that file's parent directory using each record's `pdf_path`.

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `fetch_pdfs` |
| `doc_title` | Carried through from `fetch_pdfs`'s `title` |
| `page_count` | Number of pages in the PDF |
| `outline` | `[{level, title, page, y}]` from the PDF's table of contents (`[]` if none) |
| `pages` | `[{number, file, width, height, rotation, span_count}]` — one entry per page, `file` relative to this step's directory |

Also produces `pages/<doc_slug>/NNN.json` for each page of each successfully-extracted document:

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

- `errors.json` — one entry per skipped document. Truncated to `[]` at the start of every run.

  | `error_type` | Cause |
  |---|---|
  | `NoTextLayer` | Every page's extracted text is empty/whitespace — the document appears to be scanned |
  | `PageExtractionFailed` | `pymupdf` raised while opening the PDF or extracting a page's spans/drawings/images/outline |
- `pages/<doc_slug>/` — one `NNN.json` per page, for every successfully-extracted document.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-extract every document instead of skipping already-processed ones.
