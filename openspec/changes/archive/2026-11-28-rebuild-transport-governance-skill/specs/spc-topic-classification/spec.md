# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Transport items carry a transport-governance subdomain`
- TO: `### Requirement: Transport items carry a transport-activity grouping`
- FROM: `### Requirement: The subdomain list matches the transport-governance vocabulary`
- TO: `### Requirement: The crosswalk matches the retired vocabulary and the published activity vocabulary`

## MODIFIED Requirements

### Requirement: Transport items carry a transport-activity grouping

An item with a code under `04.5` SHALL also carry one or more transport-activity grouping
IDs from the published `transport-activity` vocabulary (for example `RT1`, `RT7`, `RL3`).
The classification step produces the retired transport subdomain tags; the export SHALL
map each of them to its grouping through the committed crosswalk. An item with no `04.5`
code SHALL carry no grouping.

A source subdomain absent from the crosswalk, or a grouping absent from the published
vocabulary, SHALL be rejected with an error and the item's topics SHALL NOT be published.
A source tag SHALL never be dropped silently.

#### Scenario: Footpath programme

- **WHEN** item "5.0 Presentation on Community Centers Footpath Programme" is classified
  with COFOG `04.5.1` and subdomain `infra/active-travel`
- **THEN** it is published with groupings `RT2` and `RT3`

#### Scenario: Subdomain without a transport code

- **WHEN** an item's codes are only `06.4.0` and the classification step also records
  subdomain `infra/regional-local-roads`
- **THEN** an error is recorded and that item's topics are not published

#### Scenario: Unknown source tag

- **WHEN** the classification step records a subdomain that the crosswalk does not hold
- **THEN** an error is recorded and that item's topics are not published

### Requirement: The crosswalk matches the retired vocabulary and the published activity vocabulary

The committed crosswalk SHALL hold exactly the subdomain IDs defined in the retired
transport subdomain vocabulary, each with its term and plain label, and for each one a
list of replacement grouping IDs present in the published `transport-activity` vocabulary,
or an empty list with a recorded reason where the new model has no equivalent. A
difference between the crosswalk and either vocabulary SHALL fail the test suite.

#### Scenario: Vocabulary gains a subdomain

- **WHEN** a subdomain is added to the retired vocabulary list but not to the committed
  crosswalk
- **THEN** the test suite fails, naming the missing ID

#### Scenario: Mapping to a term that does not exist

- **WHEN** a crosswalk row names a grouping that the published activity vocabulary lacks
- **THEN** the test suite fails, naming the grouping

## ADDED Requirements

### Requirement: Transport tags are mapped, not re-extracted

The export SHALL derive the published groupings from the subdomain tags already recorded
by the classification step. It SHALL NOT re-query a model to produce transport topics.
The published dataset README SHALL say that transport groupings are mapped from the
earlier subdomain tagging, so a reader knows the tag is a derivation of deeper analysis.

#### Scenario: Export without a model call

- **WHEN** the export is re-run on the committed classification output
- **THEN** every grouping is the crosswalk image of a recorded subdomain, and no
  decision, item key or attendance record changes

#### Scenario: Provenance stated

- **WHEN** a reader opens the SPC meetings README
- **THEN** it says the transport groupings are mapped from the earlier subdomain tags
