# Spec Delta

## Purpose

Covers ingestion of an action annex — a companion file publishing the actions a plan declares and the status later reported against them — into the document pipeline's action records.

> **Scaffold.** Only the requirements that hold under every resolution of the open decisions in the proposal are recorded here. Action identity representation (D-A), the attribution mechanism (D-B), multi-plan annexes (D-C) and the acquisition and step-wiring approach (D-D) are deliberately unspecified; elaborate them before implementation.

## ADDED Requirements

### Requirement: Annex acquisition records errors per document

Annex acquisition SHALL record acquisition failures — unreachable source, wrong payload format, unreadable file — against the failing document only, leaving the run and every other document unaffected. A failed document SHALL NOT be marked processed, so it is retried once its entry or its source is fixed.

#### Scenario: Wrong payload format

- **WHEN** the URL declared for an annex returns a payload of a different format than declared
- **THEN** the document records an acquisition error naming the expected and received format, and no other document is affected

#### Scenario: Failure does not mark the document processed

- **WHEN** a document's annex fails to acquire and the step is re-run after the source is fixed
- **THEN** the document is retried rather than skipped as already processed

### Requirement: Fail-closed header detection

The annex parser SHALL identify each table's header row from the annex's own column names, and a table whose header cannot be confidently matched to a recognised action layout SHALL be skipped with an explicit, classified error — never reassembled by guesswork and never silently reduced to the columns that happened to match.

#### Scenario: Unrecognised header shape

- **WHEN** a table's header does not confidently match a recognised action layout
- **THEN** the table is skipped and an error is recorded identifying the document, worksheet and table, with zero rows emitted from it

#### Scenario: Recognised header yields every row

- **WHEN** a table's header is confidently recognised
- **THEN** every data row is either emitted or individually error-logged, and none is dropped silently

### Requirement: No value is coerced to make a row fit

A cell that cannot be confidently interpreted SHALL be preserved raw with an error logged, and SHALL NOT be silently nulled, rewritten, or mapped to a nearest acceptable value.

#### Scenario: Ambiguous date cell

- **WHEN** a row's target date cannot be confidently parsed
- **THEN** its raw text is preserved, its structured date fields are null, and an error is logged

#### Scenario: Partially interpretable row

- **WHEN** one cell of an otherwise readable row cannot be interpreted
- **THEN** the row is not rewritten to fit, and the failure is attributable to that cell

### Requirement: Status vocabulary is closed and extended only deliberately

A status that cannot be mapped confidently to the closed status vocabulary SHALL be excluded and logged with its raw value rather than coerced to the nearest member. Where a source genuinely expresses a state the vocabulary lacks, the vocabulary SHALL be extended as a reviewed, recorded contract change, never widened at parse time.

#### Scenario: Unmappable status value

- **WHEN** a row's status does not map confidently to the closed vocabulary
- **THEN** that observation is excluded and an error names the row and the raw unnormalized value

#### Scenario: Genuinely new state

- **WHEN** inspection shows a source state that the vocabulary cannot express
- **THEN** the vocabulary is extended by a reviewed change with its contract and changelog records, not by the parser

### Requirement: Status observations are dated from their report

Each status observation SHALL be dated from the publication of the report that made it, never inferred from the observation's own content or from the file it was read out of.

#### Scenario: Observation date comes from the report

- **WHEN** observations are derived from an annex accompanying a published report
- **THEN** each observation's as-of date is that report's publication date

### Requirement: Observations are attributed to the plan that declared the action

A status observation SHALL be attributed to the plan edition that declared the action it observes, including when a later report observes an action carried over from an earlier plan year. An observation whose action cannot be identified SHALL be excluded and logged, never assigned to the observing report's own plan as a fallback and never attached to a neighbouring action.

#### Scenario: Carried-over action observed in a later report

- **WHEN** a report's observations cover actions declared under an earlier plan edition
- **THEN** each observation is attributed to the plan that declared the action

#### Scenario: Unattributable observation

- **WHEN** an observation's action cannot be identified against any plan's declared actions
- **THEN** it is excluded and an error names the report, the raw action reference and the reason

### Requirement: Published action identity is citable and permanent

A published action's identity SHALL be derivable from the action reference its own source document publishes, so a reader citing the action as the State publishes it can locate the published record. Once published, an action's identity SHALL NOT change, and a change to how identity is represented SHALL be treated as a dataset contract change at the severity that change warrants.

#### Scenario: Source reference locates the published action

- **WHEN** a reader holds the action reference printed in a plan's own annex
- **THEN** that reference resolves to the published action record for that plan edition

#### Scenario: Identity is stable across republication

- **WHEN** the corpus is re-extracted and republished
- **THEN** every previously published action keeps the identity it was first published with
