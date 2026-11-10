## Purpose

Defines the composition and governance of the Climate Action Plan (CAP23–CAP25) document corpus inside the document pipeline: which documents exist per plan year, what each document's role is, how a progress report links to the plan it reports on, how a report whose status detail is published outside its PDF is declared, and the identity conventions that bind once a document is published.

## Requirements

### Requirement: Corpus composition and provenance

The corpus SHALL cover the Climate Action Plan 2023, 2024 and 2025 Plan PDFs and their Annex of Actions PDFs from the Department of Climate, Energy and the Environment listing pages, and the quarterly progress-report PDFs published under those plans by the Department of the Taoiseach. Every entry SHALL record its publisher and a `public_body_id` verified against the Public Bodies dataset, using the department's current verified identifier even where the department's published name predates its current title.

#### Scenario: Plan year coverage

- **WHEN** the corpus is curated and validated
- **THEN** each plan year from 2023 through 2025 has exactly one Plan document, exactly one Annex of Actions document, and at least one progress report that reports on that year's plan

#### Scenario: Publisher identity

- **WHEN** entries for the Plans, the Annexes of Actions and the progress reports are created
- **THEN** the Plans and Annexes identify the Department of Climate, Energy and the Environment and the progress reports identify the Department of the Taoiseach, each by its verified dataset identifier

### Requirement: Annual plans are editions of one climate policy

Every CAP document SHALL belong to a single climate `policy_id`, with each annual Plan document curated as an edition of that policy rather than as a policy of its own. A progress report SHALL name the plan edition it reports on, and SHALL share that plan's `policy_id`.

#### Scenario: Reports resolve to their plan edition

- **WHEN** a progress report for a given plan year is validated
- **THEN** it resolves to that year's Plan document and both carry the same climate `policy_id`

#### Scenario: Report naming no plan is fatal

- **WHEN** a progress report names no plan, or names one belonging to a different policy
- **THEN** validation fails process-fatally, naming the entry

### Requirement: Reports whose status detail is published elsewhere

A progress report whose machine-readable status detail is published in a companion file rather than inside its PDF SHALL declare that fact on its entry, and PDF status extraction SHALL skip it by declaration — emitting no status record and no unrecognized-format error. A report carrying no such declaration SHALL continue to be read, and to error, exactly as before.

#### Scenario: Declared external status source

- **WHEN** a progress report declaring an external status source is processed
- **THEN** it contributes no status observations and no unrecognized-format error, and it still publishes as a document bundle

#### Scenario: Undeclared unrecognised report

- **WHEN** a report carries no external-status declaration and its layout is not recognised
- **THEN** it records an unrecognized-format error as it does today

### Requirement: Permanent identity conventions

Corpus `doc_slug` values SHALL be stable lowercase identifiers that encode the plan year, and the reporting quarters where applicable, chosen before first publication and never changed afterwards. A document's `title` SHALL come from the source PDF itself and its `published_date` from the page or document metadata — never guessed from a download filename.

#### Scenario: Retitled document keeps its address

- **WHEN** a published entry's title is corrected after publication
- **THEN** its `doc_slug` and every previously published address remain unchanged

#### Scenario: Slug encodes year and quarters

- **WHEN** a progress report covering more than one quarter is curated
- **THEN** its slug encodes its plan year and each quarter it covers, distinguishing it from every other report for that year

### Requirement: Published corpus matches the curated corpus

The published document index SHALL account for exactly the curated set: every curated document SHALL appear either as published or as explicitly failed, with a reason. A curated document missing from the index SHALL fail verification rather than publish silently.

#### Scenario: Curated entry that fails to process

- **WHEN** a curated CAP document cannot be processed
- **THEN** it appears in the index's failed list with a reason, and verification of the published corpus still passes

#### Scenario: Curated entry absent from the index

- **WHEN** a curated CAP document appears neither as published nor as failed
- **THEN** verification fails

### Requirement: Image-only pages are machine-read and labelled

A page that a curator has listed under `ocr_pages` in `documents.yml`, and that is a full-page raster image with no meaningful text layer, SHALL be read with a deterministic OCR pass in its own pipeline step (`ocr_pages`), which never modifies the upstream page extraction, so its content is covered rather than silently dropped or papered over as furniture. Text derived from OCR SHALL be marked as machine-read in the pipeline's intermediate records and in the published bundle (section text and `meta.json`), and OCR pages that return no text or low confidence SHALL be logged for human review. An OCR page that returns no text SHALL NOT count as covered.

#### Scenario: Image-only page is read

- **WHEN** a progress-report page is a full-page image with no text layer
- **THEN** its OCR text is assigned to a section, the section's body states that pages are machine-read, and `meta.json` lists them under the section's `ocr_pages`

#### Scenario: OCR is opt-in per page

- **WHEN** a page is image-only but not listed under its document's `ocr_pages`
- **THEN** it is never OCR'd and its extracted output is unchanged

#### Scenario: Listed page is not scanned

- **WHEN** `ocr_pages` lists a page that has a real text layer, no full-page image, or does not exist
- **THEN** the page is not OCR'd and an `OcrPageNotScanned` error is logged

#### Scenario: OCR finds nothing

- **WHEN** OCR of an image-only page returns no text
- **THEN** the page remains a coverage gap, an `OcrEmpty` error is logged, and the document stays withheld

### Requirement: Annex of Actions documents are the corpus's action sources

Each plan year's Annex of Actions document SHALL be curated as that edition's action source, so the actions it declares publish in the actions dataset under the annex's own slug (`climate-action-plan-<year>-annex-of-actions`). Plan documents and progress reports SHALL remain non-sources, so each action is extracted once, from its annex.

#### Scenario: Annex yields the edition's actions

- **WHEN** a plan year's Annex of Actions is processed end to end
- **THEN** its declared actions publish in the actions dataset under the annex's slug

#### Scenario: Plan and report documents yield no actions

- **WHEN** a CAP Plan document or progress report is processed
- **THEN** action extraction emits no rows for it

### Requirement: Annex table layouts are declared per document

Layout handling that differs from the default table reading SHALL be enabled only by an explicit declaration on a document's entry, drawn from a closed set of layout behaviours. A document without the declaration SHALL be read exactly as before. An unknown behaviour, or a declaration on a document that is not an action source, SHALL be a fatal validation error.

#### Scenario: Declared annex layout

- **WHEN** an Annex of Actions entry declares that tables continue across pages without a header
- **THEN** a headerless continuation table is read with the header of the table it continues, and its actions are extracted

#### Scenario: Continuation without an empty spacer column

- **WHEN** a declared continuation table lacks a column that is empty in every row of the table it continues
- **THEN** it is still read with that table's header, mapped onto the non-empty columns

#### Scenario: Undeclared documents are unaffected

- **WHEN** every curated action plan is re-extracted after layout handling is added
- **THEN** the output for documents without a declaration is byte-identical to before

#### Scenario: Invalid declaration

- **WHEN** an entry declares an unknown layout behaviour, or declares one on a document that is not an action source
- **THEN** validation fails process-fatally, naming the entry
