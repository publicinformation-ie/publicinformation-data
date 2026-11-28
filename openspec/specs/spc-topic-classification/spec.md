## Purpose

Tags each SPC agenda item with what it is about, using the UN Classification of the Functions of Government (COFOG 1999) as a common cross-government taxonomy. Transport items get a transport-activity grouping, mapped from the retired subdomain tags, so discussion topics can be counted and compared across meetings, committees and councils.

## Requirements

### Requirement: COFOG 1999 is committed from the official source

The COFOG code list SHALL be committed as reference data derived from the UN Statistics Division's COFOG 1999 English structure file. The committed data SHALL record the source URL, the retrieval date and the source file's sha256. It SHALL hold every division, group and class code with its description as published.

#### Scenario: Code list matches the source

- **WHEN** the committed list is checked against its recorded source
- **THEN** it contains the 10 divisions, every group and every class, including `04.5` "Transport", `04.5.1` "Road transport" and `06.4.0` "Street lighting", with the descriptions as published

### Requirement: Each agenda item gets one to three COFOG codes

Every classified agenda item SHALL carry between one and three COFOG codes, the first being the primary. A code SHALL be a class (for example `04.5.1`), or a group (for example `04.5`) only where the item spans several classes of that group. A code absent from the committed list SHALL be rejected with an error, and the item's topics SHALL NOT be published.

#### Scenario: Road item

- **WHEN** item "4.0 The Roadworks Programme – Schedule of Municipal District Works" is classified
- **THEN** its primary code is `04.5.1`

#### Scenario: Non-transport item

- **WHEN** item "4.0 Climate Action – Decarbonisation Zones (DZ's)" is classified
- **THEN** its codes are drawn from division `05` or other COFOG divisions, not forced into `04.5`

#### Scenario: Invented code

- **WHEN** a model returns the code `04.5.9`
- **THEN** an `UnknownCofogCode` error is recorded and that item's topics are not published

### Requirement: Transport items carry a transport-activity grouping

An item with a code under `04.5` SHALL also carry one or more transport-activity grouping IDs from the published `transport-activity` vocabulary (for example `RT1`, `RT7`, `RL3`). The classification step produces the retired transport subdomain tags; the export SHALL map each of them to its grouping through the committed crosswalk. An item with no `04.5` code SHALL carry no grouping.

A source subdomain absent from the crosswalk, or a grouping absent from the published vocabulary, SHALL be rejected with an error and the item's topics SHALL NOT be published. A source tag SHALL never be dropped silently.

#### Scenario: Footpath programme

- **WHEN** item "5.0 Presentation on Community Centers Footpath Programme" is classified with COFOG `04.5.1` and subdomain `infra/active-travel`
- **THEN** it is published with groupings `RT2` and `RT3`

#### Scenario: Subdomain without a transport code

- **WHEN** an item's codes are only `06.4.0` and the classification step also records subdomain `infra/regional-local-roads`
- **THEN** an error is recorded and that item's topics are not published

#### Scenario: Unknown source tag

- **WHEN** the classification step records a subdomain that the crosswalk does not hold
- **THEN** an error is recorded and that item's topics are not published

### Requirement: The crosswalk matches the retired vocabulary and the published activity vocabulary

The committed crosswalk SHALL hold exactly the subdomain IDs defined in the retired transport subdomain vocabulary, each with its term and plain label, and for each one a list of replacement grouping IDs present in the published `transport-activity` vocabulary, or an empty list with a recorded reason where the new model has no equivalent. A difference between the crosswalk and either vocabulary SHALL fail the test suite.

#### Scenario: Vocabulary gains a subdomain

- **WHEN** a subdomain is added to the retired vocabulary list but not to the committed crosswalk
- **THEN** the test suite fails, naming the missing ID

#### Scenario: Mapping to a term that does not exist

- **WHEN** a crosswalk row names a grouping that the published activity vocabulary lacks
- **THEN** the test suite fails, naming the grouping

### Requirement: Transport tags are mapped, not re-extracted

The export SHALL derive the published groupings from the subdomain tags already recorded by the classification step. It SHALL NOT re-query a model to produce transport topics. The published dataset README SHALL say that transport groupings are mapped from the earlier subdomain tagging, so a reader knows the tag is a derivation of deeper analysis.

#### Scenario: Export without a model call

- **WHEN** the export is re-run on the committed classification output
- **THEN** every grouping is the crosswalk image of a recorded subdomain, and no decision, item key or attendance record changes

#### Scenario: Provenance stated

- **WHEN** a reader opens the SPC meetings README
- **THEN** it says the transport groupings are mapped from the earlier subdomain tags

### Requirement: Procedural items are classified as such

Items that are purely procedural (approval of previous minutes, matters arising with no substantive content, scheduling of meetings) SHALL be classified `01.1.1` "Executive and legislative organs" so every item has a code. They SHALL carry a `procedural: true` flag so consumers can exclude them from topic counts.

#### Scenario: Meeting schedule

- **WHEN** item "3.0 Agree Meeting date for 2026 – Provisional date" is classified
- **THEN** its code is `01.1.1` and it is flagged procedural
