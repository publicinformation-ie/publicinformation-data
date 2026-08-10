# extract_pages

The only step in `document_pipeline` that interprets PDF content. Every step downstream of this one reads only the JSON written here and never opens a PDF again — except `extract_figures`, which reopens the PDF purely as a rasteriser, never to ask what its content means. Second step in `document_pipeline`.

## What it does

For each document in `fetch_pdfs/output.json`:

1. Resolves the PDF as `Path(fetch_pdfs_dir) / record["pdf_path"]` and opens it once with `pymupdf`, closing it in a `finally` — a 400-page document is never reopened per page.
2. Walks every page, extracting:
   - **Spans** — one entry per non-whitespace text run, with `text`, `font`, `size`, `bbox`, and its `block`/`line`/`span` indices.
   - **Drawings** — vector shapes (`get_drawings()`), skipping any with an empty rect.
   - **Images** — raster images (`get_images(full=True)`), one entry per placement rect.
   - **Tables** — via `find_tables()`, with `bbox`, `rows`, `cols`, `cells`, and the extracted `text` grid. A page `find_tables()` can't parse contributes no table entries rather than failing the page.
3. Reads the document's outline/TOC (`get_toc(simple=False)`).
4. If every page's spans list is empty — i.e. the document has no text layer anywhere, a hallmark of a scanned PDF — logs one `NoTextLayer` error and skips the document entirely: **no partial record or page files are written for it**. OCR is out of scope for this pipeline.
5. Otherwise writes one `pages/<doc_slug>/NNN.json` file per page (zero-padded to 3 digits, 4 past 999 pages) and appends a summary record indexing them to `output.json`.

Every coordinate (bbox values, table cells, drawing/image rects) is rounded to 2 decimal places on write, so `pages/*.json` diffs stay small and hand-readable — later tasks treat these files as an intermediate representation meant to be inspected, not just consumed.

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

- `errors.json` — one `NoTextLayer` entry per skipped (scanned) document. Truncated to `[]` at the start of every run.
- `pages/<doc_slug>/` — one `NNN.json` per page, for every successfully-extracted document.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-extract every document instead of skipping already-processed ones.
