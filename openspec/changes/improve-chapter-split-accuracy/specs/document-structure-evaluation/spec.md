# Spec Delta

## ADDED Requirements

### Requirement: Report scores the production detection path

The report SHALL produce each document's raw tree through the same detection entry point that the production step uses. That entry point includes outline filtering, position resolution and entry normalisation. The report SHALL NOT call a narrower function that skips any of these steps. The post-override tree SHALL be produced from that raw tree with the production override merge.

#### Scenario: Outline preparation applied

- **GIVEN** a gold document whose raw outline contains Word auto-bookmarks and entries that point one page after their heading
- **WHEN** the report scores it
- **THEN** the scored tree matches what the production step would write, with the bookmarks removed and the entries moved to their heading pages

### Requirement: Held-out gold documents

A gold file SHALL be able to declare itself held out. The report SHALL summarise held-out documents separately from the other scored documents, with the same macro and micro metrics and the same fully-correct count. Held-out documents SHALL appear in the per-document table, marked as held out, and SHALL be included in the baseline and its diff. A held-out file SHALL meet every rule that applies to other gold files.

#### Scenario: Separate summaries

- **GIVEN** ten reviewed gold documents, four of them marked as held out
- **WHEN** the report runs
- **THEN** it prints one summary for the six tuning documents, one for the four held-out documents, and one for all ten

#### Scenario: Held-out flag absent

- **WHEN** a gold file does not declare itself held out
- **THEN** it is a tuning document

### Requirement: Detector-change results log

Each detector change measured with the report SHALL be recorded in a committed results log. A log entry SHALL name the change and the commit it was measured at. It SHALL give the tuning and held-out corpus summaries before and after the change, and list every per-document metric change from the baseline diff. Every per-document regression SHALL be given a stated reason. The baseline SHALL be refreshed only after the entry is written.

#### Scenario: Regression recorded

- **WHEN** a detector change raises corpus F1 but lowers one document's page attribution
- **THEN** the log entry lists that document's drop and its reason before the baseline is refreshed
