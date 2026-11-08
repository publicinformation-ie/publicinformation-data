# Proposal

## Why

Published document bundles ship corrupt tables of contents: `sustainable-mobility-policy` publishes chapters titled `1`–`6` (bare numerals), the SMP progress reports publish chapters/sections titled `”` (a 70pt pull-quote glyph), and 13 other documents publish TOC lines, page numbers, map glyphs, cover text, and sentence fragments as chapter titles. The artifacts were last built 2026-10-13, before the TOC-name strategy (`342f926d`) landed — and re-detection at current HEAD still yields invalid trees for 10 of 24 documents, including `sustainable-mobility-policy` itself (a `toc` tree with zero level-1 nodes). `validate_split` exists and is tested, but `process()` never calls it, so nothing in the pipeline reports a structurally invalid tree, let alone stops one reaching `public/`.

## What Changes

- **Validation wired into `detect_structure`'s `process()`**: `validate_split()` runs on every tree after `merge_overrides`, and failures are written to `errors.json` as `InvalidStructure` (doc_slug, failing check, offending value). Per the repo's fail-closed-logged rule the record still publishes unaltered — so the *step* does not block. What blocks is this change's own merge criterion: `public/` does not merge to `main` while any document carries an unresolved `InvalidStructure`, resolved either by a code fix or by a committed `override.json` entry (see design D9).
- **`validate_split` gains a level invariant**: a non-empty tree with no level-1 node is invalid. This is the `sustainable-mobility-policy` failure. The invariant is unconditional, *not* conditioned on the tree having more than one level — an all-level-2 tree is a single level, so a conditional check would miss exactly the document that motivated it. A genuinely flat (all level-1) tree stays valid; no synthetic level is invented.
- **TOC pages are excluded from the legacy strategies** (`steps/detect_structure/process.py`): `from_numbering`, `from_font_hierarchy`, and `_supplement_numbered_nodes` currently scan every page, so a TOC line can become a published body heading even under the `toc` method (`build_occurrence_index` excludes TOC pages; the legacy paths do not). This, not title cleanup, is the root fix for the emra / `code-of-practice-recreational-craft` / `national-cycle-network-plan` dot-leader chapters.
- **TOC page parsing robustness**:
  - `page_lines()` returns lines in reading order (y rounded to a named constant, then x) instead of raw extractor span order, so footer page numbers, running headers, and trailing titles no longer interleave wrongly (the root trigger of the SMP pollution chain).
  - `_parse_toc_page()` skips bare-number lines at any x on a flagged TOC page, skips running-header/footer lines, and starts entry collection at the TOC title line. Skipped lines contribute no indentation bucket to `_infer_levels`, which is what pushed all 21 real SMP entries to level 2.
- **Title cleanup, narrowed**: strip leading `|`/`-` fragments, control characters, and *trailing* dot leaders with a glued page number. Interior dot leaders are deliberately **not** stripped — `is_heading_candidate`'s dot-leader rule is the signal that a line is a TOC line, and stripping it first would launder contamination into a title that passes validation.
- **Legacy-cascade guards**: `from_font_hierarchy()` and `from_numbering()` apply the existing `is_heading_candidate` guard and join consecutive same-style lines (up to 2), so bare numerals (`1`–`6`, `2040`, `21`, `l`), quote glyphs (`”`), bullets, cover text, and wrapped-heading fragments stop becoming nodes.
- **Corpus regeneration**: the document pipeline is re-run from `detect_structure` (first re-run since 2026-10-13), regenerated bundles re-audited against the previous run's per-document metrics, and documents that still fail validation get hand-curated `override.json` entries rather than new heuristics.
- **Regression fixtures** for each demonstrated failure (SMP page-4 chain, the quote-glyph page, emra dot-leader page, cover-text and wrapped-title cases).

**Deferred, not included:** a `Chapter N` / `Section N` level-anchoring rule in `_infer_levels`. The SMP and all-island-rail level failures are caused by the polluted indentation bucket, which the TOC-page filtering above removes — once it does, SMP's entries share one left edge and infer a correct flat tree with no anchor rule needed. Adding a textual anchor would change level inference for every TOC document in the corpus to fix a symptom whose cause is already addressed, and it contradicts the existing spec's "missing level signal yields a flat tree" scenario. Task 7.2 re-audits level distributions after regeneration; if a document's only honest level signal really is a `Chapter N` prefix, that becomes its own evidenced change.

**Non-goal:** no heuristic is invented to reconstruct malformed TOCs that no deterministic rule can parse — those fall through to validation logging + `override.json`, per the repo's data-handling principle.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities

- `document-structure-detection`:
  - **MODIFIED** `Deterministic split validation` — adds the level-1 invariant to the existing title/boundary/coverage criteria.
  - **MODIFIED** `Strategy placement and fallback` — detected TOC pages are excluded from the numbering strategy, the font strategy, and the numbered-heading supplement, including when the TOC-name strategy did not fire.
  - **MODIFIED** `TOC-name occurrence-scoring strategy` — "one to three joined consecutive body lines" is pinned to reading-order consecutiveness, which the `page_lines()` sort redefines.
  - **ADDED** reading-order line extraction, TOC-page entry filtering, heading title normalization, the legacy-cascade heading guard, the production validation gate with explicit failure recording, and the post-detection corpus audit.

## Impact

- Code: `pipelines/document_pipeline/steps/detect_structure/process.py` (`page_lines`, `_parse_toc_page`, `_infer_levels` inputs, `from_numbering`, `from_font_hierarchy`, `_supplement_numbered_nodes`, `_legacy_cascade`, `detect_structure`, `validate_split`, `process`) and its tests (`pipelines/document_pipeline/tests/test_detect_structure.py`).
- Code: `pipelines/document_pipeline/steps/detect_structure/eval/compare.py` consumes `validate_split` and will report the new level issue; check its output shape still reads correctly.
- Data: `pipelines/document_pipeline/steps/detect_structure/output.json` + `errors.json`, then the whole downstream chain (`extract_figures`, `clean_text`, `extract_actions`, `extract_action_status`, `assemble_sections`, `publish_bundles`, and `public/documents/**`).
- Published artifacts: `public/documents/**/meta.json`, `full.md`, `llms.txt`, bundles for ~15 of 24 documents (content changes; no schema change — `detection_method` enum unchanged, so the web repo needs no changes).
- Overrides: `steps/detect_structure/override.json` may gain entries for documents that still fail validation after regeneration.
- No pipeline input changes (`documents.yml`, `pipeline.json` untouched). Slug changes are possible where titles change — `override.json` is the mechanism that pins published URLs, and any new `override.json` entries must be committed as source of truth.
