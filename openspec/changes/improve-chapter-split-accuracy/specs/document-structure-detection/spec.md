# Spec Delta

## MODIFIED Requirements

### Requirement: Strategy placement and fallback

The system SHALL insert the TOC-name strategy between the existing `outline` and `numbering` strategies in the cascade, so that a document with a plausible PDF outline still uses `outline` and never reaches the TOC-name strategy. An outline is plausible when, after unusable entries are filtered out, it has at least two entries at its shallowest level; an implausible outline SHALL NOT be used as chapter evidence, and the cascade SHALL continue to the TOC-name strategy as if the document had no outline. The strategy SHALL activate only when the share of plausible body-heading TOC entries matched above the score floor meets a configurable match-rate gate (initial value 60%, a module constant set from the experiment); TOC entries classified as non-heading furniture (abbreviations, glossary, list-of-figures, and the like) SHALL be excluded from the gate's denominator. The strategy SHALL supplement its matched boundaries with legacy-detected **numbered** headings not present in the TOC (excluding running-header lines, deduplicated by boundary; the font strategy is not used for supplementing), and SHALL fall back to the existing cascade (numbering, font, flat) when no usable TOC exists or the match rate is below the gate.

When the TOC-name strategy fires, the document's chapters SHALL be exactly the boundaries it derived from top-level TOC entries. A supplemented numbered heading SHALL be added only as a section (level 2 or deeper), only when it lies within a TOC chapter's page range, and only when its leading number component equals that chapter's number: the number printed in the TOC, or, for an unnumbered TOC chapter, the leading component shared by its numbered child entries. A supplemented heading that fails any of these SHALL be dropped and recorded as an informational `SupplementHeadingRejected` error; it SHALL NOT become a chapter.

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

## ADDED Requirements

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

When the system parses a TOC page, it SHALL join a line that has no heading number and no page number onto the entry before it, provided that entry has no page number of its own and the line is not a chapter label. A joined entry SHALL take its indentation from its first line. A line that carries its own page number SHALL always start a new entry.

#### Scenario: Wrapped TOC entry joined

- **GIVEN** TOC lines `3 Long Term Strategic Issues` (no page number) followed by `for National Roads` with page number `11`
- **WHEN** the TOC is parsed
- **THEN** one entry, `Long Term Strategic Issues for National Roads`, numbered `3` and with printed page `11`, is produced, and no entry is produced for `for National Roads`

#### Scenario: Separate entries stay separate

- **WHEN** two consecutive TOC lines each carry their own page number
- **THEN** they produce two entries

### Requirement: TOC chapter labels

The system SHALL read a `Chapter N` label (any case, with an optional `:`, `–` or `-` separator) as the heading number `N` of a level-1 entry. The label may be on the same line as the title or on its own line directly above it. In a TOC that has chapter labels, an unnumbered, non-furniture entry after the first labelled chapter and before the next one SHALL be a level-2 entry of the chapter before it. Entries before the first label and furniture entries SHALL stay level 1.

#### Scenario: Label on the title line

- **WHEN** a TOC line reads `Chapter 1 – Introduction`
- **THEN** the entry is level 1, numbered `1`, and titled `Introduction`

#### Scenario: Label on its own line

- **WHEN** a TOC line `CHAPTER 2:` is directly followed by `Strategic Vision`
- **THEN** one level-1 entry numbered `2` and titled `Strategic Vision` is produced, and no entry is produced for the label

#### Scenario: Entries between labels are sections

- **GIVEN** a TOC listing `Foreword`, `Summary`, `Chapter 1 – Introduction`, `Purpose of Policy`, `Chapter 2 – Alignment with existing policies`, and finally `List of Abbreviations`
- **WHEN** levels are inferred
- **THEN** `Foreword`, `Summary`, both chapters and `List of Abbreviations` are level 1, and `Purpose of Policy` is level 2 under chapter 1

### Requirement: TOC continuation pages

The system SHALL treat a page as a continuation of the main TOC when it directly follows the last page of the TOC block, has no title of its own, and has at least three right-column page numbers, and when the running header it shares with the TOC page (if any) names the contents. Its entries SHALL be parsed as part of the main TOC. A page that meets these conditions but follows a gap SHALL remain a part TOC and SHALL NOT be parsed.

#### Scenario: Untitled second contents page parsed

- **GIVEN** a TOC on page 4 and, on page 5, an untitled page with 22 right-column page numbers under the running header `… | Table of Contents`
- **WHEN** the TOC is parsed
- **THEN** the entries on page 5 are part of the main TOC

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

### Requirement: Unpaged TOC entries excluded from the gate

When at least half of a TOC's entries carry a printed page number, the system SHALL classify each entry without one as unpaged. An unpaged entry SHALL be excluded from the match-rate gate's denominator. It SHALL still be matched like any other entry. When it matches, it creates a boundary. When it does not, it is recorded as `TocEntryUnmatched`.

#### Scenario: Side-panel prose does not depress the gate

- **GIVEN** a contents page listing 16 paged chapter entries plus 20 lines of explanatory prose in a side panel without page numbers
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

### Requirement: Guarded placement by printed page

The system SHALL place a top-level TOC entry that has no body occurrence and an arabic printed page at the top of PDF page `printed + offset`, but only when the nearest text-matched top-level entries before and after it share that offset. A placement SHALL be logged as `TocEntryPlacedByPageNumber`, SHALL carry lower confidence, and SHALL NOT count towards the gate. Otherwise the entry stays unmatched.

#### Scenario: Artwork chapter placed

- **GIVEN** TOC chapters at printed pages 4, 7 and 17, where the chapters at printed 4 and 17 matched body headings on PDF pages 6 and 19, and the chapter at printed 7 has no body occurrence
- **WHEN** the TOC strategy runs
- **THEN** that chapter starts at the top of PDF page 9, carries placement confidence, and a `TocEntryPlacedByPageNumber` error names it, its printed page and the offset 2

#### Scenario: Disagreeing neighbours prevent placement

- **WHEN** the matched chapters either side of an unmatched chapter have offsets 11 and 13
- **THEN** no boundary is created and the entry is recorded as `TocEntryUnmatched`

#### Scenario: No neighbour on one side

- **WHEN** an unmatched chapter is the first or last top-level entry, so it has a matched neighbour on one side only
- **THEN** no boundary is created and the entry is recorded as `TocEntryUnmatched`

#### Scenario: Placement does not open the gate

- **WHEN** a TOC's text-matched share is below the match-rate gate, but would meet it if placed entries were counted
- **THEN** the TOC-name strategy does not fire, and `LowTocMatchRate` is logged

### Requirement: Single detection entry point

The system SHALL expose one detection entry point that takes a document's pages, raw outline and page count. It SHALL perform every outline preparation step (filtering unusable entries, resolving positions, normalising entries) and run the strategy cascade. It SHALL return the tree, the detection method and every problem found. The production step SHALL use this entry point, and so SHALL any evaluation or comparison tool that claims to score production behaviour.

#### Scenario: Same tree in production and evaluation

- **WHEN** the production step and the accuracy report process the same document's pages and outline
- **THEN** they produce identical detected trees before overrides are applied

#### Scenario: Word bookmarks never reach the tree

- **WHEN** a document's raw outline contains `_Hlk…` auto-bookmarks
- **THEN** neither the production tree nor the scored tree contains a node for them, and each dropped entry is reported as a problem
