# active-travel-allocation-extraction Specification

## Purpose
Turns the NTA's annual Active Travel allocation PDFs into verified allocation records, by reading a committed publication list, classifying every table row, and refusing to publish any authority section whose figures the document's own arithmetic does not confirm.

## Requirements

### Requirement: The committed publication list is the only ingestion source

The years and documents to be ingested SHALL be declared in committed configuration, each entry naming the year, the publication page, the document URL and the document's kind. The pipeline SHALL NOT ingest a year or document absent from that list, and SHALL NOT derive the allocation year from page text.

#### Scenario: Adding a year is a configuration edit

- **WHEN** a new annual document is added to the committed list
- **THEN** the next run ingests it, with no code change

#### Scenario: An undeclared year is not ingested

- **WHEN** a document exists on the publisher's site but is absent from the committed list
- **THEN** no record carries that document's year

#### Scenario: Year comes from the list

- **WHEN** a document's pages do not print their year, or print it inconsistently
- **THEN** every record from that document carries the year declared in the committed list

### Requirement: Documents are cached, not committed

Each declared document SHALL be fetched into a git-ignored cache and reused on later runs without a network request. The document's bytes SHALL NOT be committed, and the observed digest SHALL be recorded in the run's output.

#### Scenario: Cold cache

- **WHEN** a declared document is not in the cache and its URL is reachable
- **THEN** the run downloads it, records its digest, and the extraction steps read the cached copy

#### Scenario: Warm cache

- **WHEN** a cached copy of a declared document exists
- **THEN** no network request is made for it

#### Scenario: Source unreachable

- **WHEN** a declared document is neither cached nor fetchable
- **THEN** the run records an error naming it and ingests no records from it

### Requirement: Table extraction is gated structurally

A page's extracted table SHALL be accepted only when its row structure is sound. A page whose table fails the structural gate SHALL yield no records and SHALL be recorded as an error naming the page and the failed checks. A single cell's imperfect text SHALL NOT cause rejection by itself.

#### Scenario: Sound table with imperfect cell text

- **WHEN** a page's table has uniform row widths but one cell contains a run-together word
- **THEN** the page's rows are used and the defect is recorded as cell-level, not as a rejected page

#### Scenario: Broken table shape

- **WHEN** a page's table rows vary in width beyond the accepted tolerance
- **THEN** no records are produced from that page and an error names the page and the failed checks

### Requirement: Every row is classified before use

Every extracted row SHALL be classified into exactly one kind: document title, column header, recipient heading, funding-stream divider, project row, subtotal or total, footnote, or blank. Only project rows SHALL become records. A row that fits no kind SHALL be recorded as an error and SHALL NOT become a record.

#### Scenario: Footnote rows are not projects

- **WHEN** a row reads `* Scheme to be designed by NTA consultants under different project code`
- **THEN** it is classified as a footnote and produces no record

#### Scenario: An unclassifiable row is reported

- **WHEN** a row has cells that fit none of the known kinds
- **THEN** the run records an error carrying the document, page and raw cells, and publishes nothing from that row

### Requirement: Amounts are normalised with every repair recorded

The printed amount SHALL be read as whole euro, treating the currency symbol, thousands separators and incidental whitespace inside the printed number as formatting. Each row whose printed text was changed to obtain the value SHALL be recorded, naming the raw cell and the value used.

#### Scenario: Digits split by whitespace

- **WHEN** a cell prints `€ 2 0,000,000`
- **THEN** the record carries `20000000` and the repair is recorded against that row

#### Scenario: A non-numeric amount is withheld

- **WHEN** an amount cell prints `€ -`, is empty, or mixes text into the number
- **THEN** no record is published from that row and an error names the raw cell

### Requirement: Recipients are attributed from two independent signals

Each project row SHALL be attributed to a recipient using its section's recipient heading, corroborated by the project-code prefix. A row whose signals agree is attributed to that recipient. A row whose signals conflict, or whose recipient cannot be determined, SHALL NOT be published and SHALL be recorded as an error.

#### Scenario: Rows before the first heading

- **WHEN** a section's first page carries project rows whose recipient heading appears only on a later page
- **THEN** those rows are attributed from the corroborating code prefix, and no row is attributed by position alone

#### Scenario: Heading and code prefix disagree

- **WHEN** a row's section heading names one recipient and its code prefix another
- **THEN** the row is withheld and an error names both signals

### Requirement: Funding streams come from the document's money anchors

Each project row SHALL be assigned to a funding stream, and the stream SHALL be determined from the subtotal and total rows that close each block rather than from page position. A block that opens without its divider heading SHALL still be assigned correctly when its closing anchors bracket it.

#### Scenario: Missing divider heading

- **WHEN** a section's second block has no divider heading but is closed by a subtotal and a combined total
- **THEN** its rows are assigned to the other-NTA-streams stream

#### Scenario: Rows outside any bracketed block

- **WHEN** project rows cannot be placed inside any block bounded by anchors
- **THEN** they are withheld and the run records an error naming the section and rows

### Requirement: Sections are published only when their arithmetic reconciles

For each recipient and funding stream, the sum of the section's project-row allocations SHALL equal the total declared in the document. When it does not, no record from that section SHALL be published, and the run SHALL record an error naming the recipient, the stream, both sums and the difference.

#### Scenario: Reconciling section

- **WHEN** a section's project rows add up to its declared total
- **THEN** the section's records are eligible for publication

#### Scenario: Section off by a rounding difference

- **WHEN** a section's rows differ from its declared total by any amount, including one euro
- **THEN** none of that section's records are published and the difference is reported

### Requirement: Body-level summaries are a second, independent check

Where a document carries a body-level summary of allocations, the per-recipient totals extracted from its project tables SHALL be compared with that summary. A recipient whose totals disagree SHALL be recorded as an error and its records SHALL NOT be published.

#### Scenario: Summary table present

- **WHEN** a document's front matter lists a per-recipient total that differs from the sum of that recipient's extracted project rows
- **THEN** the recipient is reported and none of its records are published

#### Scenario: BSEP-style column is not compared with project rows

- **WHEN** a summary table carries a separate allocation column with no project-level counterpart
- **THEN** that column is excluded from the comparison and is not published as a project allocation

### Requirement: Withheld data is always reported

Every row, section or document withheld from publication SHALL appear in the step's errors with the document, page, recipient and raw cells needed to resolve it. The pipeline SHALL NOT silently drop a row, silently null a field, or publish a substituted value.

#### Scenario: A withheld row is traceable

- **WHEN** a row is withheld for any reason
- **THEN** an error entry identifies the document, page and raw cells

#### Scenario: Withheld sections do not disappear quietly

- **WHEN** a section is withheld because it failed reconciliation
- **THEN** the run's error output names the section and the reconciliation difference
