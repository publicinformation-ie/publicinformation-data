# Design

## Context

- **Observation joins.** `build_observations` (`resolve_action_identity/process.py:412`) looks up `mint_action_id(record["reports_on"], number)` = `"{plan_slug}#{number}"` and nothing else. A miss is `UnresolvedActionNumber`. `documents.py` requires a `role: report` to name exactly one `reports_on` plan in the same file sharing its `policy_id` (lines 111–119, 218–228). `reports_on` is not published: it appears in no schema, in no `publish_bundles` output, and in no `scripts/` transform.
- **Action identity.** Per `public-body-actions-dataset`, an action is identified by its plan plus the printed reference. Legacy reprints (code year < edition year) are excluded from the reprinting edition. A forward-year row (the 2023 annex's `RE/24/1`) belongs to the edition that prints it, and two editions may both declare a reference (`LU/25/1`). **So the code year does not identify the declaring plan. Only the plans' declared actions do.** `edition_year(plan_slug)` derives an edition's year from its slug.
- **Step plumbing.** `fetch_pdfs` accepts `application/pdf`, `application/x-pdf` and `application/octet-stream`, then requires `%PDF-` magic. On failure it writes no record, so the document is retried. `extract_pages` and `extract_figures` open files with pymupdf. `pipeline_runner.py:99-105` resolves one input per step, and `resolve_action_identity` finds `extract_action_status/output.json` by sibling path (`process.py:513-520`).
- **Prior art.** `foi_pipeline` canonicalizes columns and fails closed on `MissingRequiredColumns`. Its header detector, `src/lib/table_utils.detect_header_row`, does **not** fail closed: it falls back to row 0. It must not be reused here.
- **Published contract.** `ActionStatusObservation` (`public/schemas/public-body-actions.schema.json:176`) requires `as_of` (a date) and `status`, where `status` ∈ {Complete, OnSchedule, Delayed, Ongoing, Modified}. The publish-time `StatusCountMismatch` check against `expected_status_counts` lives in `scripts/transform_public_body_actions.py:159-168`. Current version: 3.0.0.

## Source facts (re-read 2026-11-10)

- **Acquisition.** All 11 annexes return 200 from `assets.gov.ie`. The four 2023 quarterly files and the legacy-exercise workbook are served as `application/octet-stream`; the rest as the spreadsheetml type. All payloads start with `PK`. The gov.ie listing page returns 403 to scripted clients.
- **Layout.**
  - Every sheet has its header in row 1, with no title rows and no merged header cells. 12 distinct normalised header signatures were found (13 before whitespace and case normalisation, since two differ only by case or spacing).
  - Twelve share the column set Chapter | Theme | Measure | Action Number | Action(s) | Steps | Output | Timeline | Lead | Responsible Department or Reporting Lead | Stakeholders | Status… | …text update. They differ only in the wording of the status and text headers. The legacy-exercise workbook adds two impact columns.
  - The 2026 annex starts at Action Number and has no Chapter, Theme, Measure or Responsible Department.
- **Plan marker.** No sheet has a plan-year column. The only marker is the `/YY/` in the reference. Legacy sheets mix `/23/` and `/24/`, and the 2026 annex mixes `/23/` (14), `/24/` (24) and `/25/` (36).
  - The Q2 2023 sheet holds one `/24/` row, `AG/24/2/A (TF)`.
  - References carry trailing NBSP (`LU/25/5\xa0`) and `(TF)` flags, some with an extra space before them.
- **Status values.**
  - Present: `Complete`, `Delayed`, `On Schedule` (1 row) and `Discontinued` (2 rows: the 2024 Q1–Q2 Legacy sheet and the 2025 Q2/Q3 Legacy sheet).
  - Whitespace variants occur: trailing and leading spaces, and one `Delayed` padded with about 140 spaces.
  - No status cell is empty.
- **Colour.** No workbook contains a colour key or legend. Status-cell fill appears only in the CAP25 Q1 workbook, where it matches the text exactly (green/red), and in the 2025 Q4 Legacy sheet, where a theme fill does not track status. No row has fill without text.
- **Cumulative sheets.** Later workbooks repeat earlier-quarter sheets with fewer rows and **changed statuses**: `AD/25/1`, `AG/25/4`, `TR/25/6` and five legacy refs moved between Delayed and Complete. They are restatements as of the later report. No reference repeats across sheets within any one workbook.
- **D-F evidence.** The 102 references in `legacy-actions-from-climate-action-plan-2023.xlsx` (all Delayed) are exactly the 102 Delayed references in the Q4 2023 annex.
- **2026 report.** 74 rows, matching the PDF's Table 1. The code-year split is 14/24/36, while the PDF's Table 3 says CAP23 14, CAP24 23, CAP25 37. The off-by-one was traced in task 1.5 (2026-11-10): by status the annex has CAP24 2 Complete / 22 Delayed and CAP25 5 / 31, while Table 3 has CAP24 2 / 21 and CAP25 5 / 32. So one **Delayed `/24/`** row is counted as CAP25 in the PDF. The only `/24/` Delayed row with a 2025 deadline is `EL/24/5` (Timeline Q1 2025; the 2024 annex declares it with deadline Q1 2025). The PDF text states no per-row plan label for it, so the explanation (Table 3 grouped by deadline year, not code year) is a hypothesis, not evidenced. It is **not** a misprinted reference: every annex reference resolves to a declared action. Attribution is by declared reference, so `EL/24/5` attributes to the 2024 edition regardless. No correction is made. The PDF's only plan labels (8 case-study headings) agree with the code year except `Completed CAP24 Action LU/25/1`, which both the 2023 and 2025 annexes declare (tie-break to 2025 stands; noted for review in 3.3).
- **Undated reports.** Q2 2023 and all three 2025 reports have no `published_date` (`documents.yml` comment: omitted rather than guessed). The 2026 PDF states no date (metadata creationDate 2026-07-27).

## Decisions

### D-B. Attribute by declared reference within the report's listed plans

For each annex row, collect the listed plans (`reports_on`) whose declared actions include the row's normalised reference, with flags separated as `action_references` already does.
- **Exactly one** candidate: attribute the observation to it.
- **Several**: take the candidate whose `edition_year` equals the reference's code year, if exactly one does.
- **Otherwise**: the observation is excluded and logged.
  - `UnattributableObservation` when there is no candidate. It names the report, sheet, row, raw reference and the plans searched.
  - `AmbiguousAttribution` when the tie-break fails.

There is never a fallback to the report's own year and never a nearest-reference match.

*Why not code year alone:* it would misattribute forward-year actions (`RE/24/1`, declared by 2023) and could not choose between two declaring editions. *Why not all editions of the policy:* an explicit per-report list is a reviewable opt-in. It also stops a 2023 report attaching to a CAP24 action that had not been published yet (`AG/24/2/A` in Q2 2023 resolves only if the 2023 annex declares it).

*Text cross-check.* Each attributed observation's normalised action text is compared with its action's published text. A mismatch is logged as a non-blocking `ActionTextMismatch` warning and reviewed (task 3.3). The archived reconciliation showed genuine wording differences (`AD/23/8/A`, `PS/23/12/C`), so the check cannot block.

### D-C. `reports_on` may be a list

`reports_on` accepts a slug or a non-empty list of slugs. Each must be a `role: plan` in the same file sharing the report's `policy_id`. A scalar keeps today's meaning exactly. Observations whose reference is an ordinal (transport, PDF extraction) require exactly one listed plan; otherwise they are logged as `AmbiguousAttribution`. CAP lists:

| Reports | `reports_on` |
|---|---|
| 2023 Q1–Q4 | `[2023-annex]` |
| 2024 Q1–Q2, Q3–Q4 | `[2024-annex, 2023-annex]` |
| 2025 Q1, Q2–Q3, Q4 | `[2025-annex, 2024-annex, 2023-annex]` |
| 2026 Q1–Q2 legacy | `[2025-annex, 2024-annex, 2023-annex]` |

`reports_on` is internal, so the list form is not a contract change.

### D-D. The workbook is an attribute of its report, read by two new steps

- **Entry field.** A report entry with `status_source: annex` may declare `status_annex: {url, format: xlsx}`. `status_annex` without `status_source: annex` is an entry error, and `xlsx` is the only format. Since the workbook is not a document, `fetch_pdfs`, `extract_pages` and the rest of the PDF chain never see it, and nothing needs to skip it.
- **`fetch_status_annexes`.** Reads the curated entries the same way `fetch_pdfs` does and downloads each declared workbook. Validation is payload-based: zip magic `PK\x03\x04`, then openpyxl `load_workbook(read_only=True)` must succeed. Any content type in an allow-list that includes `application/octet-stream` passes. Failures (`AnnexUnreachable`, `AnnexWrongFormat` naming expected and received, `AnnexUnreadable`) are per document and write no record, so the document is retried. The step is stale whenever `documents.yml` changes, not only when its input does (a known runner gotcha for `fetch_pdfs`).
- **`extract_annex_status`.** Takes `fetch_status_annexes` as its input and emits one record per report, in the `extract_action_status` record shape. Each observation additionally carries the raw and normalised reference, the source sheet and row, the raw status, the raw Timeline and the raw action text. Provenance stays internal; no published fields are added.
- **Fan-in.** `resolve_action_identity` also reads `extract_annex_status/output.json` by the same sibling-path convention and exits if it is missing, as it does for `extract_action_status`. Shared-runner multi-input stays out of scope. The new steps are added to `document_pipeline/pipeline.json` after `extract_action_status`, with explicit `input_steps`.

### D-E. Status comes from cell text only

The reviewed status mapping, after normalisation:

| Normalised text | Status |
|---|---|
| `complete` | Complete |
| `delayed` | Delayed |
| `on schedule` | OnSchedule |

Anything else, including `discontinued`, is excluded as `UnmappableStatus` with the raw value. Fill is never read. An empty status cell is `MissingStatus` and excluded, whatever its fill. A fixture pins this: a fill-only cell yields `MissingStatus`, not a status.

### D-F. The legacy-exercise workbook is not ingested

It has no report to date it from, and its content duplicates the Q4 2023 annex's Delayed rows (verified 102 = 102). It is recorded here and in `documents.yml` comments as deliberately excluded.

### D-G. Header layouts are an exact, reviewed table

The parser reads row 1 only. It normalises each header cell (Unicode whitespace collapsed, NBSP included, ends trimmed, casefolded) and requires an **exact** match of the full ordered header against a reviewed table of layout signatures. The table starts with the 13 observed, each mapping its columns to the canonical `reference`, `action_text`, `timeline`, `status` and `status_text`.
- No match: `UnrecognisedAnnexLayout` naming document, sheet and the header found. The sheet is skipped with zero rows.
- Merged or multi-row headers, or a header below row 1, therefore fail closed.
- There is no fuzzy matching. `table_utils.detect_header_row` is not used.
- A new layout is added to the table by a reviewed edit with a fixture.

Every sheet of a declared workbook is read. Earlier-quarter sheets are observations as of this report (Source facts, cumulative sheets).

### D-H. Normalisation is limited and reviewed

The permitted normalisations are:
- Unicode-whitespace collapse and trim on reference, status and timeline.
- Casefolding for status matching.
- Flag separation by the existing `action_references` parser.

Nothing else is rewritten. A reference that `action_references` cannot parse is `UnresolvedActionNumber`, with the raw value logged. A duplicate reference within one report's annex is `DuplicateAnnexReference` and both rows are excluded (none exists today). Timeline parses strictly as `Q[1-4] YYYY`. Any other value (e.g. `Q3 2023 Delayed`) keeps `reported_deadline_raw`, sets the structured deadline fields to null and logs `UnparsedTimeline`.

### D-I. Dates come from the report; undated reports publish nothing

`as_of` = the report entry's `published_date`. Missing dates are curated with evidence: the Taoiseach listing page (read in a browser, since it blocks scripts) or the department's press release, cited in an entry comment. A report still undated after curation emits zero observations and one `MissingReportDate` error. Its date is never taken from PDF metadata alone, file headers, or workbook content.

## Goals / Non-Goals

**Goals:**
- Quarterly CAP status observations publish against the CAP actions, dated from their report.
- Carried-over actions are attributed to the edition that declared them.
- All parsing fails closed.

**Non-Goals:**
- No change to action identity, published fields or the status vocabulary. `Discontinued` is a candidate for a later reviewed change.
- No shared spreadsheet engine, and no runner fan-in.
- No CAP2019/2021 retro-ingestion, and no ingestion of the legacy-exercise workbook.

## Risks / Trade-offs

- **Layout drift.** Each new quarter likely brings a new header wording, so it fails closed until a reviewed layout is added. That is the intended trade: a loud failure instead of a silent mis-map. Pinned `expected_status_counts` catch row loss at publish.
- **A typo'd reference that resolves to a real action.** This is mitigated by the `ActionTextMismatch` review and pinned counts, not prevented. The 2026 off-by-one (task 1.5) is the first test of it.
- **Restated statuses** make several observations per action, one per report. That is intended (the dated series), but the publish diff is large, so triage `errors.json` per step first.
- **Two pipelines touching Excel.** Accepted duplication, to be revisited if a third domain needs it.
