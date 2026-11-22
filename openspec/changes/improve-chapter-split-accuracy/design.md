# Design

## Context

The baseline report on 2026-11-22 (snapshot mode, 10 gold documents) gives raw macro exact F1 0.47 and page attribution 0.34, with 2/10 fully correct. The diagnosis behind this design ran gold, predicted chapters, raw outline and `parse_toc` output side by side for each failing document:

| Document | Method | Root cause | Fix (decision) |
|---|---|---|---|
| `climate-action-plan-2023` | outline | the outline is one `Untitled` entry; the TOC parses with an 86% match rate but is never reached | D3 |
| `climate-action-plan-2025-annex-of-actions` | outline | single-root outline (1 L1, 15 L2); the TOC's `RE \|Title` does not match the body's `RE \| Title`; 20 side-panel prose lines depress the gate | D3, D6, D7 |
| `gda-transport-strategy-2022-2042` | outline | the eval skips `resolve_outline_positions`, so the outline is one page late; wrapped outline fragments; PART A/B and GLOSSARY are not in the outline | D1, D2 (PART/GLOSSARY: residual) |
| `national-roads-2040-final-report` | outline | the eval skips `filter_outline`, so `_Hlk…` bookmarks score as chapters; a newline blocks the number split | D1, D2 |
| `national-cycle-network-plan` | toc | the supplement adds 16 level-1 junk headings (`30 [approximately 50kph]`, route names, the address) | D4 |
| `sustainable-mobility-policy` | toc | p. 5 of the TOC is not detected; `Chapter N –` labels are not parsed, so all entries are level 1; chapter titles are artwork | D5, D8 |
| `emra-regional-spatial-and-economic-strategy` | numbering | `CHAPTER N:` labels on their own line; wrapped entries; artwork titles; unpaged appendices; gate at 43% | D5, D6, D8 |
| `connecting-ireland-rural-mobility-plan` | numbering | garbled subset-font text layer (`%HQH´WV…`); one wrapped entry | D5 only, partial (non-goal) |

Two of these causes are in the eval, not the detector (D1).

Detection behaviour in the main spec reflects `fix-document-structure-corruption` only once that change is archived. It is complete but not archived, so it is archived first (task 0.1).

## Goals / Non-Goals

**Goals:**
- Each decision lands as its own measured step, with a results-log entry, so that any change in the numbers can be traced to one rule.
- Every rule is deterministic and exact-match based, and each one cites a corpus case. A case the rule cannot decide is logged as an error; it is never guessed.

**Non-Goals:**
- Tuning thresholds (`MATCH_RATE_GATE`, `SCORE_FLOOR`) to the gold. Moving a gate to fit 10 documents is the overfitting this change guards against.
- Reconciling the outline with the printed TOC when both exist (GDA's PART A/B). This is a larger design question, left for a later change. GDA keeps its residual error.
- Rewriting published titles, such as stripping `Appendix A`. Title accuracy may stay below 1.0 where gold strips a label the document prints.

## Decisions

### D0. Measurement protocol

The order is: held-out gold first (task group 1), then D1, then D2 to D8, one step per commit. For each step:

1. Implement the rule with unit tests.
2. Run `score.py --baseline eval/baseline.json`. Paste the summaries and per-document diff into `eval/RESULTS.md`, with a reason for each regression.
3. Run `compare.py` on all 40 documents. Record detection-method changes, `InvalidStructure` count changes and orphaned overrides for the 30 documents without gold.
4. Refresh the baseline and commit.

A step that improves no targeted document, or that causes a regression it cannot explain, is reverted, not tuned. The held-out summary is printed every time but is never a design input. If a held-out document regresses, it is investigated only after task group 9.

*Alternative considered:* landing all the rules and measuring once. It was rejected, because then a net gain could hide a rule that hurts.

### D1. One detection entry point

Extract `detect_document_structure(pages, raw_outline, page_count) -> (nodes, method, toc_report, problems)` in `process.py`. It wraps `filter_outline`, `resolve_outline_positions`, the D2 normalisation and `detect_structure`. `process()` uses it and turns `problems` into `errors.json` entries exactly as it does today. `score.detect_document` calls it, which removes the copy that has drifted. A test runs `process()` and `score.score_document` on the same fixture and asserts identical trees.

The baseline change from D1 is recorded in `RESULTS.md` as a **measurement correction**. Expected effect: national-roads loses its 6 `_Hlk` chapters, and GDA's boundaries move one page earlier.

### D2. Outline entry normalisation

- **Number split:** collapse `\s+` to a single space before `_split_number`.
- **Merge wrapped fragments:** consider only adjacent entries at the same level on the same page, where the second has no number and the first does not end in `.`, `!` or `?`. Merge them only when `_find_title_line` finds the joined title on that page, which is the same exact-match rule `resolve_outline_positions` already uses. Matching against the page text is what keeps two real headings that share a page (for example `2.7` and `2.8` on p. 20) apart.

### D3. Outline plausibility

An outline is plausible when, after filtering, its shallowest level has at least 2 entries. Otherwise `detect_structure` moves on as if there were no outline. The method recorded is whichever strategy produced the tree, and a new informational `OutlineNotUsed` error records the reason.

*Alternative considered:* a single-root outline (CAP 2025 annex) could be flattened, promoting the root's children to chapters. This was rejected. It is right for the annex, but wrong for the common document-title wrapper, where the root is the cover rather than a chapter. Falling through to the TOC handles both cases.

### D4. The TOC defines chapters; the supplement only adds sections

In `_supplement_numbered_nodes`, compute each TOC chapter's number. Use the entry's own number. Failing that, use the leading component shared by all its numbered child entries, if they agree. Failing that, the chapter has no number, and nothing can be supplemented under it. A candidate is kept only if its level is 2 or more, and its leading component equals the number of the TOC chapter whose page range contains it. Everything else is dropped with a `SupplementHeadingRejected` error.

The national-cycle check: `4 Public Consultation.` (p. 20) is level 1, so it is dropped. The `30…70 [approximately …]`, route-name and address headings are level 1 in chapter 8's range, so they are dropped.

### D5. TOC parsing: continuation lines, chapter labels, continuation pages

The parsing rules are in the spec. For the code, `_parse_toc_page` must stop discarding bare page numbers. Instead it attaches each one to the entry on the same row (same `y` grid cell, to its right) or, for separate-line layouts, to the entry before it. Continuation joining (spec: TOC entry continuation) depends on this, and so do D6 and D8. All three changes are in task group 5 but are measured as three sub-steps (5a continuation and page capture, 5b chapter labels, 5c continuation pages).

`Chapter N` labels set `level_hint = 1` with `number = N`. `_infer_levels` gains a third signal, `label`, which is tried before `indent` and only when at least two labels are present. The current spec scenario, "Missing level signal yields a flat tree", still holds, because a labelled TOC has a signal.

### D6. Unpaged entries and the gate

Entries are tagged `unpaged` after a TOC is parsed, using the ≥ 50% paged rule in the spec. The gate denominator excludes furniture and unpaged entries. The rule depends only on the TOC's own structure, so it is not a threshold fitted to the gold.

### D7. Pipe-separated codes

The pattern `^([A-Z0-9]{2,5})\s*\|\s*(\S.*)$` is checked in `_split_number` before `NUMBER_PREFIX_RE`. Because the outline, numbering, TOC and occurrence-index paths all go through `_split_number` or the number-prefix alias in `build_occurrence_index`, one change covers all four. Slugs keep the code (`re-research-and-innovation`), following the existing "slug keeps the heading number" rule.

### D8. Guarded placement by printed page

For each unmatched top-level entry with an arabic `printed_page`, find the nearest text-matched top-level entries before and after it that have arabic printed pages. If both exist and `pdf_page - printed_page` is equal for the two, place the entry at `(printed + offset, y = 0)` with `CONFIDENCE["toc_placed"] = 0.5`, and log `TocEntryPlacedByPageNumber`. A placed entry never counts as matched for the gate (spec).

National-cycle's offsets differ between neighbours, because its unnumbered divider pages make the offset grow. There the rule declines to place anything, which is correct: no evidence, no boundary.

*Alternative considered:* a document-wide median offset. It was rejected, because one inserted map would shift every later placement silently. Agreement between neighbours limits any error to the space between two verified anchors.

### D9. Held-out gold

Four documents are annotated with the existing `annotate.py` helper and review page, following `GUIDELINE.md`, and given `"held_out": true`. The candidates are chosen for a spread of detection methods. They are the first four of the following list that have a printed TOC. A document without one goes into `no_toc.json` with its reason, and the next candidate is used.

1. `ev-infrastructure-strategy` (toc)
2. `sustainable-mobility-policy-action-plan-2022-2025` (font)
3. `climate-action-plan-2023-annex-of-actions` (numbering)
4. `national-ports-policy` (outline, 3 levels)
5. `nta-statement-of-strategy-2026-2030` (toc, reserve)
6. `climate-action-plan-2025` (outline, reserve)

The annotator does not run `score.py`, and does not open `detect_structure/output.json`, for these documents before their gold is committed. `gold.py` validates `held_out` as an optional boolean, and `score.py` adds the third summary.

### D10. Acceptance

The change is accepted when all of the following hold:

- (a) Every step's entry is in `RESULTS.md`.
- (b) No tuning or held-out document has an unexplained regression in raw exact F1 or page attribution against the post-D1 baseline.
- (c) Every rule D2 to D8 improves at least one of its target documents (Context table).
- (d) The held-out macro page attribution does not fall below its post-D1 value.
- (e) The `InvalidStructure` count across all 40 documents does not rise.
- (f) The three test suites and pyright pass.

The expected outcomes below are predictions, so that a surprise is visible. They are not targets to tune towards: national-roads and CAP 2024 Q1-Q2 fully correct or title-only misses; CAP 2023 and national-cycle exact F1 ≥ 0.9; sustainable-mobility page attribution ≥ 0.8; emra improved but probably still below the gate.

## Risks / Trade-offs

- [The rules are designed from 10 documents] → The held-out four are read only at the end (D0, D9), and every rule must cite a corpus case and be stated without document-specific constants.
- [Published slugs change for the 30 documents without gold] → `compare.py` lists the slug changes and orphaned overrides at each step. Before `document_pipeline` output is regenerated, orphaned overrides are re-pointed or removed in a reviewed commit (task 9.3).
- [D8 places a chapter on the wrong page when an inserted page sits between two agreeing anchors] → Mitigations: the confidence is lower, every placement is logged, and gold scoring shows the error at once. The error is limited to the span between two verified anchors.
- [D3 sends an implausible-outline document into a TOC or numbering path that is also poor] → The method change is visible in the record and in `RESULTS.md`. If the fall-through tree scores worse than the outline tree on a gold document, the step's acceptance (D0) catches it.
- [Each step's baseline refresh can mask a slow drift] → `RESULTS.md` also carries the post-D1 baseline numbers, and the final entry compares against them as well as against the previous step.

## Migration Plan

Nothing is published by this change on its own. After task group 9, the maintainer regenerates `document_pipeline` from `detect_structure` with `--force --stop-on-error`, reviews the bundle diff and the orphaned overrides, and merges. To roll back, revert the step commits. Each step is self-contained.
