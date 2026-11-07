# Spec Delta

## ADDED Requirements

### Requirement: Reading-order line extraction

The system SHALL group each page's spans into lines and order those lines by vertical position (top before bottom), then horizontal position, before any strategy consumes them, instead of preserving the extractor's raw span order. Line sizing (a line's size and font come from its largest span) SHALL be unchanged.

#### Scenario: Footer page number precedes body text in extraction order

- **WHEN** a page's spans are emitted such that the footer page number (bottom-most, left-most) precedes the running header and every body line in raw order
- **THEN** the grouped lines are ordered top-down, with the running header before body lines and the footer page number last

#### Scenario: Reading order applies to every strategy

- **WHEN** the outline, TOC-name, numbering, or font strategy consumes pages
- **THEN** each strategy sees the same reading-ordered lines

### Requirement: TOC page entry filtering

When parsing a flagged TOC page, the system SHALL skip bare page-number lines wherever they appear on the page (not only in a right-hand column), skip lines identified as running-header or footer lines, and begin collecting entries at the parsed `contents`/`Table of Contents` title line in reading order. Skipping a line SHALL not be classified as creating any TOC entry.

#### Scenario: Footer number does not open a separate-line-number entry

- **WHEN** a flagged TOC page's first reading-order lines are a footer page number `2`, the running header, then real TOC entries
- **THEN** no entry is created from `2`, the running header is skipped, and collection starts at the first real TOC entry line after the title

#### Scenario: TOC title line is not an entry

- **WHEN** the `Table of contents` title line appears anywhere in the flagged TOC block
- **THEN** it produces no TOC entry regardless of its position in raw span order

### Requirement: Structural level anchoring

When a parsed TOC entry's title matches a structural prefix (`Chapter <n>`, `Section <n>`, `Part <n>`, case-insensitive), the system SHALL infer level 1 for that entry and level greater than 1 for subsequent entries until the next structurally anchored entry, without applying an indentation signal, unless explicit numbering depth indicates otherwise. This rule SHALL take precedence over the indentation heuristic. Level inference SHALL remain deterministic and never fuzzy.

#### Scenario: Shared indentation with chapter-prefixed titles

- **WHEN** every entry on a TOC page shares the same left edge `x0`, and entries alternate between `Chapter N – Title` and unprefixed section titles
- **THEN** chapter-prefixed entries are level 1, the entries following each chapter prefix are level 2, and the tree contains at least one level-1 node

#### Scenario: No structural prefixes falls back to existing signals

- **WHEN** no TOC entry title matches a structural prefix
- **THEN** levels are inferred exactly as before (numbering depth, then indentation, then all level 1)

### Requirement: Heading title normalization

The system SHALL strip from extracted and TOC-parsed titles any leading pipe or dash fragments, any interior or trailing dot leaders and trailing page numbers, and any control characters; a title containing no letters SHALL be rejected by the heading-candidate guard wherever a title is accepted. A rejected text SHALL never become a node title, a slug source, or a published URL segment.

#### Scenario: Leading pipe fragment

- **WHEN** a heading or TOC entry yields the text `| Investing in Transport`
- **THEN** the node title is `Investing in Transport` with the leading pipe removed

#### Scenario: Control character in a matched heading

- **WHEN** a matched heading contains an interior control character such as `\x07`
- **THEN** the control character is stripped from the node title and the slug

#### Scenario: Dot-leader TOC line outside the TOC strategy

- **WHEN** a line such as `Landscape and Visual .........` is considered by the numbering or font strategy
- **THEN** its dot leaders and trailing number are not silently passed through: the line either yields the clean title `Landscape and Visual` or is rejected as a non-heading candidate, and no slug or title contains the leader dots

#### Scenario: Punctuation-only or letterless text is never a title

- **WHEN** an extracted line's text is only digits, glyph(s), or punctuation (for example `1`, `”`, `l`, `21`, `2040`, `"`)
- **THEN** the text is rejected wherever a heading is accepted, and no node is created from it

### Requirement: Legacy-cascade heading guard

When the `numbering` or `font` strategy considers a line as a potential heading, the system SHALL apply the heading-candidate guard to the candidate title and SHALL join up to two consecutive lines that share the same heading-relevant style (size, font class) when the first line does not end a sentence, producing one candidate from the joined text rather than two separate nodes.

#### Scenario: Chapters from bare numerals with separate titles

- **WHEN** a chapter-opener page renders a lone oversized numeral `1` (or cover text `2040`, or a map glyph `l`) at a heading level's size, followed by the chapter's real title at another size
- **THEN** the numeral (or cover text, or glyph line) produces no node, and no chapter is titled `1`, `2040`, or `l`

#### Scenario: Oversized decorative glyph

- **WHEN** a pull-quote glyph rendered at a heading-size produces a one-character line
- **THEN** no section is created from that line

#### Scenario: Wrapped heading joined across lines

- **WHEN** a heading is wrapped so that its continuation text sits on the following line in the same style (for example `Whole of journey` / `approach`, or `Integration of land use` / `and transport planning`)
- **THEN** one node is created whose title joins both lines, and no node titles are the fragments

### Requirement: Structural tree validity criteria

A detected tree SHALL be considered valid only when every node title passes the heading-candidate guard, no two nodes share the same (start_page, start_y) boundary, node page ranges cover from the first node's start page through the page count without gaps, and when the tree contains nodes of more than one level it determines at least one level-1 node. A tree whose nodes are all a single level SHALL be valid regardless of that level.

#### Scenario: Tree with only level-2 nodes is invalid

- **WHEN** a detected tree's nodes span more than one level but none is level 1
- **THEN** the tree is invalid and the failure names the document and the missing level-1 node

#### Scenario: Genuinely flat tree stays valid

- **WHEN** every node in a detected tree is level 1 (for example a map atlas whose sections genuinely are flat)
- **THEN** the tree is valid with no synthetic level invented

### Requirement: Production validation gate with explicit failure recording

The detection step SHALL validate every document's tree before writing its output record, failing strictly per the structural-tree-validity criteria. A failure SHALL be recorded in the step's errors file with the document slug, the failing check, and the offending value, and SHALL never silently alter or drop nodes. A failing document SHALL still be written to output so downstream consumers and triage can see it.

#### Scenario: Junk title is flagged by the production step

- **WHEN** a detected tree contains a node whose title is a bare numeral or glyph
- **THEN** the validation recorded with that document names the title, independent of which strategy produced the node

#### Scenario: Duplicate boundary is flagged

- **WHEN** two nodes in the produced tree share the same (start_page, start_y)
- **THEN** the validation records a failure naming both nodes

#### Scenario: Valid tree passes silently

- **WHEN** a detected tree satisfies the structural-tree-validity criteria
- **THEN** no validation failure is recorded for that document

#### Scenario: Tree with only level-2 nodes is flagged

- **WHEN** a detected tree's nodes are all level 2 while at least one node set has more than one level (a tree with a section/subsection split but no chapter)
- **THEN** validation records a failure identifying the document, and the record carries the validation failure for triage

#### Scenario: Junk title is flagged by the production step

- **WHEN** a detected tree contains a node whose title is a bare numeral or glyph
- **THEN** the validation recorded with that document names the title, independent of which strategy produced the node

#### Scenario: Duplicate boundary is flagged

- **WHEN** two nodes in the produced tree share the same (start_page, start_y)
- **THEN** the validation records a failure naming both nodes

#### Scenario: Valid tree passes silently

- **WHEN** a detected tree satisfies every check above
- **THEN** no validation failure is recorded for that document

### Requirement: Post-detection corpus audit

The system SHALL provide a means to report, per document, whether its detected tree (or its published artifact) satisfies the structural-tree-validity criteria, so structure problems can be enumerated across the whole corpus without inspecting each publication by hand. The audit SHALL be read-only and SHALL derive all findings from entity outputs and committed publications, not from manual lists.

#### Scenario: Corpus audit reports affected documents

- **WHEN** the audit is run over every processed document's detected tree
- **THEN** it lists per document the detection method, node counts, and any failure of the structural-tree-validity criteria, with none of the cited problems left undiscovered: bare numerals on chapter openers, glyphs, map text, cover text, dot-leader lines, and pipes each appear as their classification, not as a generic error
