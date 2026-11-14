## Purpose

Defines when the FOI pipeline accepts or rejects a PDF's extracted table, so that a rejection always means the table structure is unreliable, never just that the text is imperfect or that something is wrong which a later step already repairs.

## Requirements

### Requirement: Rejection is reserved for structural defects
The gate SHALL reject a PDF table only when one or more structural checks fail: too few data rows, low row-width uniformity, a high share of fragment rows, low column-type purity, or a high rate of words broken across column boundaries. Defects confined to the text of a single cell SHALL NOT cause rejection on their own.

#### Scenario: Run-together words in otherwise sound table
- **WHEN** a PDF table has uniform row widths, no fragment rows and pure column types, but more than 2% of its cells contain run-together tokens such as `informaQon` or `andThe`
- **THEN** the gate accepts the table and keeps its rows

#### Scenario: Structurally broken table
- **WHEN** a PDF table's row-width uniformity is below the threshold
- **THEN** the gate rejects it, empties its rows and records `TableStructureUnreliable` with `width_uniformity` among the failed checks

### Requirement: Adjacent complete values are not split words
A pair of adjacent cells SHALL count as a word broken across a column boundary only when the boundary leaves a word stub on at least one side. A cell that ends in a complete word next to a cell that begins with a lowercase complete word SHALL NOT count.

#### Scenario: Requester type next to lowercase description
- **WHEN** a row has `Journalist` in one cell and `all records relating to…` in the next
- **THEN** the pair does not count toward the split-word rate

#### Scenario: Word broken by a column boundary
- **WHEN** a row has `S` in one cell and `ummary of request` in the next
- **THEN** the pair counts toward the split-word rate

### Requirement: Rows repeating the header do not cause rejection
Rows identical to the detected header row SHALL be excluded before the structural checks are computed. The share of such rows SHALL be recorded but SHALL NOT on its own cause rejection.

#### Scenario: Header repeated on every page
- **WHEN** a multi-page PDF table repeats its header row at the top of each page and is otherwise sound
- **THEN** the gate accepts it, and no published record from it carries header text as a field value

### Requirement: Every gated file records its signals
For every PDF table it assesses, the gate SHALL record the structural signals, the in-cell text-defect rate and the repeated-header share as separate values. For every rejected file it SHALL list the checks that failed.

#### Scenario: Accepted file with poor text
- **WHEN** a table passes the gate with a high in-cell text-defect rate
- **THEN** its recorded score shows that rate, so the file can be found for cell repair

#### Scenario: Rejected file
- **WHEN** a table is rejected
- **THEN** its `TableStructureUnreliable` entry names only structural checks among the failed checks

### Requirement: Manual overrides bypass the gate
A PDF whose URL has a manual column mapping SHALL never be rejected by the gate, whatever its score.

#### Scenario: Overridden file with poor structure
- **WHEN** a PDF listed in the manual column mappings fails a structural check
- **THEN** its rows are kept and its score is marked override-exempt
