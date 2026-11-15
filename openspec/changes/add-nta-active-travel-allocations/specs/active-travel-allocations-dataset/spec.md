# Spec Delta

## Purpose

Publishes the National Transport Authority's annual Active Travel Investment Grant allocations as a versioned Linked Data dataset of project-level records, joinable to public bodies and comparable across years.

## ADDED Requirements

### Requirement: Versioned and latest distributions

The dataset SHALL be published to a versioned directory and mirrored to `public/latest/`. Each SHALL contain a JSON-LD file, a CSV file, a CSVW metadata file and a `README.md`, and the `latest/` copy SHALL be byte-identical to the newest version.

#### Scenario: Both distributions are present and mirrored

- **WHEN** the dataset is published at its current version
- **THEN** the versioned directory and `public/latest/active-travel-allocations/` each contain the JSON-LD, CSV, CSVW metadata and README files, with identical contents

### Requirement: One record per project allocation

The dataset SHALL publish one record per project allocation row: a project listed under one recipient in one funding stream in one annual document. Each record SHALL carry the allocation year, the recipient, the project code as printed, whether that code is provisional, the project name as printed, the allocation in whole euro, the funding stream, and its source document and page.

#### Scenario: A project allocation becomes one record

- **WHEN** a 2026 document lists project `WCC/25/0003` "Vale Road Pedestrian Improvement Scheme, Arklow" at €350,000 under Wicklow County Council
- **THEN** the dataset contains one 2026 record with that code, name, recipient, €350,000 allocation and source page

#### Scenario: The same project in two years is two records

- **WHEN** a project code appears in both the 2025 and 2026 documents
- **THEN** the dataset contains two records, one per year, each carrying that year's allocation

### Requirement: Stable record identity

Every record SHALL carry an `@id` that is stable across re-runs of unchanged source documents and unique within the dataset. Records whose project code is provisional SHALL NOT be identified by that code.

#### Scenario: Identity survives a re-run

- **WHEN** the pipeline is run twice over the same documents with no source change
- **THEN** every record keeps the same `@id`

#### Scenario: Provisional codes do not collide

- **WHEN** one recipient's section lists two projects that both print the provisional code `WCC/26/XXXX`
- **THEN** they are published as two records with distinct `@id` values

### Requirement: Local-authority linkage and other recipients

A record whose recipient is a local authority SHALL carry `public_body` equal to that body's `@id` in the Public Bodies dataset, and the corresponding `public_body_id`. A record whose recipient is not a local authority SHALL carry the recipient name as printed and no `public_body`.

#### Scenario: Local authority joins to public-bodies

- **WHEN** an allocation belongs to South Dublin County Council
- **THEN** its `public_body` is that body's published URI and its `public_body_id` is present

#### Scenario: Non-local-authority recipient is kept as printed

- **WHEN** an allocation belongs to a recipient in the document's campuses, hospitals and others block
- **THEN** the record carries the printed recipient name and no `public_body`

#### Scenario: Unresolvable local authority aborts publication

- **WHEN** a local-authority recipient cannot be resolved to a public body
- **THEN** publication fails and no dataset is written, rather than emitting a record without its body link

### Requirement: Closed funding-stream vocabulary

The `funding_stream` field SHALL be one of `active_travel` or `other_nta_streams`, and the JSON Schema SHALL constrain it to that set. No record SHALL carry an unlisted stream.

#### Scenario: Every published stream is a vocabulary term

- **WHEN** every published record is validated
- **THEN** each `funding_stream` value is `active_travel` or `other_nta_streams`

#### Scenario: Schema and dataset agree on the vocabulary

- **WHEN** the JSON Schema's allowed stream values and the published records are compared
- **THEN** no record uses a term the schema does not allow

### Requirement: Allocations are whole euro

Every published `allocation_eur` SHALL be a non-negative integer number of euro. A source row whose amount cannot be read as such SHALL NOT be published with a substituted value.

#### Scenario: Thousand separators are not part of the value

- **WHEN** a row prints its allocation as `€1,100,000`
- **THEN** the published record carries `1100000`

#### Scenario: An unreadable amount is not published

- **WHEN** a row's amount cell cannot be read as a whole-euro figure
- **THEN** no record is published from that row and the run records an error naming it

### Requirement: Catalogue metadata and schema

The dataset SHALL publish DCAT-AP metadata at `public/catalog/dataset-active-travel-allocations.ttl`, related to the Public Bodies dataset via `dct:relation`, and a JSON Schema under `public/schemas/`. Every published record SHALL validate against the schema.

#### Scenario: Records validate against the schema

- **WHEN** the published JSON-LD records are validated against the dataset schema
- **THEN** every record passes

#### Scenario: Catalogue entry relates to public bodies

- **WHEN** the DCAT-AP metadata is read
- **THEN** it declares the dataset and relates it to the Public Bodies dataset

### Requirement: Content-stamped modification date

`dct:modified` in the catalogue metadata SHALL change only when the published payload content actually changes, and `owl:versionInfo` SHALL change only for a schema or shape change made deliberately.

#### Scenario: Unchanged content leaves the date untouched

- **WHEN** the publisher runs and the generated payloads are identical to those on disk
- **THEN** no payload is rewritten and `dct:modified` is unchanged

#### Scenario: Changed content stamps the date

- **WHEN** the publisher runs and a generated payload differs from disk
- **THEN** the payloads are written and `dct:modified` is set to the current date

### Requirement: Discoverability on the entry pages

The dataset SHALL be linked from `public/get-the-data.html` (its CSV download, described in plain English) and from the reference list on `public/index.html` (its README).

#### Scenario: Get the data links the CSV

- **WHEN** a user opens `get-the-data.html`
- **THEN** the page links to the dataset's CSV and describes a grant allocation in plain English

#### Scenario: Reference list links the README

- **WHEN** a user opens `index.html`
- **THEN** the reference list links to the dataset's README
