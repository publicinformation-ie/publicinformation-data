# Proposal

## Why

The chapter-accuracy report from `add-structure-accuracy-eval` gives a baseline of **2 of 10 documents fully correct**, macro exact boundary F1 **0.47** and macro page attribution **0.34**. A per-document diagnosis (gold vs. detected chapters, outline, parsed TOC) traced the eight failures to six fixable causes and one out-of-scope cause (a garbled text layer). The report also has a fidelity gap: it calls `detect_structure()` directly and skips the outline preparation that `process()` runs first (`filter_outline`, `resolve_outline_positions`). The baseline therefore scores a path that production never runs. Its national-roads row counts Word `_Hlk…` bookmarks as chapters, and its GDA row is missing the one-page-early outline correction.

## What Changes

Each item is implemented and measured on its own, against the baseline set by the item before it, so every gain or regression can be attributed to one change.

- **Eval fidelity (first, before any detector change).** Production and the report call one shared entry point that prepares the outline and runs detection. Re-baseline. This change in the numbers is a measurement correction, not a detector gain, and is recorded as such.
- **Held-out gold.** Before any detector work, add four new gold documents, annotated without looking at their detector output, and flag them `held_out`. The report summarises them separately. They are not looked at while the rules are designed, and they are read once at the end to check that the rules generalise.
- **Outline plausibility.** An outline with fewer than two top-level entries after filtering is no longer treated as chapter evidence, and the cascade moves on to the TOC strategy. Targets: `climate-action-plan-2023` (one `Untitled` entry) and `climate-action-plan-2025-annex-of-actions` (one root entry). When adjacent outline entries are wrapped fragments of one heading on the same page, they are merged, but only if the joined title is found on that page (GDA `Freight, Delivery and` / `Servicing`). Outline titles are whitespace-collapsed before their number is split off, so `3 Long Term …\nfor National Roads` loses its `3`.
- **The TOC defines the chapters when the TOC strategy fires.** Numbered headings added by the supplement may only become sections, never chapters. They must sit under a TOC chapter, and their leading number must equal that chapter's number (stated in the TOC, or inferred from its numbered children). Headings that fail this are dropped, and an informational error is logged. Target: national-cycle's 16 junk chapters (`[approximately 50kph]`, route names, the back-cover address).
- **TOC parsing.**
  - Wrapped entries are joined: a line with no number and no page number continues the entry before it when that entry had no page number of its own (national-roads, emra, connecting-ireland).
  - `Chapter N` and `CHAPTER N:` labels are read as a chapter number, on the same line as the title or the line above. This is the evidenced `Chapter N` anchor that `fix-document-structure-corruption` deferred: sustainable-mobility and emra.
  - A page that directly follows the TOC block and has the same page-number column continues the TOC (sustainable-mobility p. 5).
  - Each entry keeps its printed page number. In a mostly paged TOC, an entry with no page number (side-panel prose on the CAP 2025 annex, emra's appendices, which are not in the PDF) is left out of the match-rate gate's denominator.
  - A leading uppercase code followed by `|` (`RE |Research and Innovation`) is read as the heading number, so the TOC and body forms match whatever spacing surrounds the `|`. This is the CAP annex sector-code style.
- **Guarded placement by printed page.** A top-level TOC entry with no body occurrence is placed at its printed page plus an offset, but only when the nearest matched chapters before and after it give the same printed-to-PDF offset. The node gets lower confidence and a `TocEntryPlacedByPageNumber` informational error. Otherwise the entry stays unmatched, as today. Targets: chapters whose titles are artwork (sustainable-mobility, emra).
- **Acceptance.** The exact metrics and their thresholds are in the design. No scored document's raw exact F1 or page attribution may regress unless the regression is explained in the results log. The held-out summary is reported alongside the tuning-set summary, and is not used as a target.

**Non-goals:** decoding or flagging garbled subset-font text layers (`connecting-ireland` gains only from TOC entry continuation), section-level (level ≥ 2) accuracy, a CI gate, and changing how the gold or the metrics are defined.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `document-structure-detection`:
  - **MODIFIED** `Strategy placement and fallback`: outline plausibility; the supplement is confined to sections under a matching TOC chapter.
  - **ADDED** outline entry normalisation (merging wrapped entries, splitting numbers off multi-line titles); TOC entry continuation; TOC chapter labels; TOC continuation pages; printed page numbers on TOC entries; unpaged entries left out of the gate; pipe-separated heading codes; guarded placement by printed page; one shared detection entry point for production and evaluation.
- `document-structure-evaluation`:
  - **ADDED** the report scores the production detection path; held-out gold documents are reported separately; a per-step results log.

## Impact

- Code: `steps/detect_structure/process.py` (the new shared entry point, `from_outline`, `parse_toc`/`_parse_toc_page`, `from_toc`, `_supplement_numbered_nodes`, `detect_structure`) and `eval/score.py`, plus tests in `pipelines/document_pipeline/tests/`.
- Data: four new gold files in `eval/gold/` (manual annotation by the maintainer); `eval/baseline.json` is refreshed at each step, and a new `eval/RESULTS.md` records every step's diff.
- Published trees, and therefore slugs, change for every document whose chapters change, including the 30 documents without gold. Existing `override.json` entries can be orphaned, so the orphaned-override report in `compare.py` must be reviewed before `document_pipeline` output is regenerated. `eval/expected.json` is refreshed.
- Dependency: `fix-document-structure-corruption` is complete but not archived. Archive it first, so the `MODIFIED` requirement here builds on its text.
- No network or paid calls.
