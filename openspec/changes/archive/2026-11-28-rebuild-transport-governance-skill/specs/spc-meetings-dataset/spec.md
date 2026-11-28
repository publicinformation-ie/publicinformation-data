# Spec Delta

## MODIFIED Requirements

### Requirement: Closed vocabularies are published

Attendance status, attendance mode, attendee category, decision type, text source, COFOG
1999 codes and transport-activity groupings SHALL each be published as a vocabulary under
`public/vocabularies/`. The retired transport subdomain vocabulary SHALL stay published at
its existing CSV and CSVW URLs, with every term marked deprecated and linked to its
replacement grouping in published Turtle, so an existing link keeps working and a consumer
learns the term is retired. The JSON Schema SHALL constrain each field to its vocabulary's
terms.

#### Scenario: Schema rejects an unknown status

- **WHEN** an attendance record with status `late` is validated against the JSON Schema
- **THEN** validation fails

#### Scenario: New terms are accepted

- **WHEN** an attendance record with category `absent` and status `absent`, or category
  `guests` and status `present`, is validated against the JSON Schema
- **THEN** validation passes

#### Scenario: Schema rejects an unknown grouping

- **WHEN** an item record with grouping `RT99` is validated against the JSON Schema
- **THEN** validation fails

#### Scenario: Retired term still resolves

- **WHEN** a consumer opens the transport subdomain CSV or its Turtle at the published URL
- **THEN** the file is present, and the Turtle marks each term `owl:deprecated` with a
  `dct:isReplacedBy` link to the grouping that replaces it

## ADDED Requirements

### Requirement: The items table publishes transport groupings

Each published agenda item SHALL carry a `groupings` field holding transport-activity
grouping IDs, as an array in JSON-LD and pipe-separated in CSV with CSVW declaring the
separator. The field SHALL be empty for an item with no transport grouping, and null when
the item's topics are withheld.

#### Scenario: Reading an item in CSV

- **WHEN** a consumer opens `items.csv` for a transport item
- **THEN** the `groupings` cell holds grouping IDs such as `RT1`, not subdomain IDs such as
  `infra/regional-local-roads`

#### Scenario: Withheld topics

- **WHEN** an item's topics were withheld for an error
- **THEN** its `groupings` is null in JSON-LD and its `topics_published` is false

### Requirement: The breaking field change is released as 2.0.0

Replacing `subdomains` with `groupings` removes a published field, so the dataset SHALL be
released as `2.0.0` under `public/v2.0.0/spc-meetings/`, with `latest` mirroring it, an
`owl:versionInfo` of `2.0.0` in the catalogue record, and a `public/CHANGELOG.md` entry
naming the removed field and its replacement. Earlier releases SHALL stay in place.

#### Scenario: Old release unchanged

- **WHEN** the new release is published
- **THEN** `public/v1.2.0/spc-meetings/` still holds the previous files

#### Scenario: Version recorded

- **WHEN** the catalogue record is read
- **THEN** its `owl:versionInfo` is `2.0.0` and the changelog names the rename
