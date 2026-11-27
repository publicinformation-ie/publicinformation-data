## MODIFIED Requirements

### Requirement: Decision identity is stable

Each published decision SHALL have an ID of the form `<meeting_id>/d<NN>`. An ID SHALL be allocated once, recorded in a committed registry keyed by meeting, agenda item and normalised quote, and SHALL NOT change, be reassigned or be reused afterwards, whether the meeting is re-extracted, the prompt or model changes, or other decisions are added, dropped or reordered. A decision first seen in a meeting SHALL receive the next number not yet used in that meeting, counting retired numbers. A meeting with no registered decisions is numbered `d01`, `d02`, … in order of appearance. Each decision SHALL record its agenda item number.

A decision whose item and normalised quote match a registered entry SHALL reuse that entry's ID. A decision whose quote overlaps an unmatched registered quote in the same item, or a registered decision that is no longer extracted, SHALL be recorded as an error and SHALL NOT be published or renumbered until a human maps or retires the registry entry. A registered entry marked retired SHALL never be published, and its number SHALL stay reserved.

#### Scenario: Decision ID

- **WHEN** no decision of the 20 November 2025 meeting has been registered and its first kept decision is in item 3.0
- **THEN** its ID is `meath/transportation-urban-regeneration/2025-11-20/d01` and its item number is `3.0`

#### Scenario: Re-extraction keeps IDs

- **WHEN** a meeting is re-extracted and a published decision is found again with the same item and quote, even if another decision before it is added or dropped
- **THEN** it keeps its registered ID

#### Scenario: New decision takes the next number

- **WHEN** re-extraction finds a decision that overlaps no registered quote in a meeting whose highest used number is `d04`
- **THEN** it receives `d05` and is added to the registry

#### Scenario: Retired ID is never reused

- **WHEN** `d01` of a meeting is retired because it was not a decision of the committee, and the model extracts that quote again
- **THEN** the decision is not published, and `d01` is not given to any other decision

#### Scenario: Quote boundary drift is not renumbered

- **WHEN** re-extraction returns a quote in item 5.0 that contains, or is contained in, an unmatched registered quote in item 5.0
- **THEN** an error names the meeting, item and both quotes, neither decision is published under a new ID, and the registry is left unchanged

#### Scenario: Registered decision no longer extracted

- **WHEN** a registered, non-retired decision is absent from a re-extraction
- **THEN** an error names its ID, the decision is not published, and its number stays reserved
