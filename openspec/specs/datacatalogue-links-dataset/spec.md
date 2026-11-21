## Purpose

Publishes a link dataset that connects each canonical Irish public body to its organisation page on datacatalogue.gov.ie. Links come from deterministic name matching plus committed manual overrides, and a link is published only where a public body is resolved.

## Requirements

### Requirement: Complete organisation fetch

The pipeline SHALL fetch every organisation that datacatalogue.gov.ie lists at `https://datacatalogue.gov.ie/organization/`, following every page of the listing. Each fetched record SHALL carry the organisation's slug, display name and absolute organisation page URL.

#### Scenario: Paginated listing is fetched in full
- **WHEN** the organisation listing spans more than one page
- **THEN** the fetch output contains the organisations from every page, with no duplicate slugs

#### Scenario: Record carries identity and URL
- **WHEN** an organisation with slug `revenue-commissioners` is fetched
- **THEN** its record carries that slug, its display name, and the URL `https://datacatalogue.gov.ie/organization/revenue-commissioners`

### Requirement: Fetch fails closed

The fetch step SHALL exit non-zero, and SHALL NOT write output, when a request fails, the source returns a non-success status or a response that cannot be parsed, or zero organisations are found.

#### Scenario: Source unreachable
- **WHEN** a request to datacatalogue.gov.ie fails or returns an HTTP error status
- **THEN** the step exits non-zero, and any earlier output is left as it was

#### Scenario: Empty listing
- **WHEN** the source parses successfully but yields zero organisations
- **THEN** the step exits non-zero instead of publishing an empty dataset

### Requirement: Only active organisations are kept

The fetch SHALL drop entries that the source marks as not an organisation, or as deleted or draft, where the source exposes those markers.

#### Scenario: Deleted organisation excluded
- **WHEN** the source returns an organisation whose state is not active
- **THEN** that organisation does not appear in the fetch output

### Requirement: Deterministic name matching

Each organisation SHALL be matched to at most one canonical public body by normalised-name fuzzy matching. The algorithm and acceptance threshold SHALL be the same as the other public-body link pipelines. A match log SHALL record each organisation's normalised name, best candidate and score.

#### Scenario: Name above threshold
- **WHEN** an organisation's normalised name scores at or above the shared threshold against a public body
- **THEN** the record carries that body's `public_body_id`, and the match log records the score

#### Scenario: Name below threshold
- **WHEN** no public body scores at or above the threshold
- **THEN** the record's `public_body_id` is null

### Requirement: Manual overrides take precedence

A committed override file keyed by organisation slug SHALL set `public_body_id`, and an override value SHALL always replace the automated match. A non-null value SHALL assign that body. An explicit null SHALL suppress the automated match. Slugs absent from the file SHALL keep their automated result.

#### Scenario: Override corrects a missed match
- **WHEN** the override file maps slug `x` to body `1608` and the automated match for `x` was null
- **THEN** the resolved record for `x` carries `public_body_id` 1608

#### Scenario: Override suppresses a false match
- **WHEN** the override file maps slug `y` to null and the automated match for `y` was body `42`
- **THEN** `y` is unresolved and is not published

### Requirement: Unresolved organisations are dropped and counted

Organisations still without a `public_body_id` after overrides SHALL be left out of the published dataset. They SHALL NOT fail the run. The step SHALL report how many were matched, how many came through an override, and how many were dropped.

#### Scenario: Partial resolution
- **WHEN** 300 organisations are fetched and 120 resolve to a public body
- **THEN** the resolved output holds 120 records, and the step reports 120 matched and 180 dropped

### Requirement: Published record contract

Each published record SHALL carry a stable `@id` of the form `https://data.publicinformation.ie/datacatalogue-gov-ie-links/<slug>`. It SHALL also carry the linked body's URI from the `public-bodies` dataset, the organisation slug, and the organisation URL. Dataset count and description SHALL be included only where the source provides them.

#### Scenario: Body URI matches public-bodies
- **WHEN** a record resolves to `public_body_id` 1608
- **THEN** its `public_body` value equals the `@id` that the `public-bodies` dataset publishes for body 1608

#### Scenario: Unknown body id
- **WHEN** a resolved record carries a `public_body_id` that is not in the public-bodies data
- **THEN** the transform fails with an error naming the id, and does not drop the record or publish a guessed URI

### Requirement: JSON-LD and CSV distributions

The dataset SHALL be published as one JSON-LD document (top-level `@context` and `@graph`) and one CSV file with CSVW metadata, under `public/v1.0.0/datacatalogue-gov-ie-links/`, and copied to `public/latest/datacatalogue-gov-ie-links/`. The JSON-LD SHALL validate against `public/schemas/datacatalogue-gov-ie-links.schema.json`.

#### Scenario: Schema validation
- **WHEN** the published JSON-LD is validated against the dataset's JSON Schema
- **THEN** every record passes, with all required fields present

#### Scenario: CSV mirrors JSON-LD
- **WHEN** both distributions are generated from the same run
- **THEN** the CSV has one row per JSON-LD record, with the same identifiers and URLs

### Requirement: Catalogue entry and content-only freshness

The dataset SHALL have a DCAT-AP entry at `public/catalog/dataset-datacatalogue-gov-ie-links.ttl` with `owl:versionInfo` "1.0.0". It SHALL relate to the `public-bodies` dataset and name datacatalogue.gov.ie as the source. `dct:modified` SHALL change only when the generated content changes.

#### Scenario: Re-run without changes
- **WHEN** the transform runs again and the generated JSON-LD and CSV are byte-identical
- **THEN** `dct:modified` in the catalogue entry is unchanged

#### Scenario: Content changes
- **WHEN** a re-run adds or removes a link
- **THEN** the files are rewritten, `latest/` is refreshed, and `dct:modified` is set to the run date

### Requirement: Dataset is discoverable

The dataset SHALL be listed in the repository `README.md` dataset table, with its record count, and on `public/get-the-data.html`. The source SHALL be credited in `DATA_SOURCES.md`.

#### Scenario: README count stays accurate
- **WHEN** the README dataset-count test runs
- **THEN** the count listed for datacatalogue.gov.ie Links equals the number of rows in the published CSV
