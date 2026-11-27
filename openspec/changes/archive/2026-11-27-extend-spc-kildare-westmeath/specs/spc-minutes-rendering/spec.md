# Spec Delta

## MODIFIED Requirements

### Requirement: Page furniture is removed

The page furniture declared for the committee's layout SHALL be removed from every page: for Meath, the running header ("Miontuairiscí/Meeting Minutes"), the "Page N of M" line and the repeated footer address block. Removal SHALL match only text that repeats as furniture on the committee's pages. Each removed line SHALL be counted in the step's output.

#### Scenario: Footer removed from every page

- **WHEN** a 4-page minutes PDF is rendered
- **THEN** the footer address block and the page number appear 0 times in the rendered body

#### Scenario: Body text resembling furniture is kept

- **WHEN** an agenda item's text mentions "www.meath.ie" in a sentence
- **THEN** that sentence is kept

#### Scenario: OCR text that is not declared furniture is kept

- **WHEN** OCR reads stray marks at the top of a scanned page as a short token and that token passed the confidence gate
- **THEN** the token is kept in the rendered body, because only declared furniture is removed

### Requirement: Agenda items become headings

Each numbered agenda item line SHALL become a second-level heading with the item's number and title as printed, in any of the item forms the committee's layout declares (for example "4.0 Climate Action – Decarbonisation Zones (DZ's)", "Item 1 – Declarations of Interest" or "Item 2: Matters Arising"). Unnumbered "AOB" sections SHALL become headings too. Bullet characters SHALL become Markdown list items. Each heading SHALL have a stable anchor derived from its item number.

#### Scenario: Numbered item

- **WHEN** the source has the line "5.0 Work Programme 2026"
- **THEN** the rendered body has the heading `## 5.0 Work Programme 2026` with anchor `item-5-0`

#### Scenario: Item word form

- **WHEN** a Kildare source has the line "Item 2 – Minutes-of the meeting held on 2 October 2025"
- **THEN** the rendered body has the heading `## Item 2 – Minutes-of the meeting held on 2 October 2025` with anchor `item-2`

#### Scenario: Bullets

- **WHEN** the source has lines beginning "•"
- **THEN** each becomes a Markdown list item with its text unchanged

### Requirement: The meeting header is rendered as structured front matter and a heading block

The rendered file SHALL begin with front matter giving the meeting ID, committee ID and name, `public_body_id`, meeting date, venue, start and end times as printed, source URL, source sha256, text source (`text_layer`, `ocr` or `mixed`) and, when OCR was used, the OCR engine identifier. The attendance table SHALL be rendered as one labelled list per printed category, keeping each name's text as printed.

#### Scenario: Attendance block

- **WHEN** the header lists "Attendees – (Sectoral Representatives): Mr. Dave Anderson (DA) PPN Rep, …"
- **THEN** the rendered file has a "Sectoral Representatives" list whose entries keep each name and role text as printed

#### Scenario: OCR provenance in front matter

- **WHEN** a meeting whose PDF was fully scanned is rendered
- **THEN** its front matter gives `text_source: ocr` and the OCR engine identifier

### Requirement: Word preservation is verified

After rendering, the sequence of words in the rendered body, with markup removed, SHALL equal the source's word sequence with only the removed furniture and the override-skipped pages taken out. The source words SHALL be the text-layer words or the OCR words that ingestion produced for each page. A mismatch SHALL produce a `RenderMismatch` error giving the first differing position and words. A meeting with a mismatch SHALL NOT be published.

#### Scenario: Lossless render passes

- **WHEN** a meeting renders with every non-furniture word kept in order
- **THEN** the check passes and the meeting is eligible for publication

#### Scenario: Dropped word fails

- **WHEN** rendering loses a word from an agenda item
- **THEN** a `RenderMismatch` error is recorded and the meeting is not published

#### Scenario: OCR meeting is checked against its OCR words

- **WHEN** a scanned meeting is rendered
- **THEN** the check compares the rendered words with the OCR words in page order, and a lost OCR word fails it as `RenderMismatch`
