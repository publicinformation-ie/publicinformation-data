## Purpose

Tags each SPC agenda item with what it is about, using the UN Classification of the Functions of Government (COFOG 1999) as a common cross-government taxonomy. Transport items get a finer transport-governance subdomain, so discussion topics can be counted and compared across meetings, committees and councils.

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

### Requirement: Transport items carry a transport-governance subdomain

An item with a code under `04.5` SHALL also carry one or more transport-governance subdomain IDs from the committed subdomain list (for example `infra/active-travel`, `infra/regional-local-roads`, `svc/pso-bus`). An item with no `04.5` code SHALL carry no subdomain. A subdomain ID absent from the committed list SHALL be rejected with an error.

#### Scenario: Footpath programme

- **WHEN** item "5.0 Presentation on Community Centers Footpath Programme" is classified
- **THEN** it has COFOG `04.5.1` and subdomain `infra/active-travel`

#### Scenario: Subdomain without a transport code

- **WHEN** an item's codes are only `06.4.0` and a model also returns subdomain `infra/regional-local-roads`
- **THEN** an error is recorded and that item's topics are not published

### Requirement: The subdomain list matches the transport-governance vocabulary

The committed transport subdomain list SHALL contain exactly the subdomain IDs defined in the transport-governance vocabulary, each with its term and plain label. A difference between the two SHALL fail the test suite.

#### Scenario: Vocabulary gains a subdomain

- **WHEN** a subdomain is added to the transport-governance vocabulary but not to the committed list
- **THEN** the test suite fails, naming the missing ID

### Requirement: Procedural items are classified as such

Items that are purely procedural (approval of previous minutes, matters arising with no substantive content, scheduling of meetings) SHALL be classified `01.1.1` "Executive and legislative organs" so every item has a code. They SHALL carry a `procedural: true` flag so consumers can exclude them from topic counts.

#### Scenario: Meeting schedule

- **WHEN** item "3.0 Agree Meeting date for 2026 – Provisional date" is classified
- **THEN** its code is `01.1.1` and it is flagged procedural
