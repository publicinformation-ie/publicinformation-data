# Tasks

## 1. Pipeline scaffold and committed inputs

- [x] 1.1 Create `pipelines/activetravel_pipeline/` with `pipeline.json` listing the ten steps from design.md §3, `process.py` delegating to `src/lib/pipeline_runner.py`, and empty step directories as each group below is reached; verify `uv run python pipelines/activetravel_pipeline/process.py pipelines/activetravel_pipeline --help` exits 0 and `pipeline.json` validates as JSON.
- [x] 1.2 Write `pipelines/activetravel_pipeline/README.md` (purpose, step table, committed inputs, how to run with and without `--doc`, the section-withholding rule, and the 2022-annex non-comparison from design.md §10); verify every command in it runs as written.
- [x] 1.3 Author `steps/fetch_grant_documents/publications.json` for 2022–2026 with publication page, document URL, and kind (`project_table`, `recipient_summary` for 2025/2026 front matter, `programme_summary` for the 2022 annex); verify a unit test asserts five years, unique document URLs, and that no year lacks a `project_table`.
- [x] 1.4 Author `steps/resolve_recipients/recipient_aliases.json` (canonical names for the 30 local-authority sections plus the non-LA block, including `Dun Loaghaire Rathdown County Council` and `Waterford City and County Council including SDZ`) and `code_prefixes.json`; verify a unit test asserts every alias maps to a name present in the CSO/public-bodies register data and that prefix values are unique where they must be (`KCC` vs `KK`, `WCC`).
- [x] 1.5 Add a `status.py` following the minutes pipeline contract (per-document funnel: rows extracted → classified → reconciled → exported, errors per step, dry-step verdict); verify it exits 0 on a completed run and names the first dry step on a deliberately truncated output.

## 2. Document fetch

- [x] 2.1 Implement `steps/fetch_grant_documents/process.py`: read `publications.json`, fetch each document into a git-ignored cache keyed by URL digest, reuse cached bytes without a network call, record `sha256` and document metadata; verify tests cover cold cache, warm cache (no HTTP) and unreachable URL (`DocumentFetchError`, no records). Covered by `tests/test_fetch.py`.
- [x] 2.2 Write the step `README.md` documenting the output fields, the cache location, and why digests are recorded rather than pinned (design.md §2); verify the documented cache path matches `.gitignore`.

## 3. Table extraction and structural gate

- [x] 3.1 Implement `steps/extract_grant_tables/process.py` using `pdfplumber` page tables plus `lib.table_structure` structural checks to accept or reject each page, emitting rows with page number, row index and the page's gate outcome; verify tests cover an accepted page, a rejected page (`TableStructureUnreliable`, no rows) and a text-free page (`PageHasNoText`). Covered by `tests/test_extraction.py`.
- [x] 3.2 Add a test fixture built from real pages of each of the five committed documents asserting every accepted page yields three-column rows; verify the test fails if the extractor is changed to a two-column assumption.
- [x] 3.3 Write the step `README.md` covering the gate's checks, what is recorded for every page, and that cell-text defects do not reject a page; verify the documented error types match those emitted by the tests.

## 4. Row classification

- [x] 4.1 Implement `steps/classify_grant_rows/process.py` classifying every row into exactly one of `document_title`, `column_header`, `recipient_heading`, `stream_divider`, `project`, `anchor`, `footnote`, `blank`, with repeated page headers recognised and discarded; verify tests cover one real example of each kind taken from the five documents.
- [x] 4.2 Emit `UnknownRowKind` with raw cells for anything unmatched, and prove nothing unclassified reaches the project stage; verify a test feeds a synthetic mismatched row and asserts no `project` output plus one error.
- [x] 4.3 Write the step `README.md` listing the closed kind vocabulary with a real example of each and the rule that unknown rows are reported, not guessed; verify the examples quoted match fixtures in the test file.

## 5. Amount normalisation

- [x] 5.1 Implement `steps/normalize_grant_amounts/process.py` parsing whole-euro amounts with validated thousands grouping and rejecting letters, bare `-`, empty and ambiguous values; verify tests cover `€1,100,000`, `€ 2 0,000,000`, `€ 5 ,000`, `€ -`, and `ection€60,000`.
- [x] 5.2 Record a repair entry (raw cell, used value, rule applied) for every cell whose text was changed, and make `UnreadableAmount` withhold the affected row; verify a test asserts repairs are reported for the whitespace cases and errors for the rejected cases.
- [x] 5.3 Write the step `README.md` documenting the accepted formatting, the rejection set, and that no value is harvested from a cell containing letters; verify each documented rule has a matching test name.

## 6. Funding-stream segmentation

- [x] 6.1 Implement `steps/segment_funding_streams/process.py` assigning each project row to a stream using money anchors and dividers, handling a missing divider (2026 Wicklow second block) and a section whose first anchor is a `Subtotal:`; verify tests reproduce both shapes from real pages and assert the assigned stream.
- [x] 6.2 Emit `UnbracketedBlock` for rows no anchor brackets; verify a test with an anchor-stripped fixture yields errors and no stream assignment.
- [x] 6.3 Write the step `README.md` explaining anchor-bounded segmentation, why position is not trusted, and the two real-world shapes above; verify the README's examples match the fixtures.

## 7. Recipient resolution

- [x] 7.1 Implement `steps/resolve_recipients/process.py` requiring agreement between section heading (via `recipient_aliases.json`) and code prefix (via `code_prefixes.json`), resolving local authorities to `public_body_id` through the existing slug machinery, and keeping non-LA recipients by printed name; verify tests cover agreement, a 2022 pre-heading page (prefix-only attribution), and heading/prefix conflict (`RecipientConflict`).
- [x] 7.2 Emit `RecipientUnresolved` for unmatched headings or prefixes and withhold those rows; verify a test with an invented authority name yields the error and no record.
- [x] 7.3 Write the step `README.md` documenting both signals, the alias/prefix files as committed source of truth, and the no-linkage rule for non-LA recipients; verify the file lists every alias in `recipient_aliases.json`.

## 8. Reconciliation

- [x] 8.1 Implement `steps/reconcile_sections/process.py` comparing each section's project-row sum with its declared anchors, withholding that recipient's funding stream on any difference and reporting recipient, stream, both sums and delta; verify tests cover an exact match, a one-euro difference, and a duplicated section sequence (2024 South Dublin).
- [x] 8.2 Add `row_repairs.json` support (committed, `source_method: manual`, keyed by document + page + row) applying a confirmed correction and reporting `RowRepairApplied`; verify a test applies one repair to a failing section, sees the section publish, and asserts the repair appears in the run's output.
- [x] 8.3 Implement `steps/reconcile_summary/process.py` comparing 2025/2026 per-recipient summary totals with extracted `active_travel` totals, excluding the BSEP column, and explicitly skipping `programme_summary` (2022 annex) and documents with no summary; verify tests cover a match, a mismatch (`SummaryMismatch`, section withheld), and the 2022 annex being skipped rather than compared.
- [x] 8.4 Write both step `README.md` files documenting the gate, the withholding rule and the reason the 2022 annex is not a valid comparison; verify the README states the reconciliation guarantee in the same words as design.md §9.

## 9. Canonicalisation and export

- [x] 9.1 Implement `steps/canonicalize_allocations/process.py` building record identity per design.md §7 (real code vs provisional name-key, duplicate suffixing in document order), setting `project_code_provisional`, and failing publication when a local authority has no public body; verify tests cover two provisional rows with the same placeholder code, a code repeated across two years, and an unresolvable authority (fatal).
- [x] 9.2 Implement `steps/export_allocations/process.py` emitting the canonical flat records plus per-document counts, and fix the record fields to those in design.md §11; verify a test asserts the exact field set and types, and that no record carries a null required field.
- [x] 9.3 Write both step `README.md` files with the identity grammar and the field table; verify the grammar in the README reproduces the ids asserted in tests.

## 10. Publishing

- [x] 10.1 Write `public/schemas/active-travel-allocations.schema.json` constraining the field set, integer non-negative `allocation_eur`, boolean provisional flag and the closed `funding_stream` enum; verify a test validates every exported record against it.
- [x] 10.2 Implement `scripts/transform_active_travel_allocations.py` producing `active-travel-allocations.jsonld`, `.csv`, `.csv-metadata.json` and `README.md` under `public/v1.0.0/active-travel-allocations/`, mirroring to `public/latest/`, and stamping `dct:modified` only on content change via `src/lib/dataset_publish.py`; verify root tests assert the mirror is byte-identical and that a second run with unchanged input rewrites nothing.
- [x] 10.3 Add `public/catalog/dataset-active-travel-allocations.ttl` (DCAT-AP, `dct:relation` to public-bodies, both distributions) and a `public/CHANGELOG.md` entry; verify `uv run pytest tests/ -q` includes a test asserting the TTL parses and its `owl:versionInfo` matches the published directory version.
- [x] 10.4 Add the discovery links to `public/get-the-data.html` (CSV, plain-English description) and the reference list on `public/index.html`; verify the existing discovery guard test passes with the two new links.

## 11. Integration, documentation and review pass

- [x] 11.1 Add a `DATA_SOURCES.md` entry attributing the NTA publications (source URLs, licence/attribution wording); verify the entry names all five document URLs.
- [x] 11.2 Add per-step tests to `pipelines/activetravel_pipeline/tests/` for the full chain over the committed documents, asserting per-year record counts within a tolerance the first clean run establishes; verify `uv run pytest pipelines/activetravel_pipeline/tests -q` passes.
- [x] 11.3 Run `uv run python scripts/generate_pipeline_docs.py` and update the root `AGENTS.md` step sequence table; verify CI's generated-document check passes (`git diff --exit-code` after regeneration leaves no stale section).
- [x] 11.4 Run the pipeline end to end over all five documents with `--stop-on-error`, triage the error queue with `status.py`, and add `row_repairs.json` entries only for values confirmed against the PDFs; verify the run finishes with every error either resolved or listed as needing human review, and record the outcome in the change.
- [ ] 11.5 Run `uv run pyright`, `uv run pytest pipelines/activetravel_pipeline/tests -q`, `uv run pytest tests/ -q`, and `cd pipelines/foi_pipeline && uv run pytest tests/ -q`; verify all pass and the `public/` diff contains only the new dataset's files. **Not complete: pyright, the pipeline suite, the root suite and the document-pipeline suite pass; the FOI suite was not run** (slow, no FOI code touched, stopped pending permission). The `public/` diff contains only the new dataset's files.
- [x] 11.6 Publish once, then review the generated `public/` diff and the dataset README for readability; verify the counts in the README match `status.py` output and the CSV row count matches the JSON-LD `@graph` length.

## Workflow follow-up

- Implement in the dedicated worktree `feat/nta-active-travel-allocations` (branch from `main`), where this change was scaffolded.
- Archive the change after the project's review requirements are satisfied.
- Merging the `public/` change is what publishes; do not merge until the generated diff has been reviewed.
