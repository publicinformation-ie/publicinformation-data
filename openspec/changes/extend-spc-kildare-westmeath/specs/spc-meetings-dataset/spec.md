# Spec Delta

## MODIFIED Requirements

### Requirement: Versioned and latest distributions

The dataset SHALL be published at `public/v1.2.0/spc-meetings/` and mirrored at `public/latest/spc-meetings/`. Earlier versioned releases SHALL remain unchanged. Each SHALL contain a JSON-LD file and a CSV file with CSVW metadata for each of meetings, people, attendance, agenda items and decisions, plus a `minutes/` folder and a `README.md`.

#### Scenario: Latest mirrors the versioned release

- **WHEN** the dataset is exported
- **THEN** every file under `public/v1.2.0/spc-meetings/` exists with identical bytes under `public/latest/spc-meetings/`

#### Scenario: Earlier release untouched

- **WHEN** v1.2.0 is exported
- **THEN** no file under `public/v1.1.0/spc-meetings/` changes

### Requirement: Closed vocabularies are published

Attendance status, attendance mode, attendee category, decision type, text source, COFOG 1999 codes and transport subdomains SHALL each be published as a vocabulary under `public/vocabularies/`. The JSON Schema SHALL constrain each field to its vocabulary's terms.

#### Scenario: Schema rejects an unknown status

- **WHEN** an attendance record with status `late` is validated against the JSON Schema
- **THEN** validation fails

#### Scenario: New terms are accepted

- **WHEN** an attendance record with category `absent` and status `absent`, or category `guests` and status `present`, is validated against the JSON Schema
- **THEN** validation passes

## ADDED Requirements

### Requirement: Meetings state where their text came from

Each meeting record SHALL carry `text_source`, one of `text_layer`, `ocr` or `mixed`, and `ocr_engine`, the OCR engine identifier, or null when no page was OCR'd. The dataset README SHALL state that for `ocr` and `mixed` meetings the minutes are verbatim to the OCR text, and that the source PDF, identified by URL and sha256, is authoritative.

#### Scenario: Scanned meeting

- **WHEN** the Kildare meeting of 11 December 2025 is published
- **THEN** its record has `text_source` `ocr` and a non-null `ocr_engine`

#### Scenario: Text-layer meeting

- **WHEN** a Meath meeting is published
- **THEN** its record has `text_source` `text_layer` and `ocr_engine` null, and its other fields are unchanged from v1.1.0

### Requirement: Meetings from several councils are published together

The dataset SHALL hold the meetings of every committee in the committed list in one set of distributions. Each meeting SHALL link to its own council's Public Bodies record, and its minutes file SHALL sit under its own council and committee slugs.

#### Scenario: Kildare minutes path

- **WHEN** the Kildare meeting of 11 December 2025 is published
- **THEN** its minutes are at `minutes/kildare/transport-mobility-open-spaces/2025-12-11.md` and its `public_body` is Kildare County Council's Public Bodies `@id`
