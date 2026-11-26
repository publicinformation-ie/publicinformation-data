## Purpose

Finds and fetches the published minutes of Strategic Policy Committees listed in committed configuration, and fixes each meeting's identity and date, so later steps work from a known, provenance-tracked set of minutes PDFs.

## Requirements

### Requirement: Committees are declared in committed configuration

Each committee SHALL be declared in a committed list giving a committee ID, its `public_body_id`, its name as published, its minutes page URL and the pattern that identifies minutes links. The pipeline SHALL NOT ingest a committee absent from that list. A `public_body_id` absent from the local-authority list SHALL be a fatal error.

#### Scenario: MVP committee is declared

- **WHEN** the pipeline runs with the committed list as shipped
- **THEN** it ingests only Meath County Council's Transportation and Urban Regeneration SPC, with committee ID `meath/transportation-urban-regeneration`

#### Scenario: Adding a committee is a configuration edit

- **WHEN** a new committee entry is added to the committed list
- **THEN** the next run discovers that committee's minutes with no code change

#### Scenario: Unknown body is fatal

- **WHEN** a committee entry names a `public_body_id` that is not a local authority
- **THEN** the run stops with an error naming the entry

### Requirement: Only minutes PDFs are discovered

Discovery SHALL collect links to PDF files from the committee's page whose link text or file name identifies them as minutes. Agenda PDFs and all other links SHALL be ignored. Each discovered file SHALL record the committee ID, its absolute URL and its link text.

#### Scenario: Agendas are skipped

- **GIVEN** the Meath page lists "February 2026 - Agenda - SPC Transportation and Urban Regeneration" and "February 2026 - Minutes - SPC Transportation and Urban Regeneration"
- **WHEN** discovery runs
- **THEN** only the minutes PDF is collected

#### Scenario: Same file linked twice

- **WHEN** the page links the same PDF URL more than once
- **THEN** it is collected once

### Requirement: Downloads record provenance

Each discovered PDF SHALL be downloaded with TLS certificate verification on. Its sha256, byte size and retrieval time SHALL be recorded. A download that fails SHALL produce an error naming the URL and the failure, and SHALL NOT produce a record.

#### Scenario: Successful download

- **WHEN** a minutes PDF downloads successfully
- **THEN** its record carries the source URL, sha256, size and retrieval timestamp

#### Scenario: Certificate failure is not bypassed

- **WHEN** the server's certificate cannot be verified
- **THEN** the download fails with an error and verification is not disabled to proceed

### Requirement: A minutes PDF must have a text layer

The pipeline SHALL extract the text and word positions of each page. A PDF with no extractable text on any page SHALL produce an error and SHALL NOT be passed to later steps. The pipeline SHALL NOT run OCR.

#### Scenario: Image-only PDF

- **WHEN** a downloaded PDF yields no extractable text
- **THEN** a `NoTextLayer` error names the file and no meeting is produced from it

### Requirement: Meeting date comes from the document header

Each meeting's date SHALL be read from the header line naming the committee and date (for example "Transportation & Urban Regeneration Strategic Policy Committee 19th February 2026"). The date's month and year SHALL agree with the month and year in the link text where the link text gives them. A missing, unparseable or disagreeing date SHALL produce an error, and no meeting SHALL be produced.

#### Scenario: Header date resolves

- **WHEN** the header reads "19th February 2026" and the link text reads "February 2026 - Minutes - …"
- **THEN** the meeting date is `2026-02-19`

#### Scenario: Header and link disagree

- **WHEN** the header reads "21st May 2026" and the link text reads "February 2026 - Minutes - …"
- **THEN** a `MeetingDateMismatch` error is recorded and no meeting is produced from that file

### Requirement: Meeting identity is stable

Each meeting SHALL have the ID `<committee_id>/<YYYY-MM-DD>`. Two files resolving to the same meeting ID SHALL produce an error, and neither SHALL be published until a human resolves it.

#### Scenario: Meeting ID

- **WHEN** the February 2026 minutes of the Meath committee are ingested
- **THEN** the meeting ID is `meath/transportation-urban-regeneration/2026-02-19`

#### Scenario: Duplicate meeting

- **WHEN** two different PDFs both resolve to `meath/transportation-urban-regeneration/2026-02-19`
- **THEN** a `DuplicateMeeting` error lists both URLs and neither is published
