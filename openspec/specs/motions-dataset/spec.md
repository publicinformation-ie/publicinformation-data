## Purpose

Publishes the motions moved at Irish local-authority meetings as a curated, versioned Linked Data dataset, so they can be consumed and joined to public bodies like every other dataset in the catalogue.

## Requirements

### Requirement: Versioned and latest distributions

The motions dataset SHALL publish a versioned distribution at `public/v1.0.0/motions/` and a mirror at `public/latest/motions/`. Each SHALL contain a JSON-LD file, a CSV file, a CSVW metadata file, and a `README.md`. The `latest/` copy SHALL always mirror the newest version.

#### Scenario: Both distributions are present and mirrored

- **WHEN** the dataset is published at version 1.0.0
- **THEN** `public/v1.0.0/motions/` and `public/latest/motions/` each contain `motions.jsonld`, `motions.csv`, `motions.csv-metadata.json`, and `README.md`, with identical file contents

### Requirement: Stable record identity and body linkage

Every motion record SHALL carry an `@id` derived from its canonical `motion_id`, and a `public_body` field whose value is the same URI published as `@id` for that body in the Public Bodies dataset. A `public_body_id` that cannot be resolved to a known body SHALL fail publication rather than be guessed or dropped.

#### Scenario: Record identity is derived from motion_id

- **WHEN** a canonical motion has `motion_id` `meath/2026-05-20/m001`
- **THEN** its published `@id` is `https://data.publicinformation.ie/motion/meath/2026-05-20/m001`

#### Scenario: Body linkage joins to public-bodies

- **WHEN** a motion belongs to the body with slug `meath`
- **THEN** its `public_body` is `https://data.publicinformation.ie/body/meath`, matching the `@id` published in the Public Bodies dataset

#### Scenario: Unresolvable body aborts publication

- **WHEN** a motion's `public_body_id` has no matching record in the Public Bodies data
- **THEN** the publisher raises an error and writes no dataset, rather than emitting a motion with a missing or invented `public_body`

### Requirement: JSON-LD and CSV serialisations

The dataset SHALL publish every motion as a node in a single JSON-LD `@context` + `@graph` document, and as one row per motion in a CSV file. The CSVW metadata SHALL declare the CSV's columns and types. Each motion SHALL retain `meeting_date`, `meeting_type`, `municipal_district`, `source_file_url`, `motion_text`, `proposer`, `seconder`, and `status`.

#### Scenario: JSON-LD wraps all records

- **WHEN** the dataset is published
- **THEN** the JSON-LD file contains one `@graph` array holding every motion record

#### Scenario: CSV has one row per motion

- **WHEN** the dataset contains N motions
- **THEN** `motions.csv` contains N data rows, one per motion, with the documented columns

### Requirement: Closed status vocabulary

The `status` field SHALL be one of the terms in the published `motion-status` vocabulary: `carried`, `carried_as_amended`, `not_carried`, `withdrawn`, `deferred`, `not_recorded`. The JSON Schema SHALL constrain `status` to this set.

#### Scenario: Published statuses are all vocabulary terms

- **WHEN** every published motion record is validated
- **THEN** each `status` value is one of the six vocabulary terms

#### Scenario: Vocabulary and schema agree

- **WHEN** the `motion-status` vocabulary and the JSON Schema `status` enum are compared
- **THEN** they list exactly the same terms

### Requirement: Catalogue metadata and schema

The dataset SHALL publish DCAT-AP metadata at `public/catalog/dataset-motions.ttl`, related to the Public Bodies dataset via `dct:relation`, and a JSON Schema at `public/schemas/motions.schema.json`. Every published record SHALL validate against the schema.

#### Scenario: Records validate against the schema

- **WHEN** the JSON-LD `@graph` records are validated against `motions.schema.json`
- **THEN** every record passes

#### Scenario: Catalogue entry relates to public bodies

- **WHEN** the DCAT-AP metadata is read
- **THEN** it declares the dataset and includes a `dct:relation` to the Public Bodies dataset

### Requirement: Content-stamped modification date

`dct:modified` in the catalogue metadata SHALL be updated only when the published payload content actually changes, and `owl:versionInfo` SHALL be bumped by hand only for breaking or additive schema changes.

#### Scenario: Unchanged content leaves the date untouched

- **WHEN** the publisher runs and the generated payloads are byte-identical to those on disk
- **THEN** `dct:modified` is not rewritten

#### Scenario: Changed content stamps the date

- **WHEN** the publisher runs and any generated payload differs from disk
- **THEN** the payloads are written and `dct:modified` is set to the current date

### Requirement: Discoverability on the open-data entry pages

The dataset SHALL be linked from `public/get-the-data.html` (its CSV download with a plain-English description) and from the `#reference` list on `public/index.html` (its README), consistent with the existing discovery guard.

#### Scenario: Get the Data links the CSV

- **WHEN** a user opens `get-the-data.html`
- **THEN** the page links to `latest/motions/motions.csv` and describes what a motion is in plain English

#### Scenario: Reference list links the README

- **WHEN** a user opens `index.html`
- **THEN** the `#reference` list links to `latest/motions/README.md`