# transport-raci-vocabularies Specification

## Purpose
Publishes the axes of the transport RACI as stable, machine-readable vocabularies: stages, activities with their L4 groupings, parties, and evidence levels. Other datasets and tools can link to these terms, and the activities hang off the published COFOG 1999 vocabulary.

## Requirements

### Requirement: Four vocabularies are published from the master

The generator SHALL publish `transport-stage`, `transport-activity`, `transport-raci-party` and `raci-evidence-level` under `public/vocabularies/`, each built only from the master tables.

#### Scenario: Vocabularies exist

- **WHEN** the generator runs on a valid master
- **THEN** each of the four vocabularies is written

#### Scenario: Stage count

- **WHEN** `transport-stage` is read
- **THEN** it holds the 20 stages: S1, S2, S3, S4, S5, S5G, S6, S7a, S7b, S7c, S7D, S8, S9, S10, S11, S12, S13a, S13b, S14 and S15

### Requirement: Each vocabulary has JSON, CSV with CSVW, and SKOS Turtle

Each vocabulary SHALL be published as JSON, as a CSV with the columns `uri`, `notation`, `name` and `description` plus CSVW metadata declaring `uri` as the primary key, and as SKOS Turtle with one concept scheme and one `skos:Concept` per term. The three distributions SHALL hold the same set of notations.

#### Scenario: Distributions agree

- **WHEN** the CSV notations, JSON codes and Turtle notations of `transport-activity` are compared
- **THEN** the three sets are equal

#### Scenario: CSVW contract

- **WHEN** a vocabulary's CSVW metadata is read
- **THEN** it declares `uri` as the primary key and `{uri}` as the about URL

### Requirement: Term URIs are stable and resolvable

Each term SHALL have the URI `https://data.publicinformation.ie/ns/<vocabulary>#<notation>`. Each namespace base SHALL resolve to an HTML page that names the vocabulary and links every distribution. The URI shape SHALL NOT change within the vocabulary's lifetime.

#### Scenario: Activity URI

- **WHEN** activity `RT-09` is published
- **THEN** its URI is `https://data.publicinformation.ie/ns/transport-activity#RT-09`

#### Scenario: Resolver page

- **WHEN** a browser opens `https://data.publicinformation.ie/ns/transport-stage`
- **THEN** it reaches a page linking the JSON, CSV, CSVW metadata and Turtle files

### Requirement: Activities form one hierarchy under COFOG

`transport-activity` SHALL hold groupings and activities in one scheme. Each activity SHALL be `skos:broader` its primary grouping and `skos:related` any other grouping. Each grouping with a `confirmed` COFOG class SHALL be `skos:broader` that class's `/ns/cofog#<code>` URI. A `candidate` class SHALL be linked with `skos:related` only.

#### Scenario: Confirmed grouping links to COFOG

- **WHEN** grouping `RT3` is read from the Turtle
- **THEN** it is `skos:broader` `https://data.publicinformation.ie/ns/cofog#04.5.1`

#### Scenario: Candidate link is not broader

- **WHEN** grouping `X1` is read from the Turtle
- **THEN** it is `skos:related` `https://data.publicinformation.ie/ns/cofog#03.1.0`, and it has no `skos:broader` to COFOG

#### Scenario: No COFOG labels are copied

- **WHEN** the `transport-activity` distributions are read
- **THEN** no COFOG concept is declared in them, only referenced by URI

### Requirement: Activity terms carry their definition and status

Each activity term SHALL carry its name, its definition (what it covers and excludes), its status (`active`, `retired` or `placeholder`) and the stages it has. Retired and placeholder activities SHALL be published, marked as such.

#### Scenario: Retired activity is visible

- **WHEN** `RT-30` is looked up
- **THEN** it exists with status `retired` and no stages

### Requirement: Parties link to public bodies and carry plain labels

Each party term SHALL carry a name, a plain label, its kind, and, for bodies with an entry, `skos:exactMatch` to the `public-bodies` URI. Council organs SHALL state that they stand for an organ of the council named by each assignment.

#### Scenario: Party exact match

- **WHEN** party `TII` is read from the Turtle
- **THEN** it has `skos:exactMatch` `https://data.publicinformation.ie/body/transport-infrastructure-ireland`

### Requirement: Evidence levels carry plain-words confidence

Each evidence-level term SHALL carry a plain label. The labels are: `statute` "set by law"; `source` "stated in official guidance or observed practice"; `default-s149-4` "assumed by default (an executive function because it is not reserved to elected members)"; `unverified` "not yet confirmed". The vocabulary SHALL also publish `not-assessed` "not yet assessed", marked as a coverage state that is never stored on an assignment.

#### Scenario: Plain label lookup

- **WHEN** a consumer looks up `statute`
- **THEN** the plain label is "set by law"

### Requirement: One generator writes every vocabulary, with a check mode

The vocabularies SHALL be written only by the transport RACI generator, through change-detecting writes. A check mode SHALL exit non-zero and name each committed file that differs from what the generator would write.

#### Scenario: Regeneration is a no-op

- **WHEN** the generator runs against an unchanged master
- **THEN** every vocabulary file is byte-identical and the check mode exits zero

#### Scenario: Hand edit is detected

- **WHEN** `transport-stage.csv` is edited by hand
- **THEN** the check mode exits non-zero and names that file
