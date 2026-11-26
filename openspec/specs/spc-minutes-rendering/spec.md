## Purpose

Turns each meeting's minutes PDF into verbatim, structured Markdown that reads well on a phone, and proves that no word of the source was added, lost or changed along the way.

## Requirements

### Requirement: Rendered minutes are verbatim

The rendered body SHALL contain every word of the minutes text, in source order, except removed page furniture. It SHALL NOT summarise, paraphrase, correct spelling, expand initials or add words, apart from Markdown markup and the generated front matter.

#### Scenario: Typos are preserved

- **WHEN** the source reads "Meat has 6 MD's"
- **THEN** the rendered body reads "Meat has 6 MD's"

#### Scenario: Initials are preserved

- **WHEN** the source refers to a member as "SD"
- **THEN** the rendered body reads "SD", not the member's full name

### Requirement: Page furniture is removed

The running header ("Miontuairiscí/Meeting Minutes"), the "Page N of M" line and the repeated footer address block SHALL be removed from every page. Removal SHALL match only text that repeats as furniture on the committee's pages. Each removed line SHALL be counted in the step's output.

#### Scenario: Footer removed from every page

- **WHEN** a 4-page minutes PDF is rendered
- **THEN** the footer address block and the page number appear 0 times in the rendered body

#### Scenario: Body text resembling furniture is kept

- **WHEN** an agenda item's text mentions "www.meath.ie" in a sentence
- **THEN** that sentence is kept

### Requirement: Broken lines are rejoined

Lines broken by the PDF's layout SHALL be joined into paragraphs, including across page breaks. A line break SHALL be kept only where a new paragraph, bullet, heading or labelled line (such as "Proposed by;") begins.

#### Scenario: Sentence across a page break

- **WHEN** a sentence ends one page with "with LEO, Economic" and continues on the next with "Development, Local Business, …"
- **THEN** the rendered body has one paragraph containing "with LEO, Economic Development, Local Business, …"

### Requirement: Agenda items become headings

Each numbered agenda item line (for example "4.0 Climate Action – Decarbonisation Zones (DZ's)") SHALL become a second-level heading with the item's number and title as printed. Unnumbered "AOB" sections SHALL become headings too. Bullet characters SHALL become Markdown list items. Each heading SHALL have a stable anchor derived from its item number.

#### Scenario: Numbered item

- **WHEN** the source has the line "5.0 Work Programme 2026"
- **THEN** the rendered body has the heading `## 5.0 Work Programme 2026` with anchor `item-5-0`

#### Scenario: Bullets

- **WHEN** the source has lines beginning "•"
- **THEN** each becomes a Markdown list item with its text unchanged

### Requirement: The meeting header is rendered as structured front matter and a heading block

The rendered file SHALL begin with front matter giving the meeting ID, committee ID and name, `public_body_id`, meeting date, venue, start and end times as printed, source URL and source sha256. The attendance table SHALL be rendered as one labelled list per printed category, keeping each name's text as printed.

#### Scenario: Attendance block

- **WHEN** the header lists "Attendees – (Sectoral Representatives): Mr. Dave Anderson (DA) PPN Rep, …"
- **THEN** the rendered file has a "Sectoral Representatives" list whose entries keep each name and role text as printed

### Requirement: Rendered Markdown contains no raw HTML

The rendered Markdown SHALL contain no raw HTML elements, and characters that Markdown or HTML would interpret as markup SHALL be escaped, so the website can render it without sanitisation.

#### Scenario: Angle brackets in source

- **WHEN** the source text contains "<" or ">"
- **THEN** the rendered Markdown escapes them and contains no HTML tag

### Requirement: Word preservation is verified

After rendering, the sequence of words in the rendered body, with markup removed, SHALL equal the source's word sequence with only the removed furniture taken out. A mismatch SHALL produce a `RenderMismatch` error giving the first differing position and words. A meeting with a mismatch SHALL NOT be published.

#### Scenario: Lossless render passes

- **WHEN** a meeting renders with every non-furniture word kept in order
- **THEN** the check passes and the meeting is eligible for publication

#### Scenario: Dropped word fails

- **WHEN** rendering loses a word from an agenda item
- **THEN** a `RenderMismatch` error is recorded and the meeting is not published
