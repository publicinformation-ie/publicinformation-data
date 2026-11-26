## Purpose

Publishes SPC meetings, the people who attended them, their attendance, agenda items with topics, decisions and verbatim minutes as a curated, versioned Linked Data dataset. It joins to Public Bodies and councillor IDs like the rest of the catalogue, and is the contract the website consumes.

## Requirements

### Requirement: Versioned and latest distributions

The dataset SHALL be published at `public/v1.0.0/spc-meetings/` and mirrored at `public/latest/spc-meetings/`. Each SHALL contain a JSON-LD file and a CSV file with CSVW metadata for each of meetings, people, attendance, agenda items and decisions, plus a `minutes/` folder and a `README.md`.

#### Scenario: Latest mirrors the versioned release

- **WHEN** the dataset is exported
- **THEN** every file under `public/v1.0.0/spc-meetings/` exists with identical bytes under `public/latest/spc-meetings/`

### Requirement: One verbatim Markdown file per published meeting

The `minutes/` folder SHALL hold one rendered Markdown file per meeting that passed the word-preservation check, at `minutes/<council_slug>/<committee_slug>/<YYYY-MM-DD>.md`. Each meeting record SHALL give that path.

#### Scenario: Minutes file path

- **WHEN** the 19 February 2026 Meath meeting is published
- **THEN** its minutes are at `minutes/meath/transportation-urban-regeneration/2026-02-19.md` and its meeting record's `minutes_path` gives that path

### Requirement: Records have stable URIs

Every meeting, person, attendance, agenda item and decision record SHALL carry an `@id` of the form `https://data.publicinformation.ie/spc-meetings/<kind>/<id>`. Attendance IDs are `<meeting_id>/<person_id>`, item IDs are `<meeting_id>/item-<N-N>`, and the other IDs are as defined by their capabilities. An ID published once SHALL NOT be reassigned to a different record.

#### Scenario: Meeting URI

- **WHEN** the meeting `meath/transportation-urban-regeneration/2026-02-19` is published
- **THEN** its `@id` is `https://data.publicinformation.ie/spc-meetings/meeting/meath/transportation-urban-regeneration/2026-02-19`

### Requirement: Records link to Public Bodies and councillors

Each meeting SHALL carry a `public_body` field holding the URI published for its body in the Public Bodies dataset. Each person of kind `councillor` SHALL carry the councillor ID used by the motions dataset, so attendance and motions can be joined.

#### Scenario: Body link

- **WHEN** a Meath meeting is published
- **THEN** its `public_body` equals the `@id` of Meath County Council in the Public Bodies dataset

#### Scenario: Councillor join

- **WHEN** Cllr Sean Drew's person record is published
- **THEN** its `councillor_id` is `meath/sean-drew`

### Requirement: Attendance can be counted per person

The attendance distribution SHALL hold one row per person per meeting at which they are recorded, with meeting ID, meeting date, person ID, category, role as printed, status and mode. Meetings whose attendance was withheld SHALL be marked on the meeting record with `attendance_published: false`, so consumers can tell missing data from absence.

#### Scenario: Count meetings attended

- **WHEN** a consumer filters attendance to `person_id = meath/person/dave-anderson` and `status = present`
- **THEN** the count equals the number of published meetings at which the minutes list him as attending

#### Scenario: Withheld attendance is visible

- **WHEN** a meeting's attendance was withheld because of an unresolved name
- **THEN** its meeting record has `attendance_published: false` and no attendance rows exist for it

### Requirement: Closed vocabularies are published

Attendance status, attendance mode, attendee category, decision type, COFOG 1999 codes and transport subdomains SHALL each be published as a vocabulary under `public/vocabularies/`. The JSON Schema SHALL constrain each field to its vocabulary's terms.

#### Scenario: Schema rejects an unknown status

- **WHEN** an attendance record with status `late` is validated against the JSON Schema
- **THEN** validation fails

### Requirement: Catalogue metadata, schema and discovery

The dataset SHALL publish DCAT-AP metadata at `public/catalog/dataset-spc-meetings.ttl`, related to the Public Bodies and Motions datasets. It SHALL have a JSON Schema at `public/schemas/spc-meetings.schema.json`, a `public/CHANGELOG.md` entry and a `DATA_SOURCES.md` attribution for the council minutes and for COFOG. It SHALL be linked from `public/get-the-data.html` and from the `#reference` list on `public/index.html`. `dct:modified` SHALL change only when the published payload changes.

#### Scenario: Every record validates

- **WHEN** the export completes
- **THEN** every published record validates against `public/schemas/spc-meetings.schema.json`

#### Scenario: Unchanged re-run

- **WHEN** the export is re-run with no change to any published record
- **THEN** `dct:modified` is unchanged

### Requirement: Nothing with an unresolved error is published as clean

A meeting with an ingestion or render error SHALL NOT be published. A meeting's attendance, decisions or topics with errors SHALL be withheld as their capabilities define, while the rest of the meeting is published. The export SHALL report the count of withheld parts by error type.

#### Scenario: Render failure

- **WHEN** a meeting has a `RenderMismatch` error
- **THEN** no meeting, attendance, item or decision record and no minutes file is published for it, and the export report counts it
