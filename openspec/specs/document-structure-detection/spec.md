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

The system SHALL provide a detection strategy that parses a Table of Contents page to obtain canonical heading entries (title plus inferred level), locates each distinct entry's occurrences in the document body by exact text match of normalized (control-character-stripped, whitespace-collapsed, case-insensitive, punctuation-trimmed) text across one to three joined consecutive body lines — with deterministic number-prefix stripping on the body side, and never fuzzy similarity — scores each occurrence by font rules (heading-like size, monotonic so that larger relative to body size scores higher; boldness; isolation between body-sized text; and exclusion of the TOC page and of running-header lines), and selects the highest-scoring occurrence as the section boundary, recovering start_page, start_y, and the heading number from that occurrence. Distinct TOC entries that share a normalized title (for example a per-chapter "Introduction") SHALL each resolve to their own occurrence rather than collapsing to one boundary. For an occurrence that spans two or three joined body lines, the boundary SHALL record the full vertical span of the heading block so downstream assembly can exclude the whole heading rather than only its first line.

#### Scenario: TOC entry matched to a body heading

- **WHEN** a TOC entry title normalizes to a string that exactly matches a joined run of one to three consecutive body lines, after any configured deterministic number-prefix stripping
- **THEN** that occurrence becomes a candidate boundary with its own start_page and start_y

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

#### Scenario: Usable TOC activates strategy

- **WHEN** a document has a TOC and the match rate meets the configured gate
- **THEN** the TOC-name strategy is used and its detection_method is recorded as `toc`

#### Scenario: Low match rate falls back

- **WHEN** a document has a TOC but the match rate is below the configured gate
- **THEN** the system falls back to the numbering and font strategies and logs a LowTocMatchRate error

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

The system SHALL provide a pure `validate_split(nodes, page_count)` function that returns a list of issue strings, and SHALL consider a split valid only when every node title passes a heading-candidate guard, no two nodes share the same (start_page, start_y) boundary, and the union of node page ranges covers from the first node's start_page through page_count without gaps. Pages before the first node's start page are front matter, not a gap.

#### Scenario: Valid split yields no issues

- **WHEN** a split has real heading titles, unique boundaries, and coverage from its first boundary to the last page
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
