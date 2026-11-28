## Purpose

Finds and fetches the published minutes of Strategic Policy Committees listed in committed configuration, and fixes each meeting's identity and date, so later steps work from a known, provenance-tracked set of minutes PDFs.

## Requirements

### Requirement: Committees are declared in committed configuration

Each committee SHALL be declared in a committed list giving a committee ID, its `public_body_id`, its name as printed on its minutes, one or more minutes page URLs, the pattern that identifies minutes links, its header layout and, optionally, the years to ingest. The pipeline SHALL NOT ingest a committee absent from that list, nor read pages other than those declared. A `public_body_id` absent from the local-authority list SHALL be a fatal error.

#### Scenario: MVP committee is declared

- **WHEN** the pipeline runs with the committed list as shipped
- **THEN** it ingests Meath County Council's Transportation and Urban Regeneration SPC with committee ID `meath/transportation-urban-regeneration`, unchanged

#### Scenario: Shipped committees

- **WHEN** the pipeline runs with the committed list as shipped
- **THEN** it ingests exactly `meath/transportation-urban-regeneration`, `kildare/transport-mobility-open-spaces` and `westmeath/planning-regeneration-transportation`

#### Scenario: Published name is the name printed on the minutes

- **GIVEN** Kildare's web page calls the committee "Transportation, Safety and Emergency Services" and its minutes print "Transport, Mobility and Open Spaces Strategic Policy Committee"
- **WHEN** the committee is ingested
- **THEN** its published committee name is "Transport, Mobility and Open Spaces Strategic Policy Committee"

#### Scenario: Adding a committee is a configuration edit

- **WHEN** a new committee entry with a known header layout is added to the committed list
- **THEN** the next run discovers that committee's minutes with no code change

#### Scenario: Unknown body is fatal

- **WHEN** a committee entry names a `public_body_id` that is not a local authority
- **THEN** the run stops with an error naming the entry

#### Scenario: Unknown layout is fatal

- **WHEN** a committee entry names a header layout the pipeline does not define
- **THEN** the run stops with an error naming the entry

### Requirement: Only minutes PDFs are discovered

Discovery SHALL collect links to PDF files from each of the committee's declared pages whose link text or file name identifies them as minutes. Agenda PDFs and all other links SHALL be ignored. Each discovered file SHALL record the committee ID, the page it was found on, its absolute URL and its link text.

#### Scenario: Agendas are skipped

- **GIVEN** the Meath page lists "February 2026 - Agenda - SPC Transportation and Urban Regeneration" and "February 2026 - Minutes - SPC Transportation and Urban Regeneration"
- **WHEN** discovery runs
- **THEN** only the minutes PDF is collected

#### Scenario: Same file linked twice

- **WHEN** the page links the same PDF URL more than once
- **THEN** it is collected once

#### Scenario: Minutes spread over several pages

- **GIVEN** the Kildare committee declares its `2025/Minutes/` and `2026/Minutes/` pages
- **WHEN** discovery runs
- **THEN** the minutes PDFs of both pages are collected, each recording the page it was found on

#### Scenario: File name with spaces

- **WHEN** a link's path is "2026/Minutes/Minutes Transport Mobility and Open Spaces SPC 050226.pdf"
- **THEN** the recorded URL is absolute with each space percent-encoded once

### Requirement: Downloads record provenance

Each discovered PDF SHALL be downloaded with TLS certificate verification on. Its sha256, byte size and retrieval time SHALL be recorded. A download that fails SHALL produce an error naming the URL and the failure, and SHALL NOT produce a record.

#### Scenario: Successful download

- **WHEN** a minutes PDF downloads successfully
- **THEN** its record carries the source URL, sha256, size and retrieval timestamp

#### Scenario: Certificate failure is not bypassed

- **WHEN** the server's certificate cannot be verified
- **THEN** the download fails with an error and verification is not disabled to proceed

### Requirement: A minutes PDF must yield text

The pipeline SHALL extract each page's words and positions from the text layer. A page with no text-layer words SHALL be read by OCR with the repository's local OCR engine. A file that yields no words on any page, from either source, SHALL produce a `NoTextRecovered` error and SHALL NOT be passed to later steps.

#### Scenario: Image-only PDF

- **WHEN** a downloaded PDF has no text layer on any page and OCR recognises text on its pages
- **THEN** the meeting proceeds with the OCR words and positions, each page marked as read by OCR, and no `NoTextLayer` error is produced

#### Scenario: Mixed file is read page by page

- **WHEN** a PDF has a text layer on pages 1 to 3 and none on page 4
- **THEN** pages 1 to 3 use the text layer, page 4 is read by OCR, and the file is marked `mixed`

#### Scenario: Nothing recovered

- **WHEN** neither the text layer nor OCR yields a word on any page
- **THEN** a `NoTextRecovered` error names the file and no meeting is produced from it

### Requirement: Meeting date comes from the document header

Each meeting's date SHALL be read from the header's date line as defined by the committee's layout (for example "Transportation & Urban Regeneration Strategic Policy Committee 19th February 2026", or "Minutes of Meeting held on Thursday, 11 December 2025 at 3.30p.m."). The date's month and year SHALL agree with the month and year in the link text where the link text gives them. A missing, unparseable or disagreeing date SHALL produce an error, and no meeting SHALL be produced. A header that prints a day and month but no year SHALL take the year from the link text, and only when the link text's month agrees with the header's month; otherwise it is an error.

#### Scenario: Header date resolves

- **WHEN** the header reads "19th February 2026" and the link text reads "February 2026 - Minutes - …"
- **THEN** the meeting date is `2026-02-19`

#### Scenario: Kildare date line

- **WHEN** the header reads "Minutes of Meeting held on Thursday, 11 December 2025 at 3.30p.m. in the Committee Room, Aras Chill Dara, Naas." and the link text reads "Minutes of Transportation, Mobility and Open Spaces SPC Meeting 11 December 2025 (Acrobat pdf, 759KB)"
- **THEN** the meeting date is `2025-12-11`

#### Scenario: Header prints no year

- **WHEN** the header reads "held in the Council Chambers ... at 10am on Thursday 13 February - Hybrid Meeting" and the link text reads "Minutes of SPC Meeting 13th February 2025"
- **THEN** the meeting date is `2025-02-13` and the record states that the year came from the link text

#### Scenario: Header prints no year and the link text cannot supply it

- **WHEN** the header prints no year and the link text names a different month or no month and year
- **THEN** a `MeetingDateUnparseable` error is recorded and no meeting is produced

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

### Requirement: Discovery can be limited to given years

A committee MAY declare the years to ingest. When it does, a minutes link SHALL be collected only if the four-digit year in its link text is one of those years. A link whose text gives no year SHALL produce an `UndatedMinutesLink` error and no record. The year SHALL NOT be inferred from the file name or URL.

#### Scenario: Older minutes are skipped

- **GIVEN** the Westmeath committee declares years 2025 and 2026
- **WHEN** its page lists "Minutes of SPC Meeting 17th Nov 2023" and "Minutes of SPC Meeting 6th March 2026"
- **THEN** only the 6 March 2026 minutes are collected

#### Scenario: Undated link under a year window

- **WHEN** a committee declares years and a minutes link's text has no four-digit year
- **THEN** an `UndatedMinutesLink` error names the link and it is not collected

### Requirement: Low-confidence OCR is not published

An OCR'd page whose mean word confidence is below the step's committed threshold SHALL produce an `OcrLowConfidence` error naming the file, page and confidence, and no meeting SHALL be produced from that file. Individual words SHALL NOT be dropped or altered for low confidence.

#### Scenario: Poor scan

- **WHEN** page 2 of a scanned PDF OCRs with mean confidence below the threshold
- **THEN** an `OcrLowConfidence` error names the file, page 2 and its confidence, and no meeting is produced

### Requirement: Blank pages are skipped only by reviewed override

An OCR'd page that would fail the confidence gate SHALL be skipped only by a committed override naming that file's sha256 and page with a reason. A page with no recognised words SHALL produce an `EmptyOcrPage` error, and a page below the threshold an `OcrLowConfidence` error, and no meeting SHALL be produced from that file, unless such an override exists. A skipped page's words, including scanner speckle read as junk words, SHALL be dropped from the record and counted. An override SHALL NOT skip a page that passes the gate. An override that matches no fetched file SHALL produce an error. Skipped pages SHALL be counted.

#### Scenario: Signature page

- **GIVEN** an override names the sha256 of the Westmeath 6 March 2026 minutes, page 4, reason "signature page"
- **WHEN** that page yields no OCR words
- **THEN** the page is skipped and counted, and the meeting proceeds

#### Scenario: Blank sheet read as junk

- **GIVEN** an override names the sha256 of the Westmeath 28 November 2025 minutes, page 4, reason "blank sheet"
- **WHEN** OCR reads three junk words on that page with mean confidence below the threshold
- **THEN** the page is skipped, its three words are dropped and counted, and the meeting proceeds

#### Scenario: Override on a good page

- **WHEN** an override names a page whose OCR passes the confidence gate
- **THEN** the page is kept, not skipped

#### Scenario: File republished

- **WHEN** the council republishes that file with different bytes
- **THEN** the override no longer applies, the empty page produces an `EmptyOcrPage` error, and the stale override is reported

### Requirement: OCR results are reproducible

Each OCR'd page SHALL record the OCR engine identifier, including its version, language and settings. OCR output SHALL be cached by the file's sha256, page number and engine identifier, and SHALL NOT be reused when any of these differ.

#### Scenario: Unchanged re-run

- **WHEN** the pipeline re-runs on the same file with the same engine
- **THEN** no OCR is performed and the same words are produced

#### Scenario: Engine upgraded

- **WHEN** the OCR engine version changes
- **THEN** cached OCR output is not reused and the file is OCR'd again

### Requirement: Bot-protected sources are not fetched

The pipeline SHALL NOT solve, evade or bypass bot-protection challenges. A declared page that returns a challenge or access denial SHALL produce a `PageFetchFailed` error.

#### Scenario: Challenge page

- **WHEN** a committee page responds with a JavaScript challenge or HTTP 403
- **THEN** a `PageFetchFailed` error names the page and no attempt is made to pass the challenge
