## Purpose

Identifies the official decisions an SPC made at each meeting, such as what it agreed, adopted, referred or deferred. Approval of the previous meeting's minutes is left out. Every published decision is a verbatim, checkable quote from the minutes.

## Requirements

### Requirement: Approval of previous minutes is excluded

An agenda item whose title is approval of the previous meeting's minutes (for example "1.0 Minutes of Previous Meeting 11th September 2025") SHALL produce no decision, and SHALL NOT be sent for model extraction. Any extracted decision whose quoted text only approves earlier minutes SHALL be discarded and counted.

#### Scenario: Minutes approval item

- **WHEN** item 1.0 reads "Minutes of Previous Meeting 11th September 2025 / Proposed by; Cllr Amanda Smith (AS) / Seconded by: Cllr Mike Bray (MB)"
- **THEN** no decision is published for item 1.0

### Requirement: Decisions are verbatim quotes

Each decision SHALL carry `decision_text`, a contiguous quote from its agenda item's text. After whitespace normalisation the quote SHALL appear exactly in that item's rendered text. A decision whose quote does not appear SHALL be rejected with a `DecisionNotInSource` error.

#### Scenario: Quote found

- **WHEN** an extracted decision quotes "It was agreed to circulate the DoT & TII Policy on Roadside Memorials to the members."
- **THEN** the quote is found in item 6.0's text and the decision is kept

#### Scenario: Paraphrase rejected

- **WHEN** an extracted decision reads "The committee decided to share the memorial policy" and that text is not in the item
- **THEN** a `DecisionNotInSource` error is recorded and the decision is not published

### Requirement: Decision type is from a closed set

Each decision SHALL have a `decision_type` from the published closed set: `agreed`, `adopted`, `recommended_to_council`, `referred`, `deferred`, `appointment`. A value outside the set SHALL be rejected with an error and SHALL NOT be mapped to a nearby term.

#### Scenario: Acting chair elected

- **WHEN** the minutes read "Cllr Sean Drew (SD) was proposed as Acting Chair by Cllr Paddy Meade and Seconded by Cllr Amanda Smith"
- **THEN** the decision type is `appointment`

#### Scenario: Item referred onward

- **WHEN** the minutes read "MB referred Item to the next SPC …"
- **THEN** the decision type is `referred`

#### Scenario: Unknown type

- **WHEN** a model returns the type `noted`
- **THEN** an error is recorded and that decision is not published

### Requirement: Proposer and seconder resolve through the register

Where the minutes name a proposer or seconder for a decision, by name or by initials, each SHALL be resolved to a person ID through the attendance register and that meeting's printed initials. A name or initials that do not resolve SHALL produce an error and the field SHALL be null, never guessed. A decision with no proposer or seconder printed SHALL have null fields without error.

#### Scenario: Initials resolve

- **WHEN** the minutes read "Acceptance of the Terms of Reference as presented was proposed by AS and seconded by SD"
- **THEN** the proposer is `meath/amanda-smith` and the seconder is `meath/sean-drew`

#### Scenario: Consensus decision

- **WHEN** the minutes read "It was agreed that the SPC should continue to work towards developing a practical approach …"
- **THEN** proposer and seconder are null and no error is recorded

### Requirement: Extraction failure fails the whole meeting closed

A failed, truncated or unparseable model response SHALL produce an error for the meeting, and none of that meeting's decisions or topics SHALL be published. The pipeline SHALL NOT publish a partial result from the response.

#### Scenario: Unparseable response

- **WHEN** the model returns text that is not valid against the response schema
- **THEN** an `ExtractionFailed` error names the meeting and no decisions or topics are published for it

### Requirement: Decision identity is stable

Each decision SHALL have the ID `<meeting_id>/d<NN>`, numbered in order of appearance in the minutes, and SHALL record its agenda item number.

#### Scenario: Decision ID

- **WHEN** the first kept decision of the 20 November 2025 meeting is in item 3.0
- **THEN** its ID is `meath/transportation-urban-regeneration/2025-11-20/d01` and its item number is `3.0`
