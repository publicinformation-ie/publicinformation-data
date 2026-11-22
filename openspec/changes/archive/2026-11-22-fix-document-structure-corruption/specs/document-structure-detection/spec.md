# Spec Delta

## MODIFIED Requirements

### Requirement: TOC-name occurrence-scoring strategy

The system SHALL provide a detection strategy that parses a Table of Contents page to obtain canonical heading entries (title plus inferred level), locates each distinct entry's occurrences in the document body by exact text match of normalized (control-character-stripped, whitespace-collapsed, case-insensitive, punctuation-trimmed) text across one to three joined consecutive body lines — consecutive in reading order (top-to-bottom, then left-to-right), with deterministic number-prefix stripping on the body side, and never fuzzy similarity — scores each occurrence by font rules (heading-like size, monotonic so that larger relative to body size scores higher; boldness; isolation between body-sized text; and exclusion of the TOC page and of running-header lines), and selects the highest-scoring occurrence as the section boundary, recovering start_page, start_y, and the heading number from that occurrence. Distinct TOC entries that share a normalized title (for example a per-chapter "Introduction") SHALL each resolve to their own occurrence rather than collapsing to one boundary. For an occurrence that spans two or three joined body lines, the boundary SHALL record the full vertical span of the heading block so downstream assembly can exclude the whole heading rather than only its first line.

#### Scenario: TOC entry matched to a body heading

- **WHEN** a TOC entry title normalizes to a string that exactly matches a joined run of one to three consecutive body lines, after any configured deterministic number-prefix stripping
- **THEN** that occurrence becomes a candidate boundary with its own start_page and start_y

#### Scenario: Joined runs follow reading order

- **WHEN** a heading's continuation line precedes it in the extractor's raw span order but follows it in reading order
- **THEN** the joined run that matches the TOC entry is formed in reading order, so the heading and its continuation join in the order a reader sees them

#### Scenario: Best occurrence selected by font score

- **WHEN** a TOC entry title occurs multiple times in the document
- **THEN** the occurrence with the highest font score is selected, with ties broken by earliest document order

#### Scenario: Repeated TOC titles resolve to distinct boundaries

- **WHEN** a TOC lists the same title more than once (for example a per-chapter "Introduction" or "References")
- **THEN** each distinct TOC entry is matched and scored independently and produces its own boundary, rather than all occurrences of the shared title collapsing to one node

#### Scenario: Occurrence below the score floor is rejected

- **WHEN** an entry's best-scoring occurrence falls below the configured score floor
- **THEN** the entry is recorded as a TocEntryNoHeading error and no boundary is created for it

#### Scenario: TOC page excluded from candidates

- **WHEN** the only occurrence of a TOC entry title is on the TOC page itself
- **THEN** that entry is not promoted to a boundary and is recorded as unmatched in errors.json

#### Scenario: Unmatchable entry is logged, not guessed

- **WHEN** a TOC entry title has no confident body occurrence under the configured matching rule
- **THEN** the entry is recorded as a TocEntryUnmatched error and no boundary is created for it

### Requirement: Strategy placement and fallback

The system SHALL insert the TOC-name strategy between the existing `outline` and `numbering` strategies in the cascade, so that a document with a PDF outline still uses `outline` and never reaches the TOC-name strategy. The strategy SHALL activate only when the share of plausible body-heading TOC entries matched above the score floor meets a configurable match-rate gate (initial value 60%, a module constant set from the experiment); TOC entries classified as non-heading furniture (abbreviations, glossary, list-of-figures, and the like) SHALL be excluded from the gate's denominator. The strategy SHALL supplement its matched boundaries with legacy-detected **numbered** headings not present in the TOC (excluding running-header lines, deduplicated by boundary; the font strategy is not used for supplementing), and SHALL fall back to the existing cascade (numbering, font, flat) when no usable TOC exists or the match rate is below the gate.

A line on a detected TOC page SHALL NOT produce a boundary under any strategy. The numbering strategy, the font strategy, and the numbered-heading supplement SHALL exclude the detected TOC pages from their candidate lines, as the occurrence index already does, and SHALL do so even when the TOC-name strategy itself did not fire (no usable TOC, or a match rate below the gate), so a table-of-contents line can never be published as a body heading.

#### Scenario: Usable TOC activates strategy

- **WHEN** a document has a TOC and the match rate meets the configured gate
- **THEN** the TOC-name strategy is used and its detection_method is recorded as `toc`

#### Scenario: Low match rate falls back

- **WHEN** a document has a TOC but the match rate is below the configured gate
- **THEN** the system falls back to the numbering and font strategies and logs a LowTocMatchRate error

#### Scenario: TOC page lines never become boundaries in the fallback cascade

- **WHEN** a TOC page is detected but the TOC-name strategy does not fire, and that page's lines include numbered, dot-leader, or heading-sized entries
- **THEN** the numbering and font strategies skip the detected TOC pages and no node's title or slug is derived from a TOC line

#### Scenario: Supplement excludes TOC pages

- **WHEN** the numbered-heading supplement runs over a document whose TOC page carries numbered entries such as `1.1 Landscape and Visual`
- **THEN** those TOC-page lines are excluded from the supplement and only body occurrences can be added

#### Scenario: No TOC present

- **WHEN** a document has no detectable TOC page
- **THEN** the system uses the existing outline, numbering, font, and flat cascade unchanged

#### Scenario: Outline still wins

- **WHEN** a document's PDF has an outline
- **THEN** the outline strategy is used and the TOC-name strategy is not reached

#### Scenario: Missing level signal yields a flat tree

- **WHEN** a TOC has no usable level signal (no indentation, no numbering depth, no size hierarchy)
- **THEN** every entry becomes level 1 (a flat tree), which is the correct structure for flat documents; correctness is guarded by the match-rate gate and `validate_split` rather than a fallback

### Requirement: Deterministic split validation

The system SHALL provide a pure `validate_split(nodes, page_count)` function that returns a list of issue strings, and SHALL consider a split valid only when every node title passes a heading-candidate guard, no two nodes share the same (start_page, start_y) boundary, the union of node page ranges covers from the first node's start_page through page_count without gaps, and the node set contains at least one level-1 node. Pages before the first node's start page are front matter, not a gap.

A non-empty node set with no level-1 node SHALL be invalid regardless of how many distinct levels it contains, because the tree then has no root heading a reader or a downstream consumer can start from. A node set whose nodes are all level 1 is a flat tree and SHALL be valid; no synthetic level SHALL be invented to satisfy the check.

#### Scenario: Valid split yields no issues

- **WHEN** a split has real heading titles, unique boundaries, at least one level-1 node, and coverage from its first boundary to the last page
- **THEN** validate_split returns an empty list

#### Scenario: Front matter is not flagged

- **WHEN** the first node starts on a page after page 1 (for example cover and TOC pages before it)
- **THEN** validate_split returns no coverage issue for the pages before the first node

#### Scenario: Junk title flagged

- **WHEN** a node title contains no letters, is a single character, is punctuation-only, begins with a currency symbol, or contains dot leaders
- **THEN** validate_split returns an issue naming that node

#### Scenario: Gap in page coverage flagged

- **WHEN** some page between the first node's start page and page_count is not covered by any node's range
- **THEN** validate_split returns an issue naming that page

#### Scenario: Tree with no level-1 node flagged

- **WHEN** every node in a non-empty node set is level 2 or deeper, whether or not the set contains more than one distinct level
- **THEN** validate_split returns an issue stating that the tree has no level-1 node

#### Scenario: Genuinely flat tree stays valid

- **WHEN** every node in a node set is level 1 (for example a map atlas whose sections genuinely are flat)
- **THEN** validate_split returns no level issue and no synthetic level is invented

## ADDED Requirements

### Requirement: Reading-order line extraction

The system SHALL group each page's spans into lines and order those lines by vertical position (top before bottom), then horizontal position, before any strategy consumes them, instead of preserving the extractor's raw span order. The vertical-position comparison SHALL round coordinates to a named module constant so that lines sharing a baseline sort by horizontal position rather than by sub-point noise. Line sizing (a line's size and font come from its largest span) SHALL be unchanged.

#### Scenario: Footer page number precedes body text in extraction order

- **WHEN** a page's spans are emitted such that the footer page number (bottom-most, left-most) precedes the running header and every body line in raw order
- **THEN** the grouped lines are ordered top-down, with the running header before body lines and the footer page number last

#### Scenario: Lines sharing a baseline sort left to right

- **WHEN** two lines on the same visual baseline differ in vertical position by less than the rounding constant
- **THEN** they are ordered by horizontal position, left before right

#### Scenario: Reading order applies to every strategy

- **WHEN** the outline, TOC-name, numbering, or font strategy consumes pages
- **THEN** each strategy sees the same reading-ordered lines

#### Scenario: Reordering does not reduce TOC match rates

- **WHEN** the corpus is re-detected with reading-order lines
- **THEN** no document's TOC match rate falls below its previously recorded match rate, and any document whose rate falls is reported for review rather than accepted silently

### Requirement: TOC page entry filtering

When parsing a flagged TOC page, the system SHALL skip bare page-number lines wherever they appear on the page (not only in a right-hand column), skip lines identified as running-header or footer lines, and begin collecting entries at the parsed `contents`/`Table of Contents` title line in reading order. Skipping a line SHALL not be classified as creating any TOC entry, and SHALL not contribute an indentation position to level inference.

#### Scenario: Footer number does not open a separate-line-number entry

- **WHEN** a flagged TOC page's first reading-order lines are a footer page number `2`, the running header, then real TOC entries
- **THEN** no entry is created from `2`, the running header is skipped, and collection starts at the first real TOC entry line after the title

#### Scenario: Skipped lines do not pollute indentation inference

- **WHEN** a skipped footer or header line sits at a left edge no real entry shares
- **THEN** its left edge contributes no indentation bucket, so remaining entries that share one left edge infer a single level rather than being pushed one level deeper

#### Scenario: TOC title line is not an entry

- **WHEN** the `Table of contents` title line appears anywhere in the flagged TOC block
- **THEN** it produces no TOC entry regardless of its position in raw span order

### Requirement: Heading title normalization

The system SHALL strip from every accepted title any leading pipe or dash fragment, any trailing dot leaders together with a glued page number, and any control characters, then SHALL apply the heading-candidate guard. Interior dot leaders SHALL NOT be stripped. A rejected text SHALL never become a node title, a slug source, or a published URL segment.

#### Scenario: Leading pipe fragment

- **WHEN** a heading or TOC entry yields the text `| Investing in Transport`
- **THEN** the node title is `Investing in Transport` with the leading pipe removed

#### Scenario: Control character in a matched heading

- **WHEN** a matched heading contains an interior control character such as `\x07`
- **THEN** the control character is stripped from the node title and the slug

#### Scenario: Interior dot-leader line is rejected, not cleaned

- **WHEN** a line such as `Landscape and Visual ......... 23` is considered by the numbering or font strategy
- **THEN** the line is rejected as a non-heading candidate and produces no node; it is not rewritten into the title `Landscape and Visual`

#### Scenario: Punctuation-only or letterless text is never a title

- **WHEN** an extracted line's text is only digits, glyph(s), or punctuation (for example `1`, `”`, `l`, `21`, `2040`, `"`)
- **THEN** the text is rejected wherever a heading is accepted, and no node is created from it

### Requirement: Legacy-cascade heading guard

When the `numbering` or `font` strategy considers a line as a potential heading, the system SHALL apply the heading-candidate guard to the candidate title. It SHALL join up to two reading-order-consecutive lines into one candidate when they share a rounded type size and bold class, sit within a named vertical-adjacency constant, and the first does not end a sentence. Join thresholds SHALL be module constants pinned by fixtures in both directions.

#### Scenario: Chapters from bare numerals with separate titles

- **WHEN** a chapter-opener page renders a lone oversized numeral `1` (or cover text `2040`, or a map glyph `l`) at a heading level's size, followed by the chapter's real title at another size
- **THEN** the numeral (or cover text, or glyph line) produces no node, and no chapter is titled `1`, `2040`, or `l`

#### Scenario: Oversized decorative glyph

- **WHEN** a pull-quote glyph rendered at a heading-size produces a one-character line
- **THEN** no section is created from that line

#### Scenario: Wrapped heading joined across lines

- **WHEN** a heading is wrapped so that its continuation text sits on the following line in the same style (for example `Safe and Green` / `Mobility`)
- **THEN** one node is created whose title joins both lines, and no node titles are the fragments

#### Scenario: Same-size columns are not joined

- **WHEN** two lines share a rounded type size and bold class but sit in separate columns, so their vertical gap exceeds the adjacency constant
- **THEN** they are not joined and each is judged as its own candidate

### Requirement: Production validation gate with explicit failure recording

The detection step SHALL validate every document's tree with `validate_split` after overrides are merged and before the output record is written, recording each failure in the step's errors file with the document slug, the failing check, and the offending value. Validation SHALL never alter, re-level, or drop nodes, and a failing document SHALL still be written to output. A recorded failure SHALL be resolvable only by a code fix or a committed override entry.

#### Scenario: Junk title is flagged by the production step

- **WHEN** a detected tree contains a node whose title is a bare numeral or glyph
- **THEN** the step records a validation failure naming the document and that title, independent of which strategy produced the node

#### Scenario: Duplicate boundary is flagged

- **WHEN** two nodes in the produced tree share the same (start_page, start_y)
- **THEN** the step records a validation failure naming both nodes

#### Scenario: Tree with no level-1 node is flagged

- **WHEN** a produced tree's nodes are all level 2 or deeper
- **THEN** the step records a validation failure naming the document and the missing level-1 node

#### Scenario: Failing document is still written to output

- **WHEN** a document's tree fails validation
- **THEN** its record is written to output with its nodes unaltered, alongside the recorded failure

#### Scenario: Valid tree passes silently

- **WHEN** a detected tree satisfies the deterministic split validation criteria
- **THEN** no validation failure is recorded for that document

### Requirement: Post-detection corpus audit

The system SHALL provide a read-only means to report, per document, whether its detected tree or published artifact satisfies the deterministic split validation criteria, deriving all findings from step outputs and committed publications rather than manual lists. The report SHALL include each document's detection method, node counts, level distribution, and TOC match rate, so a re-detection can be compared against the previously recorded run.

#### Scenario: Corpus audit reports affected documents

- **WHEN** the audit is run over every processed document's detected tree
- **THEN** it lists per document the detection method, node counts, and any failure of the deterministic split validation criteria, with none of the cited problems left undiscovered: bare numerals on chapter openers, glyphs, map text, cover text, dot-leader lines, and pipes each appear as their classification, not as a generic error

#### Scenario: Audit compares a re-detection against the previous run

- **WHEN** the audit is run after a change to detection
- **THEN** it reports per document the change in node count, level distribution, and TOC match rate against the previously recorded values, so a regression in a document that still validates is visible
