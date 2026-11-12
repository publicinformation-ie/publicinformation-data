# Spec Delta

## Purpose

Covers ingestion of a status annex, a machine-readable companion workbook in which a progress report publishes the status of plan actions. The annex is declared on its report, acquired, and parsed into dated status observations that are attributed to the plan edition declaring each action. Action identity, citability and URIs are specified by `public-body-actions-dataset`.

## ADDED Requirements

### Requirement: A report declares its status annex

A progress report entry that declares `status_source: annex` MAY declare a `status_annex` with a URL and a format, where `xlsx` is the only accepted format. A `status_annex` on an entry without `status_source: annex`, or with an unknown format, SHALL be rejected as an entry error. A status annex is an attachment of its report and SHALL NOT be processed as a corpus document by the PDF steps.

#### Scenario: Declared annex

- **WHEN** a report entry declares `status_source: annex` and a `status_annex` of format `xlsx`
- **THEN** the annex is acquired and parsed by the annex steps, and the report still publishes as a document bundle from its PDF

#### Scenario: Annex without an external status source

- **WHEN** an entry declares `status_annex` but not `status_source: annex`
- **THEN** curation validation fails naming the entry

### Requirement: A report may observe several plans

A report's `reports_on` SHALL accept either one plan slug or a non-empty list of plan slugs. Each slug SHALL name a `role: plan` entry sharing the report's `policy_id`. A single slug SHALL keep its existing meaning unchanged.

#### Scenario: Report spanning plan years

- **WHEN** the Q1&Q2 2026 legacy report lists the 2023, 2024 and 2025 Annexes of Actions
- **THEN** the entry validates, and its observations may attribute to any of the three

#### Scenario: Listed slug is not a plan of the same policy

- **WHEN** a listed slug is missing, is not a plan, or has a different `policy_id`
- **THEN** curation validation fails naming the report and the slug

### Requirement: Annex acquisition records errors per document

Annex acquisition SHALL validate the payload itself and not its declared content type: it SHALL be a zip container that the spreadsheet reader can open. Failures (unreachable source, wrong payload format, unreadable file) SHALL be recorded against the failing document only, leaving the run and every other document unaffected. A failed document SHALL NOT be marked processed, so that it is retried once its entry or its source is fixed.

#### Scenario: Generic content type with a valid workbook

- **WHEN** the annex URL serves a readable XLSX as `application/octet-stream`
- **THEN** acquisition succeeds

#### Scenario: Wrong payload format

- **WHEN** the URL declared for an annex returns a payload of a different format than declared
- **THEN** the document records an acquisition error naming the expected and received format, and no other document is affected

#### Scenario: Failure does not mark the document processed

- **WHEN** a document's annex fails to acquire and the step is re-run after the source is fixed
- **THEN** the document is retried rather than skipped as already processed

### Requirement: Fail-closed header detection

The annex parser SHALL accept a worksheet's header only if its first row, after whitespace and case normalisation, exactly equals the full ordered header of a layout in a reviewed layout table. Otherwise the worksheet SHALL be skipped with a classified error, and its header SHALL NOT be matched approximately, sought in another row, or reduced to the columns that matched. Every worksheet of a declared annex SHALL be read.

#### Scenario: Unrecognised header shape

- **WHEN** a worksheet's header matches no reviewed layout
- **THEN** the worksheet is skipped and an error is recorded identifying the document, worksheet and header found, with zero rows emitted from it

#### Scenario: Merged or multi-row header

- **WHEN** a worksheet's header is merged across cells, spans several rows, or sits below the first row
- **THEN** it does not match a reviewed layout and is skipped with an error

#### Scenario: Recognised header yields every row

- **WHEN** a worksheet's header is recognised
- **THEN** every data row is either emitted or individually error-logged, and none is dropped silently

### Requirement: No value is coerced to make a row fit

The only normalisations permitted SHALL be whitespace collapse and trimming, casefolding for status matching, and the separation of printed flags from references. A cell that cannot be confidently interpreted SHALL be preserved raw with an error logged, and SHALL NOT be silently nulled, rewritten, or mapped to a nearest acceptable value.

#### Scenario: Ambiguous date cell

- **WHEN** a row's timeline cannot be parsed strictly as a quarter and year
- **THEN** its raw text is preserved, its structured deadline fields are null, and an error is logged

#### Scenario: Partially interpretable row

- **WHEN** one cell of an otherwise readable row cannot be interpreted
- **THEN** the row is not rewritten to fit, and the failure is attributable to that cell

#### Scenario: Duplicate reference within one annex

- **WHEN** the same reference appears on two rows of one report's annex
- **THEN** both rows are excluded and an error names the reference and both locations

### Requirement: Status vocabulary is closed and extended only deliberately

Status SHALL be read from cell text only, and cell formatting such as fill colour SHALL NOT be read as status. A status that does not map through the reviewed mapping to the closed status vocabulary SHALL be excluded and logged with its raw value, never coerced to the nearest member. Where a source genuinely expresses a state the vocabulary lacks, the vocabulary SHALL be extended as a reviewed, recorded contract change, never widened at parse time.

#### Scenario: Unmappable status value

- **WHEN** a row's status is `Discontinued`, or any other text outside the reviewed mapping
- **THEN** that observation is excluded and an error names the row and the raw unnormalized value

#### Scenario: Status conveyed only by fill

- **WHEN** a status cell is empty but filled with a colour
- **THEN** no status is inferred, and the observation is excluded with a missing-status error

#### Scenario: Genuinely new state

- **WHEN** inspection shows a source state that the vocabulary cannot express
- **THEN** the vocabulary is extended by a reviewed change with its contract and changelog records, not by the parser

### Requirement: Status observations are dated from their report

Each status observation SHALL take its as-of date from the curated publication date of the report that made it. It SHALL never be inferred from the observation's content, from the workbook or its sheet names, or from file metadata alone. A report with no curated publication date SHALL contribute no observations and SHALL record one error.

#### Scenario: Observation date comes from the report

- **WHEN** observations are derived from an annex accompanying a dated report
- **THEN** each observation's as-of date is that report's publication date, including those read from sheets restating earlier quarters

#### Scenario: Undated report

- **WHEN** a report declaring an annex has no publication date
- **THEN** no observations are emitted for it and a missing-date error names the report

### Requirement: Observations are attributed to the plan that declared the action

A status observation SHALL be attributed to a plan only if that plan is listed in the report's `reports_on` and declares the observation's reference. If several listed plans declare it, the observation SHALL be attributed to the one whose edition year equals the reference's code year, provided exactly one does.

#### Scenario: Carried-over action observed in a later report

- **WHEN** a 2025 report's annex lists `EN/23/6` and its `reports_on` includes the 2023 annex, which declares it
- **THEN** the observation is attributed to the 2023 edition's action

#### Scenario: Forward-year action

- **WHEN** a 2023 report observes `RE/24/1`, which the 2023 annex declares, and its `reports_on` lists only the 2023 annex
- **THEN** the observation is attributed to the 2023 edition's action

#### Scenario: Reference declared by two listed editions

- **WHEN** a 2025 report observes `LU/25/1`, which both the 2023 and 2025 annexes declare
- **THEN** the observation is attributed to the 2025 edition, whose year matches the code year

### Requirement: Unattributable observations are excluded, never reassigned

An observation that matches no listed plan, or whose attribution remains ambiguous, SHALL be excluded and logged. It SHALL never be assigned to the observing report's own plan as a fallback, and never attached to a neighbouring action.

#### Scenario: Unattributable observation

- **WHEN** an observation's reference is declared by none of the report's listed plans
- **THEN** it is excluded and an error names the report, the sheet and row, the raw reference and the plans searched

#### Scenario: Ambiguous attribution

- **WHEN** two listed plans declare the reference and neither, or both, has the reference's code year as its edition year
- **THEN** it is excluded and an ambiguity error names both plans

### Requirement: Attributed text disagreements are surfaced

Where an attributed observation's action text, after whitespace normalisation, differs from its action's published text, the disagreement SHALL be logged as a non-blocking warning naming the reference and both texts, for review before publication.

#### Scenario: Text mismatch

- **WHEN** an annex row's action text differs from the declared action's text
- **THEN** the observation still publishes, and a warning records the reference with both texts
