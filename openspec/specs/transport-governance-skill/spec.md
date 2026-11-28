## Purpose

Defines how the `transport-governance` agent skill answers a question about who does what in local transport, using the published transport RACI dataset as its only model, and what it must say about coverage, gaps and evidence.

## Requirements

### Requirement: Answers come from the published dataset

The skill SHALL answer from the published transport RACI dataset under `public/latest/transport-raci/` and the vocabularies under `public/vocabularies/`. It SHALL NOT carry its own copy of assignments, activities, stages or parties. A change to the dataset SHALL change the skill's answers without editing the skill.

#### Scenario: Dataset ruling reaches the answer

- **WHEN** a ruling in the dataset changes the role on `RT-02.S2`
- **THEN** the skill answers with the new role, and no skill file was edited

#### Scenario: No second row table

- **WHEN** the skill's files are inspected for a row-by-row RACI table
- **THEN** none exists; the skill holds routing and wording rules only

### Requirement: A question is routed to activity and stage

The skill SHALL turn a question into one or more (activity, stage) pairs from the published transport-activity and transport-stage vocabularies before answering, and SHALL name the activity and stage it used. Where a variant applies, it SHALL name the variant.

#### Scenario: Routing a works-programme question

- **WHEN** asked who approves a council's schedule of municipal district works
- **THEN** it routes to activity `RT-02`, stage `S2`, and answers from that assignment

#### Scenario: Variant named

- **WHEN** the matching rows differ by variant, such as a scheme delivered by the National Transport Authority
- **THEN** the answer names the variant it used

### Requirement: Questions outside the analysed council still get an answer

The dataset's assignments were analysed for Meath County Council. For a question about any other council, the skill SHALL give the substantive answer the model supports and SHALL state that the assignment was analysed for Meath and may differ elsewhere. It SHALL NOT refuse, and it SHALL NOT present the Meath assignment as the other council's.

#### Scenario: Kildare bus lane

- **WHEN** asked who delivers a bus lane in Kildare
- **THEN** the answer gives the model's delivery line with a caveat that it was analysed for Meath

#### Scenario: Meath question

- **WHEN** the question is about Meath County Council
- **THEN** the caveat is not needed, though the answer still names its evidence

### Requirement: Gaps are reported as gaps

Where the matching row is `not assessed`, the skill SHALL say that the dataset does not assess it. It SHALL NOT infer a role from a neighbouring activity, stage or council, and SHALL NOT say that nobody is responsible.

#### Scenario: Unassessed row

- **WHEN** asked who maintains a national road, and that row is not assessed
- **THEN** the answer says the dataset does not assess it, and does not name a party

### Requirement: Every answer carries its evidence

An answer SHALL state the evidence level recorded for the line (`set by law`, `guidance`, `unverified`, and the levels the vocabulary defines) and, where the role is still awaiting review, SHALL say the role is not published rather than guess it.

#### Scenario: Guidance-backed role

- **WHEN** an answer rests on a line whose evidence is guidance rather than statute
- **THEN** the answer says so, and does not describe the role as a statutory duty

#### Scenario: Unresolved role

- **WHEN** a row has a role cell still awaiting review
- **THEN** the answer reports the gap instead of a party

### Requirement: The skill states what it is

An answer SHALL present the dataset as PublicInformation.ie's analysis, not as an official statement of any body's duties and not as legal advice.

#### Scenario: First answer in a conversation

- **WHEN** the skill first answers a governance question
- **THEN** the answer identifies the analysis and says each line carries its evidence

### Requirement: Public copy uses plain wording

When writing public-facing copy, the skill SHALL use the plain labels the vocabularies publish, SHALL NOT use internal identifiers such as assignment, activity or stage IDs, and SHALL apply the banned-term rules in its vocabulary page.

#### Scenario: Website copy

- **WHEN** the skill drafts public copy about a works programme
- **THEN** the copy names parties in plain words and contains no `RT-02.S2` or stage ID

### Requirement: The skill ships a validation set

The skill SHALL ship a question set with an expected activity, stage and role for each question, drawn from the published dataset, and a procedure for running it with a fresh agent. Every expected row SHALL exist in the published dataset.

#### Scenario: Expected row removed from the dataset

- **WHEN** a validation question names an assignment the dataset no longer publishes
- **THEN** the check fails and names the question
