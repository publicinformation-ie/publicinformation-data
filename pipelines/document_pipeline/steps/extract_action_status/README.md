# extract_action_status

Reads each progress report's annex tables and turns every action row into one dated status observation. Eighth step in `document_pipeline` (between `extract_actions` and `assemble_sections`). Reads only `clean_text`'s JSON — it never opens a PDF, which is what lets every function here be pure and tested against hand-written table fixtures in milliseconds.

`extract_actions` records what a plan *committed to*. This step records what the department later *reported* about each of those commitments: a status, a re-stated deadline, and the progress narrative, stamped with the report's own publication date. Together they are what makes slippage visible — a later step (`resolve_action_identity`, in `actions_pipeline`) joins a plan's declared actions against every report's observations of them.

Only `role: report` documents are processed. Plans are skipped without error — they declare actions, they do not observe them.

## What it does

For each `role: report` document in `clean_text/output.json`:

1. Determines the document's annex layout once, from the first table whose header matches a known shape, and applies that layout to every table in the document:
   - **Format A** (Year One, Year Two progress reports) — 7 columns: `No.`, `Action`, `Proposed Output`, `SMP Deadline`, `Status`, `Progress`, `ASI`. Status is read directly from the `Status` column; `ASI` (Avoid/Shift/Improve) is captured raw.
   - **Format B** (Year Three, Final progress reports) — 5 columns, no `Status` column. A row's status is instead the `Complete` / `Modified` / `Delayed` annex heading its table sits under, resolved from `detect_structure`'s section tree via `status_sections`.
   - A header matching neither shape (or no table at all) is `UnknownReportFormat` — the whole document is skipped and **not marked processed**, so a later run retries it without `--force` once the reader learns the layout. Detection is explicit and fail-closed on purpose: running the Format B reader over a Format A report would find no recognised annex heading anywhere and silently emit `UnknownStatusSection` for every table, which is indistinguishable from "this document has no actions".
2. Extracts each action row into an observation: `action_number` (digits parsed out of a possibly zero-padded `No.` cell), `action_text`, `proposed_output`, `progress_text`, `status`, `asi` (Format A only, else `None`), and the reported deadline (raw-plus-structured, via `lib.date_parse.parse_date` — the same parser `extract_actions` and `resolve_action_identity` use, so an original deadline and a reported deadline can be compared without two parsers silently disagreeing on what `Q4 2024` means).
3. Handles annex tables that split across page boundaries: a row with an empty `No.` cell continues the previous row, appending its `Action`/`Proposed Output`/`Progress` text. A continuation with no preceding row in the same table is `ContinuationRowOrphaned` — skipped, never attached to a row from a different table. A repeated header row (page furniture) is recognised and skipped, not treated as a continuation.
4. Normalizes each row's status through a closed five-value vocabulary (`Complete`, `OnSchedule`, `Delayed`, `Ongoing`, `Modified`) that tolerates line breaks and casing drift (`"On\nschedule"` → `OnSchedule`). An unmappable status is `UnknownStatusValue` — the observation is skipped and logged, never coerced to a nearest match.
5. Stamps the whole record's `as_of` with the report's own `published_date` — never inferred from document content, since a report's own publication date is what dates its claims — and tallies `status_counts` across all extracted observations.

## Inputs

- `clean_text/output.json` — page/block text and tables, read straight from `--input` (this step sits immediately after `extract_actions` in `pipeline.json`, so `--input` already points at its true predecessor).
- `detect_structure/output.json` — the section tree, resolved from the sibling step directory (the same fan-in pattern `assemble_sections` uses). Used only for Format B's status-section lookup.
- `fetch_pdfs/output.json` — document provenance and scoping: `doc_title`, `source_url`, `published_date`, `public_body_id`, and critically `role`/`reports_on` (Task 1), which is how this step knows a document is a report and which plan it reports on.

## Output

`output.json` — `{ metadata, results: [...] }`. One record per processed report:

| Field | Description |
|---|---|
| `doc_slug` / `doc_title` / `source_url` / `published_date` / `public_body_id` | Document provenance from `fetch_pdfs` |
| `reports_on` | The plan document's slug, carried through from `fetch_pdfs` |
| `report_format` | `"A"` or `"B"` — detected, never assumed |
| `as_of` | The report's own `published_date` |
| `observation_count` | Total observations extracted |
| `status_counts` | `{status: count}` tally across all observations |
| `observations` | `[{action_number, action_text, proposed_output, reported_deadline_raw, reported_deadline_start, reported_deadline_end, reported_deadline_precision, progress_text, status, asi, source_page, source_ref}]` |

`source_ref` is `p<page>-t<table>-r<row>` (page zero-padded to 3, table index + 1, 1-based row number within the table's data rows).

## Errors

Nothing here is process-fatal for the batch; each is logged to `errors.json` (truncated to `[]` at the start of every run) and the affected observation, table, or document is skipped.

| `error_type` | Scope | Cause |
|---|---|---|
| `UnknownReportFormat` | document | No table header matched Format A (7-col) or Format B (5-col); the whole document is skipped and **not marked processed**, so it retries without `--force` |
| `UnknownStatusSection` | table | A Format B table sits under no recognised `Complete`/`Modified`/`Delayed` annex heading; the table is skipped, never defaulted |
| `UnknownStatusValue` | row | A status cell (Format A) or resolved section (Format B) is not one of the five vocabulary terms; the observation is skipped, never coerced to a nearest match |
| `ContinuationRowOrphaned` | row | A row with an empty `No.` cell has no preceding row in the same table to continue; skipped |
| `UnresolvedActionNumber` | row | A `No.` cell contains no digits; the observation is skipped rather than attached to a neighbouring action |
| `DateParseError` | row | A non-empty reported deadline matched no supported date pattern; the raw text is kept with structured fields left null |
| `ExtractActionStatusFailed` | document | An unexpected exception while extracting a document (e.g. a corrupt upstream record); the document is skipped and not marked processed, isolating the batch from one bad record |

## Running it

```bash
cd pipelines/document_pipeline
uv run python steps/extract_action_status/process.py --input steps/clean_text/output.json
```

Supports incremental resumption via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`); scoping is also available by calling `process(..., doc_slug=...)` directly. `--force` re-extracts every report, including ones that previously failed with `UnknownReportFormat`.

## Known limitations

Against the real SMP corpus, only the Year One progress report currently produces observations. Year Two, Year Three, and the Final report all fail `UnknownReportFormat`.

Root cause: their annex table header rows have no PDF fill-rectangle tying them to the table's PyMuPDF-detected grid. Year One's header sits inside a colored background band that is contiguous with the body's fill rectangle, so `page.find_tables()` merges them into one grid with the header as row 0; the other three reports' headers float on plain white background immediately above the body's fill, so `find_tables()` never includes them in the table. This is a property of `extract_pages.extract_tables()` — a single, shared, pipeline-wide table-detection call used by every document this pipeline processes — not a bug in this step's own detection or extraction logic.

A real fix would need new header-reconciliation logic in `extract_pages` and has a broad blast radius: it would touch every document processed by this pipeline, including the already-published `gda-transport-strategy-2022-2042`. It is deliberately deferred rather than attempted here. This step's fail-closed design means the gap surfaces as a loud `UnknownReportFormat` error per affected document, never a silent data loss.
