# Handoff: FOI disclosure PDFs — fix table extraction, not downstream reassembly

Repo: `/Volumes/ext/dev/publicinformation/publicinformation-data` (Python, `uv`). Written 2026-11-14.
Read `AGENTS.md` sections "Core Data-Handling Principle", "Running the Pipeline" and "Tests" before changing anything.

This supersedes the "Suggested approach" in the earlier handoff (`handoff-foi-pdf-column-misalignment.md`, 2026-11-13). The symptom description there is still accurate; the direction has changed.

## Your role

You are coordinating this work. Delegate measurement and implementation to Sonnet/Haiku subagents with self-contained specs, and keep your own context for decisions. The user wants a solution to the root cause, reported with evidence, and has decided the following.

## The decision

**Move the effort into `transform_disclosure_files` (PDF to rows). Do not build more downstream reassembly** (continuation-row merging by text heuristics, header stripping, synonym lists). The tables are already broken when they leave extraction, and the extractor in use is the wrong kind of tool for these PDFs.

## The symptom, briefly

`pipelines/foi_pipeline/steps/extract_disclosures_canonicalize_rows/errors.json` holds about 2,979 errors (`UnrecognizedRequesterType` 1,737, `UnrecognizedDecisionStatus` 644, `StatusValueIsDate` 558, `StatusValueIsColumnHeader` 39). 96% come from PDFs. The values are in the wrong columns (decisions in the requester column, dates in the status column), wrapped cells appear as several rows, repeated headers are treated as data, and words are split or run together. Bodies 1655 and 1295 account for 37%.

## Evidence gathered on 2026-11-14 (read-only, nothing was run)

Measured unless marked otherwise.

**Which extractor produced the errors** (1,372 PDFs in total):

| extractor | errors | files with errors | files handled | share with errors |
|---|---:|---:|---:|---:|
| `pdfplumber` | 2,357 | 282 | 1,263 | 22% |
| `camelot_stream` | 492 | 45 | 109 | 41% |
| xlsx | 110 | 21 | 59 | 36% |
| xls | 9 | 5 | 12 | 42% |

- **No Mistral records exist in the current transform output**, although the design says Mistral OCR runs first and `ocr_cache/` holds results for 965 of the 1,372 PDFs (208 of the 327 PDFs with errors).
- **Probable cause (inferred, not confirmed):** `mistral_enabled` (`transform_disclosure_files/process.py` line 632) needs both `MISTRAL_API_KEY` and `MISTRAL_OCR_PDF_BASE_URL`. Without both, the code skips Mistral entirely, cache included. `MISTRAL_OCR_PDF_BASE_URL` was missing in the shell used for this investigation. The environment of the last real run is unknown.
- **The data is already wrong at extraction** for the four worst files:
  - RTÉ Q4 2019 (body 1655): 487 rows with widths of 8 to 12 cells; words split across cells (`'Freedo','m Of Information Request'`); fragments emitted as rows.
  - RTÉ 2018 (body 1655): 15 rows are 6 wide against 64 that are 5 wide, which shifts the columns.
  - Fingal 2016 (body 1295): 1,028 rows, all 8 wide, but each record is split into continuation rows; bilingual header over 3 to 4 rows.
  - Fingal 2024 (body 1295): widths vary between 2 and 8; first column missing.
- **The PDFs are ruled and born-digital:** all 27 error PDFs available on disk have a text layer and ruling lines on page 1. None were scans. The sample is small and not controlled by body; only 98 of the 1,372 PDFs are on disk (`verify_disclosure_files/cache`).
- **There is no structural quality check.** `_score_rows` counts recognised header columns and is the only gate (lines 487-493). Nothing checks consistent column counts, ragged rows or fragment rows. 85% of the failing files raised no `RowLengthMismatch` or `PhantomRecord` earlier.
- **The fallback is mismatched.** `camelot` *stream* is meant for tables without lines. Lattice mode, which reads ruling lines, is never tried. `_merge_page_splits` runs for Mistral and `pdfplumber` output but not for `camelot`.
- **Mistral is not a cure-all.** Its cached table for Fingal 2016 is well formed (wrapped cells kept in one row). For Fingal 2024 it is ragged (7, 8 or 9 cells per row). Neither RTÉ file has a cached result.
- **Overrides are not a constraint.** `column_mappings.json` has 13 entries (9 are PDFs, 4 carry `skip_camelot_fallback`, none carry `skip_mistral`).

## The plan, in order

### 1. Settle the Mistral question (cheap, offline)

Replay the 208 error PDFs that have cached OCR through the existing markdown path (`markdown_to_pages` and `_merge_page_splits`) in a scratch script, with no API calls, and count how many come out structurally clean.

- If most do, a large share of the errors is a silent configuration regression. The first fix is then to make a half-configured Mistral setup fail loudly instead of falling through.
- Either way, find out from the user or the run logs whether the last run was meant to use Mistral.

Do not set the missing variable and run the pipeline to find out: 407 PDFs have no cached result, and that run would make paid calls.

### 2. Run a bake-off before fixing anything

Pick 30 to 40 PDFs stratified across bodies and failure mechanisms (column shift, wrapped cells, repeated or multi-row header, split words), including the four files above. Compare:

- the current `pdfplumber` settings
- `pdfplumber` with strict line-based strategies
- `camelot` lattice
- PyMuPDF `find_tables`
- cached Mistral, where a cached result exists

Score each on metrics that need no labels:

- uniformity of row width
- per-column type purity (a date column holds dates, a reference column holds references)
- share of fragment rows (rows with one or two filled cells)
- split or run-together words

Add a small hand-checked gold set (about 10 files) so the label-free metrics can be validated against truth. Build the scoring as reusable code, because step 3 needs it.

### 3. Select the extractor by measured structure, not by fixed order

Produce candidate tables, score each one's structure, and keep the best. This replaces "the first extractor that returns something wins, checked only by header score".

### 4. Fail closed at file level

If no candidate passes the threshold, emit one named error for the file (for example `TableStructureUnreliable`) and publish no rows from it. This replaces thousands of misleading row-level "unrecognised value" errors.

### 5. Bound the blast radius with the gate

78% of `pdfplumber` files have no errors. Keep the current output wherever it passes the structural gate and switch extractor only where it fails. Then re-run the window over **all** bodies and compare record counts and error counts per type and per body. Every drop or increase must be explained.

### 6. Keep one concern per step

Put the structural assessment in its own pass-through step after `transform_disclosure_files`. Candidate extraction stays inside the transform step. Do not rewrite upstream files.

### 7. Defer vocabulary

Genuine new values (`Ongoing`, `Closed`, `Release with redactions`, `Clarification sought`, `Student`, `Staff Member`) wait until alignment is fixed, because the counts will change. List them for a human to decide on.

## What not to do

- Do not add synonyms such as `Journalist.` to status or `Granted` to requester type. Those values are in the wrong column.
- Do not add text heuristics downstream to rejoin rows.
- Do not grow `column_mappings.json` as the main fix. Use it only for files that no extractor can rebuild.

## Decisions that need the user

Ask before doing either of these.

- **Re-downloading source PDFs.** The bake-off needs the sample files and only 98 PDFs are on disk. Downloading is free but hits the public bodies' sites.
- **Paid OCR for the 407 uncached PDFs.** This only makes sense if the bake-off shows Mistral beating the free geometric extractors on ruled tables. Do not assume it will.

## Hard rules (from the repo)

- **Fail closed.** Don't guess, don't silently null or rewrite fields, don't silently drop rows. Contaminated values can be excluded only if an error is logged in `errors.json`.
- **Paid calls.** Never trigger uncached Mistral OCR (clearing `ocr_cache/`, forcing re-OCR, or enabling Mistral for a run that covers uncached files) without asking the user. Never run `minutes_pipeline`'s `extract_motions` step.
- **Running the pipeline.** Always go through the pipeline's `process.py`, bounded with `--from` and `--to`, and scoped with `--public-body <id>` where possible:
  ```bash
  cd pipelines/foi_pipeline && uv run python process.py --from transform_disclosure_files --to extract_disclosures_canonicalize_rows --public-body 1655 --force --stop-on-error
  ```
  Never run past `extract_disclosures_deduplicate`; the later steps upload to the database and sync the backlog.
- **Tests.** `cd pipelines/foi_pipeline && uv run pytest tests/ -q`. Run `uv run pyright` if you touch `src/lib`. Regression tests use fixtures taken from real files.
- **Git.** Branch from `main`. Commit only when asked.
- A shell hook may block `grep`/`rg`; use the Grep tool, `git grep`, awk or Python.

## Definition of done

- The Mistral question answered with numbers: how many of the 208 cached error PDFs are clean through the markdown path, and whether the last run was misconfigured.
- A bake-off table: each candidate extractor scored on the sample, with the gold-set check.
- Structure-based selection and the file-level fail-closed error implemented, with regression tests from real-file fixtures.
- A before/after table of errors per type and records per body across all bodies, with every change explained.
- A list of leftovers: genuine vocabulary candidates, and files that still need a manual override.

## Pointers

- `pipelines/foi_pipeline/steps/transform_disclosure_files/process.py`: Mistral attempt at lines 542-578, `mistral_enabled` at 632, `_extract_pdf` at 446-497, `_merge_page_splits` near 196, `_extract_with_camelot_stream` near 379.
- `pipelines/foi_pipeline/steps/transform_disclosure_files/mistral_ocr.py` and `ocr_cache/`.
- `pipelines/foi_pipeline/steps/extract_disclosures_canonicalize/column_mappings.json`.
- Each step's `output.json` is `{metadata, results: [records]}`; each `errors.json` is a list. They are large: aggregate in Python, never print them whole.
- Investigation scripts from 2026-11-14 (`q1.py`, `q4.py`, `q56.py`) are in the same directory as this file and can be reused for the before/after counts.
