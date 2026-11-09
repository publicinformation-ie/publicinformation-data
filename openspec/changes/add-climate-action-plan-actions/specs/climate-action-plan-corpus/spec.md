# Spec Delta

## MODIFIED Requirements

### Requirement: Corpus composition and provenance

The corpus SHALL cover the Climate Action Plan 2023, 2024 and 2025 Plan PDFs and their Annex of Actions PDFs from the Department of Climate, Energy and the Environment listing pages, and the quarterly progress-report PDFs published under those plans by the Department of the Taoiseach. Every entry SHALL record its publisher and a `public_body_id` verified against the Public Bodies dataset, using the department's current verified identifier even where the department's published name predates its current title.

#### Scenario: Plan year coverage

- **WHEN** the corpus is curated and validated
- **THEN** each plan year from 2023 through 2025 has exactly one Plan document, exactly one Annex of Actions document, and at least one progress report that reports on that year's plan

#### Scenario: Publisher identity

- **WHEN** entries for the Plans, the Annexes of Actions and the progress reports are created
- **THEN** the Plans and Annexes identify the Department of Climate, Energy and the Environment and the progress reports identify the Department of the Taoiseach, each by its verified dataset identifier

## ADDED Requirements

### Requirement: Annex of Actions documents are the corpus's action sources

Each plan year's Annex of Actions document SHALL be curated as that edition's action source, so the actions it declares publish in the actions dataset under the annex's own slug (`climate-action-plan-<year>-annex-of-actions`). Plan documents and progress reports SHALL remain non-sources, so each action is extracted once, from its annex.

#### Scenario: Annex yields the edition's actions

- **WHEN** a plan year's Annex of Actions is processed end to end
- **THEN** its declared actions publish in the actions dataset under the annex's slug

#### Scenario: Plan and report documents yield no actions

- **WHEN** a CAP Plan document or progress report is processed
- **THEN** action extraction emits no rows for it

## REMOVED Requirements

### Requirement: Plan documents are not action sources in this corpus

**Reason**: The corpus now deliberately has action sources, the Annex of Actions documents. Plan documents stay non-sources, which is restated in "Annex of Actions documents are the corpus's action sources".

**Migration**: None. No published action or document changes identity, and Plan documents remain non-sources.
