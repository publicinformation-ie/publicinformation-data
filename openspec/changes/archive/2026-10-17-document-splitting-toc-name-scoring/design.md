## Context

Current detection lives in `pipelines/document_pipeline/steps/detect_structure/process.py`. The cascade is `outline` → `numbering` → `font` → `flat`, with tree assembly (`dedupe_slugs`, `assign_hierarchy`, `assign_page_ranges`) shared. `assemble_sections` consumes the resulting nodes as `(page, y)` boundaries and passes `detection_method` through to published output. The legacy font strategy promotes any line whose size is in the top-3 distinct sizes above body+0.5pt, with only a length guard, which is the source of most wrong splits. See proposal.md for motivation and corpus evidence.

## Goals / Non-Goals

**Goals:**
- Settle the empirical unknowns (match rates, entry shapes, thresholds) with a read-only experiment before implementation, and refine this change from its results.
- Add a TOC-name occurrence-scoring strategy that uses canonical TOC titles as an allow-list and font rules only as a disambiguator, recovering `start_y` from the body.
- Keep the existing cascade as fallback and supplement, so recall is not lost.
- Add deterministic `validate_split` and TOC metrics, plus a side-by-side comparison, to make "better" measurable.

**Non-Goals:**
- Replacing the PDF `outline` strategy (it stays first, confidence 1.0).
- Changing the `assemble_sections` contract, frontmatter keys, or published bundle shape.
- Automatic golden-file regeneration (handled as a deliberate review step).
- Fuzzy or reconstructed matching of TOC entries to body text: matching is exact after normalization plus deterministic number-prefix stripping (required — the experiment showed exact equality alone fails the gate). Anything that cannot be matched confidently is logged, not guessed (repo fail-closed principle).

## Decisions

0. **Experiment first (refinement gate).** The uncertainty in this change is empirical, so it is settled by a dated, read-only experiment in `pipelines/document_pipeline/experiments/2026-10-17-toc-splitting-comparison/` (following `pipelines/foi_pipeline/experiments/README.md`): prototype `parse_toc`, occurrence matching under candidate rules, and scoring; run both the prototype and the legacy cascade over every document's cached `extract_pages` pages; record per-document results in the experiment's README (hypothesis → results → conclusion). The experiment writes only its own results; it never touches pipeline outputs. **Run 2026-10-17 — results recorded in the experiment README and summarised in "Experiment findings" below.**

1. **TOC page detection**: a page is a TOC page if it contains a line whose normalized text is `contents` or `table of contents` at a heading-like size (≥ body + 0.5), or a line with ≥3 dot-leader lines, or a title line plus ≥3 right-hand page-number lines (far-right bare numbers). Only the **first contiguous block** of TOC pages is parsed; `list-of-*` pages and later part-TOCs are flagged (`multi_toc` / `part_tocs`) but contribute no entries, so a multi-part document does not over-split. TOC title extraction strips trailing dot leaders (ASCII `....` and Unicode `…`), trailing page numbers, and control characters (`\x00`–`\x1f`, `\x7f`). Level is inferred from numbering depth where ≥2 numbered entries have depth > 1, else from indentation (`x0`), else all entries are level 1. A missing level signal is **not** a fallback trigger: a flat tree is the correct structure for a flat document (e.g. `gda-cycle-network-plan-2022`'s 21 town sections), and correctness is guarded by the match-rate gate and `validate_split` instead.

2. **Occurrence search**: normalize both TOC entry and body lines (strip control characters, lowercase, collapse whitespace — which folds thin spaces like U+2009 — and strip trailing punctuation/dots/`…`). Join k=1..3 consecutive body lines and compare for exact equality. **The experiment shows exact equality alone fails the gate; deterministic stripping of a leading number prefix from the joined body text (`NUMBER_PREFIX_RE`, the same split `from_numbering` uses) is required** — still exact equality, never fuzzy similarity. Occurrences are resolved per distinct TOC entry, not per normalized title, so a repeated title (per-chapter "Introduction") yields one boundary per entry. The heading `number` is recovered from the body occurrence via `_split_number`, not from the TOC title, so slugs stay stable across the switch. For a k=2..3 joined occurrence, record the full vertical span of the heading block (not just the first line's y0) so `assemble_sections`' own-heading exclusion covers the whole heading. Unmatched entries are logged as `TocEntryUnmatched`; entries that match but are not heading-like are logged as `TocEntryNoHeading`; nothing is reconstructed.

3. **Scoring**: a score rewards heading-like presentation monotonically — larger size relative to body scores higher (do not add the level index, which would reward smaller headings) — plus bonuses for boldness and isolation between body-sized text. Occurrences on the TOC page and on running-header lines (text appearing on ≥25% of pages, `RUNNING_HEADER_FRACTION = 0.25`) are **excluded** from candidates, so they can never be selected. Select `max`; tie-break by earliest `(page, y)`. Reject an entry if its best occurrence is below the floor. **Score floor** (`SCORE_FLOOR`): an occurrence must be above body size or bold — the same guard `from_numbering` uses to keep prose out (`size ≥ body * 1.05` or bold) — so an in-text mention at body size cannot become a boundary.

4. **Supplement & fallback**: start with TOC-matched boundaries; add legacy **numbered** headings whose normalized title is not in the TOC set (deduplicated by `(page, y)`), excluding running-header lines. The `font` strategy is deliberately **not** used for supplementing — it is the low-precision over-splitter this change replaces, and the experiment shows re-adding its nodes reintroduces the junk. The match-rate gate (60%, `MATCH_RATE_GATE`, a module constant) is computed over plausible body-heading entries — non-heading furniture entries are excluded from the denominator. If the match rate is below the gate, discard TOC boundaries and use the legacy cascade, logging `LowTocMatchRate`. If no TOC page is detected, use the legacy cascade unchanged. A document with a PDF outline never reaches this strategy: `outline` still wins.

5. **Validation**: `validate_split(nodes, page_count)` checks heading-candidate titles, unique boundaries, and page coverage measured from the first node's `start_page` to the last page — front matter before the first heading is not a gap. Rationale: 19 of 24 current documents (including trusted `outline` ones) start their first node after page 1; requiring coverage from page 1 would flag every good existing split and would perversely favour the legacy font strategy, whose junk promotion of big cover-page text covers pages 1–2.

6. **Comparison and acceptance**: a regression harness reports, per document, validate_split issue counts, node counts, TOC match rates, and slug preservation for both strategies. Acceptance is not "fewer issues wins" alone: issue counts measure validity, not accuracy (a 201-node over-split and a 24-node correct split can both validate clean). The verdict combines (a) fewer issues, (b) node count within a configured factor of the plausible-heading TOC entry count (the over-split signal — the motivating problem), (c) no orphaning of existing slugs/overrides, and (d) golden-file diff review by a human.

7. **Published-contract details**: `detection_method: "toc"` flows into `public/documents/*/meta.json` and `index.json`. Adding a `detection_method` value is a MINOR bump of the bundle contract per `publish_bundles`' own SemVer note — bump `CONTRACT_VERSION` from 1.1.0 to 1.2.0, add a `public/CHANGELOG.md` entry, and check downstream consumers (web-repo schema/badges) before release. Per-node `confidence` for `toc` is `0.95` (between `numbering` 0.9 and `outline` 1.0). Error taxonomy: `LowTocMatchRate`, `TocEntryUnmatched`, and `TocEntryNoHeading` all go to `errors.json` for triage.

Alternatives considered: pure TOC-driven splitting (rejected: loses y, offset problems, under-splits); TOC as allow-list filter on font detection (viable but keeps dependency on font recall; the chosen approach is strictly stronger and subsumes it); fuzzy matching of TOC entries to body text (rejected: violates the fail-closed principle — log, don't guess).

## Risks / Trade-offs

- [Exact match rate too low on real TOCs] → the experiment measures it first; if no candidate matching rule clears the gate, the change is reconsidered before any production code is written.
- [Slug/override instability] → the comparison reports per-document slug preservation; a document is switched to `toc` only if its existing slugs (and any `override.json` entries keyed on them) are preserved, or after a human re-maps the orphaned overrides.
- [Repeated TOC titles collapse to one boundary] → occurrences are keyed per distinct TOC entry, and the repeated-title rate is measured in the experiment.
- [Multi-line heading mismatch] → k=1..3 line joining; measured by the experiment.
- [Under-splitting on incomplete TOCs] → supplement rule and match-rate gate.
- [TOC entries that are not body headings] → score floor and `TocEntryNoHeading` logging.
- [Level signal absent on a flat document] → all entries become level 1, which the experiment showed is the *correct* structure for flat documents like `gda-cycle-network-plan-2022`; correctness is guarded by the match-rate gate and `validate_split`, not by a fallback.
- [Golden-file churn] → regenerate only where splits improve and review diffs.
- [Scoring threshold tuning] → floor and gate are module constants, set from experiment results, adjustable without spec change.

## Migration Plan

1. Write and run the experiment; commit its README (hypothesis/results/conclusion); result tables are regenerable and stay out of git.
2. Refine this change's spec/design thresholds from the results (refinement gate).
3. Implement helpers (`normalize_heading_text`, `is_heading_candidate`, `running_header_texts`, `parse_toc`, `find_occurrences`, `score_occurrence`, `validate_split`).
4. Implement `from_toc` and wire into the `detect_structure` cascade with supplement/fallback; record TOC metrics.
5. Commit a frozen, LFS-backed corpus snapshot (mirroring foi's `eval/input.json`) so the comparison regression test is reproducible in CI; add the comparison regression test and regenerate golden files where improved.
6. Bump `publish_bundles`' `CONTRACT_VERSION` to 1.2.0 (MINOR: new `detection_method` value) and add a `public/CHANGELOG.md` entry; coordinate the new `toc` value with the web repo.
7. Rollback: revert to legacy cascade by removing `from_toc` from the cascade order (single-line change); no data migration needed.

## Experiment findings (2026-10-17)

Run over all 24 documents' cached `extract_pages` output. Summary of the
questions decision 0 posed, all now answered:

- **TOC detection**: 21 of 24 documents detected a TOC page. The three signals
  together cover the corpus's edge cases — the right-hand page-number column
  detects `sustainable-mobility-policy` (whose `Table of Contents` title is a
  body-size running header); dot-leader density detects `gda-cycle-network-plan`.
- **Entry shapes**: right-hand page-number columns (no dot leaders) are the
  most common (18 of 21 TOC documents); separate-line numbers, ASCII and
  Unicode `…` dot leaders, and multi-page/multi-TOC documents all occur.
  `code-of-practice-fishing-vessels` is a single TOC spanning 6 pages (167
  clause entries); `national-cycle-network-plan` has 8 TOC pages (part-TOCs).
  Parsing all TOC pages over-splits (`national-cycle-network-plan` 59→158
  nodes), so only the first contiguous block is parsed.
- **Matching rule**: exact equality alone fails the gate (e.g.
  `national-investment-framework` 12%); number-tolerant matching clears it
  (81%). **Required.**
- **Repeated-title rate**: repeated titles on 12 documents (up to 7), so
  per-distinct-entry resolution is required.
- **Level signals**: numbering depth on 10, indentation on 11, none on 1
  (`gda-cycle-network-plan-2022`, flat and correct).
- **Running headers**: up to 41 per document; ≥25%-of-pages exclusion is needed.
- **Supplement**: numbering-only (not font) — re-adding font nodes reintroduces
  the over-split.
- **Outcome**: the strategy turns `gda-cycle-network-plan-2022` from 201 font
  nodes to 21 nodes with 0 `validate_split` issues, and clears the 60% gate on
  the documents that benefit most. See the experiment README for the full
  per-document table.

## Open Questions

None — all open questions in decision 0 were settled by the 2026-10-17
experiment and recorded above (and in the experiment README) as module
constants and detection rules. The match-rate gate (60%) and score floor
(relative size ≥ 1.0 or bold) are module constants and may be tuned later
without a spec change.
