# Proposal

## Why

Published document bundles ship corrupt tables of contents: `sustainable-mobility-policy` publishes chapters titled `1`–`6` (bare numerals), the SMP progress reports publish chapters/sections titled `”` (a 70pt pull-quote glyph), and 13 other documents publish TOC lines, page numbers, map glyphs, cover text, and sentence fragments as chapter titles. The artifacts were last built 2026-10-13, before the TOC-name strategy (`342f926d`) landed — and re-detection at current HEAD still yields invalid trees for 10 of 24 documents, including `sustainable-mobility-policy` itself (a `toc` tree with zero level-1 nodes). Nothing in the pipeline currently stops a structurally invalid tree from publishing.

## What Changes

- **Structural validation gate in `detect_structure`**: `process()` now runs `validate_split()` plus a level invariant (≥1 level-1 node when multiple levels exist, every title passes `is_heading_candidate`) on every detected tree, and writes `InvalidStructure` entries to `errors.json` — a corrupt tree can never publish silently (it still publishes, matching the repo's fail-closed-logged rule).
- **TOC page parsing robustness** (`steps/detect_structure/process.py`):
  - `page_lines()` returns lines in reading order (page, y, then x) instead of raw extractor span order, so footer page numbers, running headers, and trailing titles no longer interleave wrongly (the root trigger of the SMP pollution chain).
  - `_parse_toc_page()` skips bare-number lines at any x on a flagged TOC page, skips running-header/footer lines, and starts entry collection at the TOC title line.
  - `_infer_levels()` gains a deterministic rule: an entry titled `Chapter N …` / `Section N:` / `Part N` anchors level 1, with following entries level 2 until the next anchor.
- **Title cleanup**: number/title splitting and TOC suffix stripping remove leading `|` pipes and control characters, and dot-leader/page-number suffixes, so titles like `| Investing in Transport`, `- Moving`, and `Landscape and Visual .........` cannot survive into slugs.
- **Legacy-cascade guards**: `from_font_hierarchy()` and `from_numbering()` apply the existing `is_heading_candidate` guard and join consecutive same-style lines (up to 2), so bare numerals (`1`–`6`, `2040`, `21`, `l`), quote glyphs (`”`), bullets, dot-leader lines, cover text, and wrapped-heading fragments stop becoming nodes.
- **Corpus regeneration**: the document pipeline is re-run from `detect_structure` (first re-run since 2026-10-13), regenerated bundles re-audited, and documents that still fail validation get hand-curated `override.json` entries rather than new heuristics.
- **Regression fixtures** for each demonstrated failure (SMP page-4 chain, the quote-glyph page, emra dot-leader page, cover-text and wrapped-title cases).

**Non-goal:** no heuristic is invented to reconstruct malformed TOCs that no deterministic rule can parse — those fall through to validation logging + `override.json`, per the repo's data-handling principle.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities

- `document-structure-detection`: adds a publish-gating structural-validation requirement (validate + level invariant + error logging in production, not only in tests), extends the TOC parse requirements for reading-order lines / TOC-page edge shapes / `Chapter N`-anchored level inference / title cleanup, and extends the legacy-cascade requirement with the heading-candidate guard and wrapped-line joining.

## Impact

- Code: `pipelines/document_pipeline/steps/detect_structure/process.py` (the five functions above), its tests (`tests/test_detect_structure.py`), and `pipelines/document_pipeline/tests/test_detect_structure.py`.
- Data: `pipelines/document_pipeline/steps/detect_structure/output.json` + `errors.json`, then the whole downstream chain (`extract_figures`, `clean_text`, `extract_actions`, `extract_action_status`, `assemble_sections`, `publish_bundles`, and `public/documents/**`).
- Published artifacts: `public/documents/**/meta.json`, `full.md`, `llms.txt`, bundles for ~15 of 24 documents (content changes; no schema change — `detection_method` enum unchanged, so the web repo needs no changes).
- Overrides: `steps/detect_structure/override.json` may gain entries for documents that still fail validation after regeneration.
- No pipeline input changes (`documents.yml`, `pipeline.json` untouched). Slug changes are possible where titles change — `override.json` is the mechanism that pins published URLs, and any new `override.json` entries must be committed as source of truth.
