# document-structure-detection Specification

## Purpose
Detects the chapter/section tree of a document PDF for the document pipeline, using heading detection strategies, and provides a deterministic comparison experiment, split validation, and comparison metrics so a new TOC-name occurrence-scoring strategy can be proven better than the legacy cascade.

## Requirements

### Requirement: Deterministic TOC comparison experiment

Before the TOC-name strategy is implemented, the system SHALL provide a read-only, dated experiment under `pipelines/document_pipeline/experiments/` that runs a prototype TOC parse/match/score alongside the legacy detection cascade over every document's cached `extract_pages` output, and SHALL record its hypothesis, per-document results, and conclusion in the experiment's README without modifying any pipeline output. The experiment SHALL measure, per document: TOC page detection outcome and signal; TOC entry count and shape classification (inline vs separate-line numbers, right-hand page-number lines, ASCII vs Unicode dot leaders, single vs multiple TOCs); the share of TOC entries that are non-heading furniture; the repeated-title rate; match rate under each candidate matching rule (exact normalized; exact with number-prefix tolerance), reported both over all entries and over plausible body-heading entries only; level-signal availability; running-header interference; validate_split issue counts and node counts for both strategies; and slug preservation against the current strategy (including any `override.json` entries a switch would orphan). The change's matching rule, thresholds, and detection rules SHALL be refined from these results before implementation tasks begin.

#### Scenario: Experiment reports per-document diagnostics

- **WHEN** the experiment runs over the corpus's extracted pages
- **THEN** its README records, for every document, the diagnostics listed above for both the prototype and the legacy cascade

#### Scenario: Experiment is read-only

- **WHEN** the experiment runs
- **THEN** no pipeline step output, golden file, or published artifact is modified; only the experiment's own results are written

#### Scenario: Refinement gate

- **WHEN** the experiment results are reviewed
- **THEN** the strategy's matching rule, thresholds, and detection rules are updated in this change's design before implementation tasks start

#### Scenario: Match rates below the gate on the corpus

- **WHEN** no candidate matching rule clears the match-rate gate on the documents the change targets
- **THEN** the change is reconsidered rather than implemented with guessed thresholds

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

The system SHALL insert the TOC-name strategy between the existing `outline` and `numbering` strategies in the cascade, so that a document with a plausible PDF outline still uses `outline` and never reaches the TOC-name strategy. An outline is plausible when, after unusable entries are filtered out, it has at least two entries at its shallowest level; an implausible outline SHALL NOT be used as chapter evidence, and the cascade SHALL continue to the TOC-name strategy as if the document had no outline. The strategy SHALL activate only when the share of plausible body-heading TOC entries matched above the score floor meets a configurable match-rate gate (initial value 60%, a module constant set from the experiment); TOC entries classified as non-heading furniture (abbreviations, glossary, list-of-figures, and the like) SHALL be excluded from the gate's denominator. The strategy SHALL supplement its matched boundaries with legacy-detected **numbered** headings not present in the TOC (excluding running-header lines, deduplicated by boundary; the font strategy is not used for supplementing), and SHALL fall back to the existing cascade (numbering, font, flat) when no usable TOC exists or the match rate is below the gate.

When the TOC-name strategy fires, the document's chapters SHALL be exactly the boundaries it derived from top-level TOC entries. A supplemented numbered heading SHALL be added only as a section (level 2 or deeper), only when it lies in the page span of a TOC chapter, and only when its leading number component equals that chapter's number: the number printed in the TOC, or, for an unnumbered TOC chapter, the leading component shared by its numbered child entries. The span that starts at a matched chapter also belongs to the unmatched TOC chapters listed after it, up to the next matched chapter, because their own headings cannot be placed by page. A supplemented heading that fails any of these SHALL be dropped and recorded as an informational `SupplementHeadingRejected` error; it SHALL NOT become a chapter.

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

- **WHEN** a document's PDF has a plausible outline
- **THEN** the outline strategy is used and the TOC-name strategy is not reached

#### Scenario: Single-entry outline is not chapter evidence

- **GIVEN** a document whose outline, after filtering, is one entry titled `Untitled`
- **WHEN** structure is detected
- **THEN** the outline strategy is not used, the TOC-name strategy is tried next, and the record's `detection_method` names the strategy that actually produced the tree

#### Scenario: Single-root outline is not chapter evidence

- **GIVEN** an outline with one level-1 entry and fifteen level-2 entries beneath it
- **WHEN** structure is detected
- **THEN** the outline is treated as implausible and the cascade continues to the TOC-name strategy

#### Scenario: Missing level signal yields a flat tree

- **WHEN** a TOC has no usable level signal (no indentation, no numbering depth, no size hierarchy)
- **THEN** every entry becomes level 1 (a flat tree), which is the correct structure for flat documents; correctness is guarded by the match-rate gate and `validate_split` rather than a fallback

#### Scenario: Supplemented heading cannot become a chapter

- **GIVEN** a TOC-strategy document whose TOC chapters are numbered 1 to 8, and a numbered body heading `30 [approximately 50kph]` inside chapter 8's page range
- **WHEN** the supplement runs
- **THEN** no node is added for it, and a `SupplementHeadingRejected` error records its text, page and reason

#### Scenario: Supplemented section under its own chapter is kept

- **GIVEN** an unnumbered TOC chapter `Introduction` whose TOC children are numbered `1.1` to `1.5`, and a body heading `1.6 Summary` within its page range that the TOC does not list
- **WHEN** the supplement runs
- **THEN** `1.6 Summary` is added as a level-2 section under `Introduction`

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

### Requirement: Slug and override stability

The system SHALL derive TOC-matched node slugs with the same slugification the existing strategies use (heading number plus title), so a document's published URL segments do not change merely because its detection method moved from `numbering` or `font` to `toc`. The comparison harness SHALL report, per document, which existing slugs a switch to the TOC-name strategy would preserve or change, and any existing `override.json` entry whose slug the switch would orphan.

#### Scenario: Slug preserved across a strategy switch

- **WHEN** the TOC-name strategy produces a node whose title and number match what a legacy strategy produced
- **THEN** the node's slug is identical to the legacy slug

#### Scenario: Orphaned override is surfaced

- **WHEN** adopting the TOC-name strategy would change a slug named by an existing `override.json` entry
- **THEN** the comparison reports the orphaned override for human review before the document is switched

### Requirement: TOC comparison metrics

The system SHALL record, for each document processed with a TOC, the TOC entry count, the matched entry count, and the match rate in the document's output record, and SHALL expose these alongside validate_split issue counts and node counts so the strategies can be compared deterministically on the same documents.

#### Scenario: Metrics recorded when TOC present

- **WHEN** a document is processed and a TOC is detected
- **THEN** its output record includes toc_entry_count, toc_matched_count, and toc_match_rate

#### Scenario: Comparison between strategies

- **WHEN** both the legacy and TOC-name strategies are run on the same document
- **THEN** their validate_split issue counts, node counts, and TOC match rates are reported side by side; a strategy is judged better only with fewer issues AND a node count within a configured factor of the plausible-heading TOC entry count (the over-split signal), and ties or ambiguity are resolved by golden-file review by a human

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

### Requirement: Outline entry normalisation

Before outline entries become nodes, the system SHALL collapse whitespace (including line breaks) in each title before splitting off its heading number. It SHALL merge two adjacent same-level entries on the same page into one entry when the second carries no heading number, the first does not end a sentence, and the joined title matches a heading line on that page. Entries that do not meet all of these conditions SHALL stay separate.

#### Scenario: Multi-line outline title loses its number

- **WHEN** an outline entry is titled `3 Long Term Strategic Issues` + line break + `for National Roads`
- **THEN** the node's number is `3` and its title is `Long Term Strategic Issues for National Roads`

#### Scenario: Wrapped outline fragments are merged

- **GIVEN** adjacent level-1 outline entries `15. Freight, Delivery and` and `Servicing` on page 196, and a heading on page 196 reading `Freight, Delivery and Servicing`
- **WHEN** outline entries are normalised
- **THEN** a single node `Freight, Delivery and Servicing` numbered `15` is produced

#### Scenario: Unverified fragments stay separate

- **WHEN** two adjacent same-page outline entries would join to a title that matches no heading line on that page
- **THEN** both entries are kept unchanged

### Requirement: TOC entry continuation

When the system parses a TOC page, it SHALL join a line that has no heading number onto the entry before it when that entry has no page number yet and the line sits directly below it. The joined entry's page number is the one on its last line, and its indentation is that of its first line. A line that has its own heading number, or that follows an entry that already has a page number, SHALL start a new entry.

#### Scenario: Wrapped TOC entry joined

- **GIVEN** TOC lines `3 Long Term Strategic Issues` (no page number) followed by `for National Roads` with page number `11`
- **WHEN** the TOC is parsed
- **THEN** one entry, `Long Term Strategic Issues for National Roads`, numbered `3` and with printed page `11`, is produced, and no entry is produced for `for National Roads`

#### Scenario: Separate entries stay separate

- **WHEN** two consecutive TOC lines each carry their own page number
- **THEN** they produce two entries

### Requirement: Continuation guards

The system SHALL join continuation lines only within a column that prints page numbers (as defined for unpaged entries), and only when the line is not indented less than the entry before it and is set in the same type size. A line that is a chapter label, or that opens with its own label such as `Goal 7:` or `Chapter 2 –`, SHALL NOT be joined: it is an entry of its own.

#### Scenario: A labelled line is a sibling, not a continuation

- **GIVEN** TOC lines `for all` (no page number) followed by `Goal 7: Design infrastructure …` with page number `28`
- **WHEN** the TOC is parsed
- **THEN** two entries are produced and `Goal 7: …` is not joined onto `for all`

#### Scenario: A TOC without page numbers is not joined

- **WHEN** no line of a contents list carries a page number
- **THEN** every line remains its own entry

### Requirement: TOC chapter labels

The system SHALL read a `Chapter N` label (any case, with an optional `:`, `–`, `-` or `|` separator) as the heading number `N` of a level-1 entry. The label may be on the same line as the title or on its own line directly above it. A body heading printed with the same label SHALL match the TOC entry by its title alone.

#### Scenario: Label on the title line

- **WHEN** a TOC line reads `Chapter 1 – Introduction`
- **THEN** the entry is level 1, numbered `1`, and titled `Introduction`

#### Scenario: Label on its own line

- **WHEN** a TOC line `CHAPTER 2:` is directly followed by `Strategic Vision`
- **THEN** one level-1 entry numbered `2` and titled `Strategic Vision` is produced, and no entry is produced for the label

#### Scenario: Body heading carries the label

- **GIVEN** a TOC entry `Purpose` read from `Chapter 1 | Purpose`, and a body heading printed `Chapter 1 | Purpose`
- **WHEN** the entry is matched
- **THEN** the body heading is its occurrence

### Requirement: Levels from chapter labels

In a TOC with at least two chapter labels, an unnumbered, non-furniture entry after the first label and before the next one SHALL be a level-2 entry of the chapter before it. A label that repeats the previous label's chapter number SHALL be a level-2 entry of that chapter. Entries before the first label, furniture entries, and entries opening with a division label (`Appendix A`, `Annex 2`, `Part B`, `Schedule 1`) SHALL stay level 1.

#### Scenario: Entries between labels are sections

- **GIVEN** a TOC listing `Foreword`, `Summary`, `Chapter 1 – Introduction`, `Purpose of Policy`, `Chapter 2 – Alignment with existing policies`, and finally `List of Abbreviations`
- **WHEN** levels are inferred
- **THEN** `Foreword`, `Summary`, both chapters and `List of Abbreviations` are level 1, and `Purpose of Policy` is level 2 under chapter 1; an `Appendix A | …` entry after the last chapter is level 1

#### Scenario: Repeated chapter number is a section

- **GIVEN** TOC entries `Chapter 4 | Recommendations` and `Chapter 4 | Freight`, then `Chapter 5 | Benefits and Costs`
- **WHEN** levels are inferred
- **THEN** `Recommendations` and `Benefits and Costs` are level 1 and `Freight` is level 2

### Requirement: TOC continuation pages

The system SHALL treat a page as a continuation of the main TOC when it directly follows the last page of the TOC block, has no title of its own or only repeats the contents title, and shows page numbers for at least three entries, either in the right column or as lines of spaced dot leaders ending in a number. Its entries SHALL be parsed as part of the main TOC.

#### Scenario: Untitled second contents page parsed

- **GIVEN** a TOC on page 4 and, on page 5, an untitled page with 22 right-column page numbers under the running header `… | Table of Contents`
- **WHEN** the TOC is parsed
- **THEN** the entries on page 5 are part of the main TOC

#### Scenario: Repeated contents title

- **GIVEN** a TOC on page 3 and, on page 4 directly after it, a small `Contents` title over entries set in spaced dot leaders (`Introduction. . . . . 68`)
- **WHEN** the TOC is parsed
- **THEN** the entries on page 4 are part of the main TOC

### Requirement: Pages that stay out of the TOC

A page SHALL NOT be added to the TOC when it shares a running header with the TOC page and that header does not name the contents, when it opens with a `List of …` title, or when it follows a gap. Such a page remains a part TOC and SHALL NOT be parsed.

#### Scenario: Later part TOC still ignored

- **WHEN** a page with many right-column page numbers sits after the TOC block with other pages in between
- **THEN** it is flagged as a part TOC and contributes no entries

### Requirement: Printed page numbers on TOC entries

The system SHALL record each TOC entry's printed page number when the TOC prints one for that entry, and SHALL record none otherwise. An arabic page number SHALL be kept as an integer. A non-arabic page number, such as a roman numeral, SHALL be kept as printed and SHALL NOT be used to place a boundary.

#### Scenario: Right-column page number recorded

- **WHEN** a TOC entry `Introduction` is followed on its row by the page number `7`
- **THEN** the entry records printed page 7

#### Scenario: Roman page number not used

- **WHEN** a TOC entry's page number is printed as `iii`
- **THEN** the entry records `iii` as printed and is never placed by page number

### Requirement: Paged TOC columns

A column of a TOC prints page numbers when it has at least three entries and half or more of them carry one. Columns SHALL be grouped by left edge in 10-point buckets. A TOC with no such column prints no page numbers.

#### Scenario: A stray page number is not a column

- **WHEN** one entry of an otherwise pageless contents list carries a page number
- **THEN** the TOC has no paged column

### Requirement: Unpaged TOC entries excluded from the gate

When a TOC has a paged column, the system SHALL classify each entry without a page number as unpaged. An unpaged entry SHALL be excluded from the match-rate gate's numerator and denominator. It SHALL still be matched like any other entry: when it matches, it creates a boundary, and when it does not, it is recorded as `TocEntryUnmatched`. A TOC with no paged column has no unpaged entries.

#### Scenario: Side-panel prose does not depress the gate

- **GIVEN** a contents page listing 16 paged chapter entries in one column plus 20 lines of explanatory prose in a side panel column without page numbers
- **WHEN** the match rate is computed
- **THEN** the denominator is the 16 paged entries

#### Scenario: Absent appendices do not depress the gate

- **WHEN** a TOC lists appendices with no page numbers because they are published separately
- **THEN** those entries are excluded from the denominator and logged as unmatched

### Requirement: Pipe-separated heading codes

The system SHALL treat a leading code of two to five uppercase letters or digits, followed by `|`, as the heading's number, whatever whitespace surrounds the `|`. This SHALL apply in the same way to TOC entries, body headings and outline titles, so that `RE |Research and Innovation` and `RE | Research and Innovation` both give number `RE` and title `Research and Innovation`.

#### Scenario: Code prefix matched across TOC and body

- **WHEN** a TOC entry reads `RE |Research and Innovation` and a body heading reads `RE | Research and Innovation`
- **THEN** both normalise to title `Research and Innovation` with number `RE`, and the entry matches the heading

#### Scenario: Ordinary pipe kept

- **WHEN** a title contains `|` after a word that is not an uppercase code, as in `Walking | Cycling`
- **THEN** the title is unchanged

### Requirement: Single detection entry point

The system SHALL expose one detection entry point that takes a document's pages, raw outline and page count. It SHALL perform every outline preparation step (filtering unusable entries, resolving positions, normalising entries) and run the strategy cascade. It SHALL return the tree, the detection method and every problem found. The production step SHALL use this entry point, and so SHALL any evaluation or comparison tool that claims to score production behaviour.

#### Scenario: Same tree in production and evaluation

- **WHEN** the production step and the accuracy report process the same document's pages and outline
- **THEN** they produce identical detected trees before overrides are applied

#### Scenario: Word bookmarks never reach the tree

- **WHEN** a document's raw outline contains `_Hlk…` auto-bookmarks
- **THEN** neither the production tree nor the scored tree contains a node for them, and each dropped entry is reported as a problem
