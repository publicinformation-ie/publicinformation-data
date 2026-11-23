# clean_text

Reflows the raw positioned spans of each document back into readable prose: headings, paragraphs, lists and tables. It is the fifth step in `document_pipeline`. It reads only JSON and never opens a PDF. That is what lets every reflow function here be pure (no side effects) and tested against hand-written page fixtures in milliseconds.

A PDF has no paragraphs, only glyphs at coordinates. This step is the inverse of a typesetting decision. It undoes the line breaking and the hyphenation. It removes the furniture that the typesetter added (running headers, page numbers), drops marginalia (text in the margin), and recovers the list structure that the bullets or numbers imply.

## What it does

For each document in `extract_pages/output.json`:

1. Loads the `pages/<doc_slug>/NNN.json` sidecars (the per-page JSON files) of that document and reuses the line grouping (`page_lines`) and body style (`body_size`, `heading_levels`) of `detect_structure`. `extract_figures` already established the same reuse, so the codebase has exactly one line and body-style model, not three. Body size and heading levels are computed from the pages of this document alone, never across a batch. In a mixed run of a large-type poster and a dense report, the typography of one document must not set the heading threshold of the other.
2. Runs the text of every line through `lib.text_utils.normalize_text` (`file_type="pdf"`) to strip `(cid:N)` glyph-mapping artifacts and to collapse internal whitespace. The step reuses the normalization that every other PDF-reading step in this repo already applies, instead of a second implementation here.
3. Strips furniture. A line in the top or bottom `FURNITURE_BAND` of the page is furniture in two cases. It matches a bare page-number pattern (`42`, `— 7 —`). Or it recurs at the same normalized text and height on at least `max(FURNITURE_MIN_PAGES, FURNITURE_RATIO × page_count)` pages, which means it is a running header or footer.
4. Drops marginalia. The step clusters body-sized lines by horizontal gap (`text_columns`) into one or more column spans. A page that is genuinely single-column collapses to one cluster, while a highlighted call-out sidebar next to ordinary prose forms its own cluster instead of being discarded. A line is marginalia, and the step drops it, only if its horizontal extent falls outside every detected column span by more than `MARGIN_TOLERANCE`.
5. Excludes any line inside the bbox of a detected table. Tables get their own block below. To count the text of a cell twice, once as a table and once as a stray paragraph, is a duplication bug, not a feature.
6. Groups the surviving lines by the block index of PyMuPDF and classifies each block:
   - List: every line matches a bullet (`•`, `·`, `▪`, a leading `-`/`*`) or a number or letter marker (`1.`, `2)`, `a.`). All lines must be the same kind. The block becomes one `list` block with `ordered` and an `items` array, and the markers are stripped.
   - Heading: the line size of the block maps to a level in `heading_levels`, and the joined text is 120 characters or less. The block becomes a `heading` block with that `level`.
   - Paragraph: everything else, with its lines joined through `dehyphenate`/`join_lines`. A line that ends in a hyphen followed by a lowercase continuation heals into one word (`accessi-` + `bility` → `accessibility`). A dash before a capitalized word or a real hyphenated compound (`park-and-ride`) is left alone.
7. Adds one table block for each `page["tables"]` entry. The block carries its `index` and `y` (the top of the table) and its cell text as extracted, and the step never flattens the table into a paragraph.
8. Sorts the blocks of the page. Single-column pages sort by ascending `y`. Multi-column pages are column-major: all blocks of one column, top-to-bottom by `y`, before the blocks of the next column. A left-column paragraph and a right-column sidebar that share a vertical band therefore do not interleave.
9. Flags a suspected reading-order failure. If, within a single PyMuPDF block, the y of a later line sits more than `READING_ORDER_TOLERANCE` points above an earlier one, the step logs the page as `SuspectReadingOrder`. This is informational only. Complex multi-column layout solving is explicitly out of scope, and PyMuPDF's own block and line ordering is otherwise trusted as it is.

The step supports incremental resumption (a later run continues from earlier work and does not redo it) via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`). You can also scope by calling `process(..., doc_slug=...)` directly.

## Input

`extract_pages/output.json`, always resolved by a fixed sibling path (`steps/extract_pages/output.json`) and not from `--input`. The shared runner chains `--input` only to the immediately preceding step in `pipeline.json`. `detect_structure` and `extract_figures` both sit between `extract_pages` and `clean_text` there, and they too consume `extract_pages` directly. Trusting the literal target of `--input` therefore silently reads one of their outputs. Those outputs carry no page geometry, so the result cascades to zero blocks with no error. `--input` is still a required flag. It is the CLI contract of the shared runner, and its path still drives the staleness test of the runner, but this step does not read it. There is one consequence. An unrelated change to `extract_figures/output.json` still triggers a rerun of this step (a false positive). A change to the real dependency, `extract_pages/output.json`, does not drive staleness at all. This is a known and accepted quirk of the fan-in (several steps that feed one step), not a bug to fix back to reading `--input` directly. The step resolves page sidecars relative to the directory of `extract_pages/` itself, using the `pages[].file` of each record.

## Output

`output.json` has the shape `{ metadata, results: [...] }`. Each record has these fields:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `extract_pages` |
| `body_size` | The character-weighted modal `(size, font)` of this document, from `detect_structure.body_size`. It is the mode, not the mean, so a few long headings cannot outvote the body text that they label |
| `pages` | `[{"number": ..., "blocks": [...]}]`, one entry for each page, in page order |

Each block has a `type` of exactly `heading`, `paragraph`, `list` or `table`, and no other value, because `assemble_sections` renders exactly these four types:

| `type` | Fields |
|---|---|
| `heading` | `level` (1+), `text`, `y` |
| `paragraph` | `text`, `y` |
| `list` | `ordered` (bool), `items` (marker-stripped strings), `y` |
| `table` | `index` (0-based, per page), `text` (the table's extracted cell rows, unchanged from `extract_pages`), `y` (the table's top) |

`y` is the top edge of each block in PDF points (top-down). Within a page, blocks are in ascending `y` order on single-column pages. On multi-column pages they are grouped column by column, from left to right, and the blocks of each column are in ascending `y` order.

On a page that `ocr_pages` produced (`page["ocr"]` present), every block that is not a table also carries `source: "ocr"`, which marks machine-read text. `assemble_sections` uses that marker for the OCR note of the section and for `meta.json` `ocr_pages`.

## Notable files

- `errors.json` is truncated to `[]` at the start of every run. Nothing here is process-fatal.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `SuspectReadingOrder` | page, informational | Spans within one PyMuPDF block run backward in y by more than `READING_ORDER_TOLERANCE` points. The block and line ordering can then be wrong for this page (for example, a complex multi-column layout). The step flags the page but does not correct it, and it still writes the blocks of the page in the ordering of PyMuPDF as it is |
  | `CleanTextFailed` | document | A page sidecar is missing, the page JSON is corrupted, or a page has a shape that the reflow does not expect. The step skips the document and the rest of the batch still runs. This is the same isolation that `extract_pages` applies with `PageExtractionFailed` and that `extract_figures` applies with `DocumentFigureExtractionFailed` |

  A document skipped by `CleanTextFailed` is not marked processed, so a later run retries it without `--force`.

## Thresholds

Every threshold is a module-level constant at the top of `process.py`, because the values are empirical.

| Constant | Default | Meaning |
|---|---|---|
| `FURNITURE_BAND` | 0.12 | The top and bottom share of the page where furniture lives |
| `FURNITURE_MIN_PAGES` | 3 | The step never calls something furniture from one sighting |
| `FURNITURE_RATIO` | 0.5 | The line must repeat on at least half of the pages of the document |
| `MARGIN_TOLERANCE` | 20.0 pt | A line outside every detected column by more than this value is marginalia |
| `COLUMN_GAP` | 60.0 pt | The horizontal gap between consecutive body-sized lines (by left edge) that is wide enough to start a new column cluster |
| `COLUMN_MIN_LINES` | 2 | A cluster needs at least this many lines to count as its own column. The step discards smaller clusters (a stray outlier) and falls back to the single largest cluster if every cluster is too small |
| `Y_BAND` | 10.0 pt | Furniture must recur at a consistent height, quantized to this band |
| `READING_ORDER_TOLERANCE` | 50.0 pt | A backward jump in y within one block that counts as a suspected reading-order failure |

## Flags

- `--doc SLUG`: scope processing to one document.
- `--force`: re-clean every document instead of skipping already-processed ones.
- `--verbose`: print the block count of each document.
