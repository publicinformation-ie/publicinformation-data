# Spec Delta

## ADDED Requirements

### Requirement: Interim milestones are published one per record
The dataset SHALL publish each action's interim milestones as separate records, in the order the plan prints them, each with a 1-based ordinal and an identifier derived from the action and ordinal.

#### Scenario: Two dated milestones
- **GIVEN** SMP 2026–2030 action 4 prints `Q1 2029 – Convene working group to review contract. Q3 2030 – Secure Ministerial sign-off on new contract…`
- **WHEN** the dataset is published
- **THEN** the milestone table holds two records for that action, ordinals 1 and 2, with due labels `Q1 2029` and `Q3 2030`

#### Scenario: Action with no milestone text
- **GIVEN** an action whose milestone cell is empty
- **WHEN** the dataset is published
- **THEN** no milestone record exists for that action

### Requirement: A milestone carries a due date only when the plan states one
A milestone record SHALL carry a due date range and precision only when its text opens with a date the plan printed; otherwise the date fields SHALL be empty. A date SHALL NOT be inferred from surrounding prose or from the action's deadline.

#### Scenario: Quarter and year markers
- **WHEN** a milestone opens with `Q1 2029 –` or `2023:`
- **THEN** its range is `2029-01-01`..`2029-03-31` (quarter) or `2023-01-01`..`2023-12-31` (year)

#### Scenario: Undated milestone
- **GIVEN** a milestone cell with no dated marker, such as `Convene Quarterly Monitoring meetings…`
- **WHEN** the dataset is published
- **THEN** one record exists with empty due label, range and precision

#### Scenario: Year range inside prose
- **GIVEN** the text `2024: Existing IMMAC reviewed. 2025: IMMAC 2025-2030 agreed.`
- **WHEN** it is split
- **THEN** exactly two milestones result and `2025-2030` is not treated as a date marker

#### Scenario: Date mentioned in prose
- **GIVEN** the text `Deliver the report by Q4 2030.`
- **WHEN** it is split
- **THEN** one undated milestone holds the whole text

### Requirement: Milestone records are a lossless split of the raw prose
The milestone records of an action SHALL together contain all of that action's `original_deadline_milestones` text, which remains published unchanged on the action. An action whose text cannot be split without loss SHALL fall back to one undated record holding the whole text and be logged.

#### Scenario: Round trip
- **WHEN** an action's milestone texts are rejoined with their markers
- **THEN** the result equals the whitespace-normalised `original_deadline_milestones`

#### Scenario: Existing tables unchanged
- **WHEN** the milestone table is introduced
- **THEN** `actions.csv`, `action-status-observations.csv` and `action-relationships.csv` have the same content as in the previous release

### Requirement: Milestone records reference published actions
Every milestone record SHALL reference an action present in the same release, its identifier SHALL be unique, ordinals SHALL be contiguous from 1 within an action, and a due range SHALL start on or before it ends. A release violating any of these SHALL NOT be written.

#### Scenario: Orphan milestone
- **GIVEN** a milestone whose `action_id` is not in the action table
- **WHEN** publication runs
- **THEN** it fails with the violation and writes nothing

#### Scenario: Repeated date in one action
- **GIVEN** an action with two milestones both due `Q3 2027`
- **WHEN** publication runs
- **THEN** both are accepted, distinguished by ordinal

### Requirement: The milestone table is described in every published schema surface
The milestone table SHALL be declared in the CSVW metadata (with a foreign key to actions), the JSON Schema, the JSON-LD (as a `milestones` array on each action) and the DCAT distribution list.

#### Scenario: Schema surfaces agree
- **WHEN** the release is validated
- **THEN** the CSVW, JSON Schema and DCAT entries each name `action-milestones.csv` and its eight columns
