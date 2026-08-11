# clean_text

Reflows each document's raw positioned spans back into readable prose: headings, paragraphs, lists and tables. Fifth step in `document_pipeline`. Reads only `extract_pages`'s JSON — it never opens a PDF, which is what lets every reflow function here be pure and tested against hand-written page fixtures in milliseconds.

A PDF has no paragraphs, only glyphs at coordinates. This step is the inverse of a typesetting decision: undo the line breaking, undo the hyphenation, remove the furniture the typesetter added (running headers, page numbers), drop marginalia, and recover the list structure the bullets or numbers imply.

## What it does

For each document in `extract_pages/output.json`:

1. Loads that document's `pages/<doc_slug>/NNN.json` sidecars and reuses `detect_structure`'s line grouping (`page_lines`) and body style (`body_size`, `heading_levels`) — the same reuse `extract_figures` already established, so there is exactly one line/body-style model in the codebase, not three. **Body size and heading levels are computed from this document's pages alone**, never across a batch: a mixed run of a large-type poster and a dense report must not let one document's typography set the other's heading threshold.
2. Runs every line's text through `lib.text_utils.normalize_text` (`file_type="pdf"`) to strip `(cid:N)` glyph-mapping artefacts and collapse internal whitespace, reusing the normalization every other PDF-reading step in this repo already applies rather than a second implementation here.
3. Strips **furniture**: a line in the top/bottom `FURNITURE_BAND` of the page that either matches a bare page-number pattern (`42`, `— 7 —`) or recurs at the same normalized text and height on at least `max(FURNITURE_MIN_PAGES, FURNITURE_RATIO × page_count)` pages — a running header or footer.
4. Drops **marginalia**: a line whose horizontal extent falls outside the document's main text column (the median left/right edge of body-sized lines) by more than `MARGIN_TOLERANCE`.
5. Excludes any line inside a detected table's bbox — tables get their own block below, so counting a cell's text twice (once as a table, once as a stray paragraph) is a duplication bug, not a feature.
6. Groups the surviving lines by PyMuPDF's own block index and classifies each block:
   - **List**: every line matches a bullet (`•`, `·`, `▪`, a leading `-`/`*`) or a number/letter marker (`1.`, `2)`, `a.`) and they're all the same kind → one `list` block with `ordered` and an `items` array (markers stripped).
   - **Heading**: the block's line size maps to a level in `heading_levels` and the joined text is ≤120 characters → a `heading` block with that `level`.
   - **Paragraph**: everything else, with its lines joined via `dehyphenate`/`join_lines` — a line ending in a hyphen followed by a lowercase continuation is healed into one word (`accessi-` + `bility` → `accessibility`); a dash before a capitalized word or a real hyphenated compound (`park-and-ride`) is left alone.
7. Adds one **table** block per `page["tables"]` entry, carrying its `index` and `y` (the table's top) and its cell text as-extracted — never flattened into a paragraph.
8. Sorts the page's blocks by ascending `y`.
9. Flags a **suspected reading-order failure**: if, within a single PyMuPDF block, a later line's y sits more than `READING_ORDER_TOLERANCE` points above an earlier one, the page is logged as `SuspectReadingOrder`. This is informational only — complex multi-column layout solving is explicitly out of scope, and PyMuPDF's own block/line ordering is otherwise trusted as-is.

Supports **incremental resumption** via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`); scoping is also available by calling `process(..., doc_slug=...)` directly.

## Input

`extract_pages/output.json`, always resolved by a fixed sibling path (`steps/extract_pages/output.json`), **not** from `--input`. The shared runner only ever chains `--input` to the *immediately preceding* step in `pipeline.json`, and `detect_structure` and `extract_figures` both sit between `extract_pages` and `clean_text` there (they too consume `extract_pages` directly) — so trusting `--input`'s literal target would silently read one of their outputs instead, which carry no page geometry, producing a cascading zero-block result with no error. `--input` is still a required flag (the shared runner's CLI contract, and its path still drives the runner's staleness check), it just is not read here. Page sidecars are resolved relative to `extract_pages/`'s own directory, using each record's `pages[].file`.

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `extract_pages` |
| `body_size` | This document's character-weighted modal `(size, font)` from `detect_structure.body_size` — the mode, not the mean, so a handful of long headings can't outvote the body text they label |
| `pages` | `[{"number": ..., "blocks": [...]}]`, one entry per page, in page order |

Each block has a `type` of exactly `heading`, `paragraph`, `list` or `table` — no others — because `assemble_sections` renders exactly these four and nothing else:

| `type` | Fields |
|---|---|
| `heading` | `level` (1+), `text`, `y` |
| `paragraph` | `text`, `y` |
| `list` | `ordered` (bool), `items` (marker-stripped strings), `y` |
| `table` | `index` (0-based, per page), `text` (the table's extracted cell rows, unchanged from `extract_pages`), `y` (the table's top) |

`y` is each block's top edge in PDF points (top-down), and blocks within a page are always in ascending-`y` order.

## Notable files

- `errors.json` — truncated to `[]` at the start of every run. Nothing here is process-fatal.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `SuspectReadingOrder` | page, informational | Spans within one PyMuPDF block run backward in y by more than `READING_ORDER_TOLERANCE` points — the block/line ordering may be wrong for this page (e.g. a complex multi-column layout). Not corrected, only flagged; the page's blocks are still written using PyMuPDF's ordering as-is |
  | `CleanTextFailed` | document | A missing page sidecar, corrupted page JSON, or a page shaped in a way the reflow does not expect. The document is skipped and the rest of the batch still runs — the same isolation `extract_pages` applies with `PageExtractionFailed` and `extract_figures` applies with `DocumentFigureExtractionFailed` |

  A document skipped by `CleanTextFailed` is **not** marked processed, so a later run retries it without `--force`.

## Thresholds

Every threshold is a module-level constant at the top of `process.py`, because they are empirical.

| Constant | Default | Meaning |
|---|---|---|
| `FURNITURE_BAND` | 0.12 | Top/bottom share of the page where furniture lives |
| `FURNITURE_MIN_PAGES` | 3 | Never call something furniture from one sighting |
| `FURNITURE_RATIO` | 0.5 | Must repeat on at least half the document's pages |
| `MARGIN_TOLERANCE` | 20.0 pt | Outside the text column by more than this is marginalia |
| `Y_BAND` | 10.0 pt | Furniture must recur at a consistent height, quantized to this band |
| `READING_ORDER_TOLERANCE` | 50.0 pt | Backward y jump within one block that counts as a suspected reading-order failure |

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-clean every document instead of skipping already-processed ones.
- `--verbose` — print each document's block count.
