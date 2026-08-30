# extract_actions

Finds the commitments inside a document's tables and turns each action row into clean, reviewable metadata. Seventh step in `document_pipeline` (between `clean_text` and `assemble_sections`). Reads only `clean_text`'s JSON — it never opens a PDF, which is what lets every function here be pure and tested against hand-written table fixtures in milliseconds.

Action plans such as the Sustainable Mobility Policy Action Plan 2026-2030 are mostly tables of actions, each with a target date, lead organisation and output. `clean_text` preserves those tables, but nothing downstream extracts the rows. This step is what makes them queryable: it classifies each document by whether it contains action tables, extracts each action row and its target date, and emits a reviewable categorisation record plus action rows themselves.

## What it does

For each document in `clean_text/output.json`:

1. Walks every `table` block across the document's pages and classifies each table, header-based and fail-closed:
   - A table **qualifies** as an action table only if its header row (first non-empty row, cells normalized via `lib.text_utils.normalize_text`) contains an action column **and** every data row's action cell is non-empty.
   - A table with no action column is **confidently excluded** — progress trackers, abbreviation tables, TOC/furniture tables and plain data tables are excluded by the *absence* of an action column, never by a positive "this is X" heuristic.
   - A header that matches an action column but whose column mapping (action vs date) is ambiguous is `ActionHeaderAmbiguous`; a header that matches but has a data row with an empty action cell is `UnclassifiedTable` — both informational, the table is skipped for extraction and a human can eyeball it in `errors.json`.
2. Buckets the document: `dated-actions` (≥1 action table with a recognizable date column) > `undated-actions` (≥1 action table, none dated) > `no-action-tables`. The record carries `dated_table_count` and `undated_table_count` so a mixed document stays visible.
3. Extracts each action row: the action column's cell is the action; the date column's cell (when the table is dated) is the target date; a stable `action_id` (`p010-t01-r01` — page, table index, row) is generated for the calendar to dedupe/reference. Optional columns (`LEAD`, `SUPPORT`, `OUTPUT`, …) are captured opportunistically as `{header: raw_text}` — raw text only, no interpretation.
4. Parses each target date raw-plus-structured: `raw_date` is always emitted; `year`/`quarter`/`month`/`day`/`precision`/`start`/`end` are filled only when a pattern matches confidently, otherwise null with a `DateParseError` logged. Nothing is silently dropped.

The action rows in `output.json` are consumed by `actions_pipeline`'s `resolve_action_identity` step and published as the `public-body-actions` dataset (which carries `public_body_id`, stable `action_id`s, and status history).

Supports incremental resumption via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`); scoping is also available by calling `process(..., doc_slug=...)` directly.

## Input

`clean_text/output.json`, read straight from `--input` — `extract_actions` sits immediately after `clean_text` in `pipeline.json`, so unlike `detect_structure`/`extract_figures`/`clean_text` (whose real dependency is `extract_pages`) there is no fan-in quirk: the shared runner already chains `--input` to the step's true predecessor. Provenance (`doc_title`, `source_url`, `publisher`, `published_date`, `public_body_id`) is resolved from `fetch_pdfs/output.json` by sibling path, the same pattern `assemble_sections` uses.

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `clean_text` |
| `doc_title` / `source_url` / `publisher` / `published_date` / `public_body_id` | Document provenance from `fetch_pdfs` |
| `category` | `dated-actions`, `undated-actions` or `no-action-tables` |
| `dated_table_count` / `undated_table_count` | Number of each action-table kind (a mixed document is visible) |
| `action_count` | Total action rows extracted across all qualifying tables |
| `actions` | `[{action_id, action, raw_date, year, quarter, month, day, precision, start, end, source_page, source_table, columns}]` |

Each action's `action_id` is `p<page>-t<table>-r<row>` (page zero-padded to 3, table index + 1, 1-based row number within the table's data rows). `source_page` is the PDF page, `source_table` the 0-based per-page table index. `columns` holds the other non-empty columns (`{header_text: cell_text}`), raw and uninterpreted.

### Date precision

`raw_date` is never discarded. Structured fields per `precision`:

| `precision` | Example `raw_date` | Populated |
|---|---|---|
| `year` | `2030` | `year`, `start` Jan 1, `end` Dec 31 |
| `quarter` | `Q2 2027` | `year`, `quarter`, `start`/`end` quarter bounds |
| `month` | `January 2026` | `year`, `month`, `start`/`end` month bounds |
| `day` | `15 January 2026` / `2026-01-15` | `year`, `month`, `day`, `start` = `end` |
| `range` | `2026–2030` / `Q1 2026 – Q4 2027` | `start`/`end` only (`year`/`quarter` null — no single value) |
| `null` | `Ongoing`, `Annual` | none — `raw_date` kept, `DateParseError` logged |

## Notable files

- `errors.json` — truncated to `[]` at the start of every run. Nothing here is process-fatal.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `UnclassifiedTable` | table, informational | Header contains an action column but at least one data row's action cell is empty; not confidently an action table |
  | `DateParseError` | row, informational | Deadline cell non-empty but no pattern matched; `raw_date` kept, structured fields null |
  | `ActionHeaderAmbiguous` | table, informational | Header matched an action column but the column mapping (action vs date) is ambiguous |
  | `ExtractActionsFailed` | document | Missing/corrupt upstream record; document skipped, batch continues |

  A document skipped by `ExtractActionsFailed` is **not** marked processed, so a later run retries it without `--force`.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-extract every document instead of skipping already-processed ones.
- `--verbose` — print each document's category and action count.

## Decisions locked

- Bucket precedence: `dated-actions` wins when a document has both, with per-table-kind counts in the report.
- Only the `DEADLINE`/target-date column is the action's date; `INTERIM MILESTONES` is a documented future extension.
- A row in a qualifying action table is one action — no row-level classification (continuation rows are out of scope).
