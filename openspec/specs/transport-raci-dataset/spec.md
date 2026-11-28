# transport-raci-dataset Specification

## Purpose
Publishes the transport RACI as an open, analytical dataset: who is Responsible, Accountable, Consulted and Informed for each assessed local transport activity and stage. Every assertion carries its confidence and sources, coverage is stated honestly, and the dataset is labelled throughout as analysis by publicinformation.ie.

## Requirements

### Requirement: The dataset is published at latest and at a version

The generator SHALL write the dataset to `public/latest/transport-raci/` and `public/v0.1.0/transport-raci/`, with identical content. The catalogue SHALL declare `owl:versionInfo` `0.1.0`.

#### Scenario: Both locations match

- **WHEN** the generator runs
- **THEN** every file under `latest/transport-raci/` is byte-identical to its counterpart under `v0.1.0/transport-raci/`

### Requirement: Normalised tables are published with CSVW

The dataset SHALL publish `assignments.csv`, `assignment-roles.csv`, `assignment-sources.csv`, `variants.csv`, `sources.csv` and `boundary-rules.csv`, each with CSVW metadata. Activities, stages, parties and evidence levels SHALL be referenced by their vocabulary URIs.

#### Scenario: Role lines reference vocabulary URIs

- **WHEN** `assignment-roles.csv` is read
- **THEN** each line carries an assignment ID, a role (R, A, C or I) and a party URI in `/ns/transport-raci-party#`

#### Scenario: Assessed line count

- **WHEN** `assignments.csv` is read for v0.1.0
- **THEN** it holds one line per migrated assessed line, and each line's jurisdiction is `https://data.publicinformation.ie/body/meath-county-council`

### Requirement: Coverage is published for every row

The dataset SHALL publish `rows.csv` with every generated activity × stage row, its coverage state (`assessed` or `not assessed`) and its count of assessed lines. A row with no assignment SHALL read `not assessed` and SHALL NOT be presented as having no local authority role.

#### Scenario: Coverage totals

- **WHEN** `rows.csv` is read for v0.1.0
- **THEN** it holds 613 rows, 184 of them `assessed`

#### Scenario: Not assessed is not "no role"

- **WHEN** a consumer reads `RL-03.S2`
- **THEN** its coverage is `not assessed`, with no roles

### Requirement: A wide reading view is generated

The dataset SHALL publish `raci-wide.csv`, a generated view with one line per assignment. It SHALL show the R, A, C and I parties as readable names, the evidence as its plain label, the variant label, the jurisdiction name, the source IDs and the public note. It SHALL be documented as a view that is never edited.

#### Scenario: Readable line

- **WHEN** the wide view line for `RT-09.S12` is read
- **THEN** A reads as the Chief Executive and executive of Meath County Council, and evidence reads "set by law"

### Requirement: "No local authority role" is derived

Each assessed line in the JSON and wide view SHALL carry a derived three-valued `no_local_authority_role`: `false` when a council organ (LA-M or LA-CE) holds any role; `true` only when the line has an Accountable party and no council organ holds any role; `unknown` when the line has no Accountable party. In the JSON the value SHALL be a boolean, with `null` for unknown; in `raci-wide.csv` the cell SHALL read `true`, `false` or `unknown`, and the CSVW metadata SHALL declare the column as `boolean` with `null` `unknown`. Unknown SHALL be documented as "it is not established who is Accountable", never as "no role".

#### Scenario: Line with no council role

- **WHEN** an assessed line has an Accountable party and roles only for national bodies and third parties
- **THEN** its flag is `true`

#### Scenario: Line with no Accountable party

- **WHEN** an assessed line has no Accountable party and no council organ holds a role
- **THEN** its flag is `null` in the JSON and `unknown` in the wide view

### Requirement: Nested JSON serves programs and LLMs

The dataset SHALL publish `transport-raci.json`, nesting activity → stage → assignments → roles and sources. Each activity SHALL carry its definition, COFOG links and coverage counts, and each stage its plain name. The JSON SHALL agree with the CSV tables.

#### Scenario: JSON agrees with tables

- **WHEN** the assignments and roles in the JSON are compared with the CSV tables
- **THEN** the sets are equal

### Requirement: Non-public references are never published

No published file in the dataset or its vocabularies SHALL contain scenario references, F-numbers or Decision numbers. Published notes SHALL come from the master's `public_note`, and the internal fields SHALL be dropped.

#### Scenario: Leak check

- **WHEN** every published file is scanned for `\bF\d+\b`, `Decision \d+` and scenario references
- **THEN** none is found

#### Scenario: Missing public note blocks the build

- **WHEN** an assignment's note cites an internal reference and it has no `public_note`
- **THEN** the build fails and names the assignment

### Requirement: Roles awaiting rulings are listed, not published

A role logged as unresolved by the migration SHALL NOT appear in the published data. The README SHALL list each unresolved item by row and role as "role not yet published: awaiting review".

#### Scenario: Unresolved role listed

- **WHEN** the role on `X-02.S14` has no ruling
- **THEN** it is absent from `assignment-roles.csv`, and the README lists it as awaiting review

### Requirement: The dataset is labelled as analytical and derived

The DCAT record `public/catalog/dataset-transport-raci.ttl` SHALL:
- state in its description that this is an analysis compiled by publicinformation.ie, not official data and not republished source data;
- carry a `dct:provenance` statement linking the methodology;
- list `prov:wasDerivedFrom` for every cited source URL;
- set `dct:spatial` to Meath and a pre-release `adms:status`;
- licence the data CC BY 4.0;
- relate the dataset to `public-bodies` and COFOG.

#### Scenario: Catalogue parses with provenance

- **WHEN** the catalogue record is parsed as Turtle
- **THEN** it has `dct:provenance`, at least one `prov:wasDerivedFrom` per cited source URL, `dct:spatial` and `adms:status`

### Requirement: Scope to Meath is stated everywhere

The README, the methodology, `llms.txt` and the catalogue description SHALL each state that assignments have been analysed only for Meath County Council, that they may differ for other councils, and that Meath is in the Greater Dublin Area.

#### Scenario: Scope statement present

- **WHEN** the README and `llms.txt` are read
- **THEN** each contains the Meath-only scope statement

### Requirement: Documentation and LLM entry point

The dataset SHALL publish:
- `README.md`: contents, how to read RACI and the evidence levels, coverage, unresolved items, a not-legal-advice statement and how to report a correction;
- `METHODOLOGY.md`: hand-authored and reviewed;
- `llms.txt`: links the README, methodology, JSON and wide view with absolute URLs, and explains how to answer a question from them.

#### Scenario: llms.txt links resolve

- **WHEN** every link in `llms.txt` is checked against the published tree
- **THEN** each one points to a file that exists

### Requirement: The dataset is discoverable

The dataset SHALL be linked from the public data README, `GET_THE_DATA.md`, `get-the-data.html` (every CSV table, with a plain description) and the `index.html` reference list. It SHALL be recorded in `public/CHANGELOG.md` and `DATA_SOURCES.md`.

#### Scenario: Get the Data lists every table

- **WHEN** `get-the-data.html` is read
- **THEN** it links every CSV under `latest/transport-raci/`

### Requirement: Benchmark questions are answerable honestly

Following only `llms.txt` and the files it links, a reader SHALL be able to answer the six benchmark questions in the brief. Questions on bus routes, active travel maintenance and greenways get answers from the data with their confidence. Questions on congestion, non-Local Link fares and train timetables get an explicit "not yet assessed" answer.

#### Scenario: Train timetables

- **WHEN** a reader asks who is responsible for public train timetables
- **THEN** the data shows that `RL-03` is entirely not assessed, and no role is invented
