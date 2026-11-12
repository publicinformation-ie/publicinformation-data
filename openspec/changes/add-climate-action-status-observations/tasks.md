# Tasks

> Decisions are in design.md (D-B to D-I). The cost rule applies throughout: no run may reach `minutes_pipeline` `extract_motions`. Only `document_pipeline` and `actions_pipeline` runs are needed here.

## 0. Decisions and sources

- [x] 0.1 **D-B**: attribute by declared reference within the listed plans, with the code-year tie-break; never fall back.
- [x] 0.2 **D-C**: `reports_on` may be a list; the 2026 legacy report lists the 2023–2025 annexes.
- [x] 0.3 **D-D**: `status_annex` attribute; `fetch_status_annexes` and `extract_annex_status` steps; second sibling input.
- [x] 0.4 **D-E**: status from text only, fill never read, `Discontinued` excluded and logged.
- [x] 0.5 **D-F**: legacy-exercise workbook not ingested (102 = Q4 2023 Delayed); **D-I**: dates from the report, curated with evidence.
- [x] 0.6 Sources re-read 2026-11-10: 11 workbooks, 22 sheets, 13 raw layouts (12 after normalisation) (design.md, "Source facts").

## 1. Corpus (`documents.yml`, `documents.py`)

- [x] 1.1 `documents.py`: accept `reports_on` as a slug or a non-empty list. Validate each slug as a same-file `role: plan` sharing `policy_id`; a scalar behaves as before. Accept `status_annex: {url, format}` only with `status_source: annex` and `format: xlsx`. Tests: list valid; empty list, unknown slug, non-plan and cross-policy slugs each rejected; `status_annex` without `status_source` rejected; unknown format rejected; existing scalar entries unchanged.
- [x] 1.2 Repoint the nine CAP reports' `reports_on` to the annex lists in design D-C, and add each one's `status_annex` URL from the proposal table.
- [x] 1.3 Add the Q1&Q2 2026 legacy report entry (`role: report`, `policy_role: progress-report`, `reports_on` the three annexes, `status_source: annex`, `status_annex`). Check its 27 pages for image-only pages and declare `ocr_pages` as the other reports do.
- [x] 1.4 Curate `published_date` for Q2 2023, the three 2025 reports and the 2026 report from the listing page (in a browser) or the department press release, citing the source in an entry comment. Leave any report without evidence undated, and record which. Add a comment that the legacy-exercise workbook is excluded (D-F).
- [x] 1.5 Explain the 2026 code-year split (annex 14/24/36 vs PDF Table 3 14/23/37): identify the row and record the finding. If it is a misprinted reference, raise it before pinning counts (4.1). Do not correct it without an evidenced, curated declaration.

## 2. Annex acquisition and parsing (`document_pipeline`)

- [x] 2.1 `fetch_status_annexes`: read declared annexes as `fetch_pdfs` reads entries. Allow-list content types including `application/octet-stream`, require the `PK\x03\x04` magic, then require openpyxl `read_only` load to succeed. Record `AnnexUnreachable`, `AnnexWrongFormat` (expected and received) or `AnnexUnreadable` per document, with no record written on failure. Make the step stale on `documents.yml` changes. Tests: an octet-stream workbook passes; a PDF payload gives `AnnexWrongFormat`; a corrupt zip gives `AnnexUnreadable`; a failed document is retried on re-run; other documents are unaffected.
- [x] 2.2 `extract_annex_status`, header layouts (D-G):
  - Reviewed layout table of the 12 normalised signatures, each mapped to `reference`, `action_text`, `timeline`, `status` and `status_text`.
  - Row 1 only, normalised, exact full match; `UnrecognisedAnnexLayout` otherwise.
  - Do not use `table_utils.detect_header_row`.
  - Fixture workbooks: a recognised layout; an unrecognised header; a merged header; a two-row header; a header in row 2.
- [x] 2.3 `extract_annex_status`, rows (D-E, D-H):
  - Status mapping table (complete, delayed, on schedule); `UnmappableStatus` with the raw value, and `MissingStatus` even when the cell is filled.
  - Reference normalisation (whitespace and NBSP) with flags from `action_references`; `UnresolvedActionNumber` when the reference cannot be parsed.
  - `DuplicateAnnexReference` excludes both rows.
  - Timeline strict `Q[1-4] YYYY`, otherwise raw kept, structured fields null, `UnparsedTimeline` logged.
  - Every sheet is read.
  - Fixtures: `Discontinued`; fill-only status; padded `Delayed`; NBSP reference; `(TF)` with an extra space; `Q3 2023 Delayed` timeline; a duplicate reference.
- [x] 2.4 Dating (D-I): `as_of` = report `published_date`. An undated report gives zero observations plus one `MissingReportDate`. Output records use the `extract_action_status` shape plus internal provenance (sheet, row, raw values). Tests for both cases, and for an earlier-quarter sheet dated from the report.
- [x] 2.5 Wire both steps into `document_pipeline/pipeline.json` after `extract_action_status`, with explicit `input_steps`. Confirm PDF steps never receive an annex and `extract_action_status` still skips `status_source: annex` reports.

## 3. Attribution (`actions_pipeline`)

- [x] 3.1 `resolve_action_identity`: read `extract_annex_status/output.json` by sibling path, exiting if missing as for `extract_action_status`. Resolve annex observations by declared reference within the listed plans, with the code-year tie-break (D-B). Emit `UnattributableObservation` (report, sheet, row, raw reference, plans searched) or `AmbiguousAttribution`, never falling back. Ordinal observations with a list `reports_on` of length > 1 give `AmbiguousAttribution`. Tests: carried-over `EN/23/6`; forward-year `RE/24/1`; `LU/25/1` in two editions; an unlisted plan's reference; a two-candidate tie that cannot be broken; transport scalar `reports_on` unchanged.
- [x] 3.2 `ActionTextMismatch` non-blocking warning, comparing normalised annex text with the declared action text. Test: mismatch still publishes and is logged.
- [x] 3.3 Run `document_pipeline` from `fetch_status_annexes` through `actions_pipeline`. Triage each step's `errors.json` and record counts by error type per report, including the two `Discontinued` exclusions, every `UnattributableObservation` and every `ActionTextMismatch`. Each unattributable or mismatched row is explained or raised; none is silently accepted.
  - Triage (2026-11-10, run `--from fetch_pdfs` then `actions_pipeline --force`; `extract_motions` never reached). `extract_annex_status`: 157 `UnparsedTimeline` (raw kept), 2 `MissingReportDate` (CAP25 Q2&Q3, Q4), 1 `UnmappableStatus`. `resolve_action_identity`: 2 `UnattributableObservation`, 64 `ActionTextMismatch`; 78 `DeadlineDivergedAtFirstReport`, 62 `OutOfEditionReference`, 23 `DateParseError`, 2 `UnresolvedActionNumber` (2025 plan p67).
  - Observations per report: 2023 Q1 36, Q2 60, Q3 66, Q4 203; 2024 Q1&Q2 81, Q3&Q4 131; 2025 Q1 70, Q2&Q3 0, Q4 0; 2026 legacy 74 (10 Complete, 64 Delayed, matching the headline).
  - `Discontinued`: the 2024 Q1&Q2 `AG/23/10` row is excluded as `UnmappableStatus`. The second row is on the 2025 Q2&Q3 Legacy sheet, whose report is undated, so it is never read (`MissingReportDate`); it is excluded either way.
  - `UnattributableObservation`: `EL/23/10B` (Q2 2023, `Q2 Final Updates!r16`) and `EL/23/10A` (Q3 2023, `Q3 final returns!r12`). The 2023 plan declares `EL/23/10/A` and `EL/23/10/B`; the annexes print the letter without the slash. Not normalised, per no-guessing; excluded for human review (a `reference_corrections`-style fix would be a separate decision).
  - `ActionTextMismatch` (64, all non-blocking): by report Q1 2023 5, Q2 2, Q3 4, Q4 14, 2024 Q1&Q2 4, Q3&Q4 14, 2025 Q1 7, 2026 14. 48 differ only by punctuation, abbreviation or truncation (one text contains the other). 16 are substantive, e.g. `AD/23/8/A` and `/B` both carry the annex wording for `/B`; the annex rows are published against the declared action and flagged for review.

## 4. Verification and publication

- [x] 4.1 Pin `expected_status_counts` per CAP report (Complete/Delayed/OnSchedule) from the triaged run, checked against the reports' published headline counts where they state them (e.g. 2026: 10 complete, 64 delayed, less any exclusions).
  - Pinned for the 8 dated annex reports in `documents.yml` as post-exclusion counts (2023 Q2 Complete 35 and Q3 Complete 23 omit the unattributable `EL/23/10B` and `EL/23/10A`); enforced by the existing `StatusCountMismatch` invariant in `transform_public_body_actions.py`. 2026 matches the published headline (10 Complete, 64 Delayed); older annexes state no headline split, so those are regression pins. The two undated reports carry no pin.
- [x] 4.2 Verification matrix: pytest and pyright for `document_pipeline`, `actions_pipeline` and `scripts/`; `openspec validate`; a full rebuild compared with the previous tree. Confirm transport observations are byte-identical and CAP declared actions are unchanged.
- [x] 4.3 `public-body-actions` 3.1.0 (MINOR: records only, no field or vocabulary change), with a `CHANGELOG` entry noting the `Discontinued` exclusions and any undated reports. Review the `public/**` diff and resolve orphans.
