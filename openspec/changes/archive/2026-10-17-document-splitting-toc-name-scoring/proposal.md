## Why

The document pipeline splits PDFs into sections using detected headings. The current cascade (PDF outline → numbered headings → font-size hierarchy → flat fallback) frequently produces wrong splits: font-based detection promotes non-headings (quote marks, page numbers, currency figures, bullets, glossary entries, running headers), and numbered-heading detection absorbs Table-of-Contents entries with dot leaders. These bad boundaries are visible in `detect_structure/output.json` and in `assemble_sections` coverage, but only after the fact. A more accurate, deterministic strategy is needed, and a measurable way to prove it is better.

Corpus evidence (24 documents): 9 use the `font` method (the worst case, `gda-cycle-network-plan-2022`, has 201 nodes), 8 `numbering`, 7 `outline`; 21 of 24 have a `Contents`/`Table of Contents` title line. The TOC is therefore a viable allow-list signal for most documents — but the real TOC pages show entry shapes (numbers on separate lines, right-hand page-number columns, Unicode dot leaders, multiple TOCs per document) whose effect on match rate is an empirical question, not a design guess.

## What Changes

- Run a small, deterministic experiment first, following the repo's experiments convention (`pipelines/foi_pipeline/experiments/README.md`): a dated, read-only prototype under `pipelines/document_pipeline/experiments/` that parses each document's TOC, locates TOC titles in the body under candidate matching rules (exact normalized; exact with number-prefix tolerance), scores occurrences, and runs both the prototype and the legacy cascade over all documents' cached `extract_pages` output. Its README records hypothesis, per-document results, and conclusion; no pipeline output is modified.
- Refine this change's spec and design from the experiment results — matching rule, match-rate gate, TOC-page detection rules, multi-TOC handling, level inference, score floor — before implementation tasks start. Implementation is gated on that refinement.
- Add a new `from_toc` detection strategy to `pipelines/document_pipeline/steps/detect_structure/process.py`, inserted between `outline` and `numbering` in the cascade: canonical heading entries from the TOC, best-scoring body occurrence per distinct entry (font rules as disambiguator only), `start_y` recovered from the body occurrence. Nodes reuse the existing slug derivation (number + title) so published URL segments do not change when a document moves from `numbering`/`font` to `toc`.
- Supplement TOC-matched boundaries with legacy-detected headings not present in the TOC, and fall back to the existing cascade when no usable TOC exists or the match rate is below the gate.
- Add a deterministic `validate_split(nodes, page_count)` — coverage measured from the first boundary to the last page, front matter is not a gap — plus TOC metrics, and a regression comparison harness so old and new algorithms can be compared per document after implementation.

## Capabilities

### New Capabilities

- `document-structure-detection`: heading detection, tree assembly, split validation, and a deterministic comparison experiment for the document pipeline, including the TOC-name occurrence-scoring strategy and deterministic comparison against the legacy cascade.

### Modified Capabilities

<!-- none -->

## Impact

- Affected code: `pipelines/document_pipeline/steps/detect_structure/process.py` (new strategy, helpers, validation), its tests (`tests/test_detect_structure.py`), `publish_bundles/process.py` (contract version bump), and possibly `assemble_sections` (unchanged contract).
- New experiments directory `pipelines/document_pipeline/experiments/2026-10-17-toc-splitting-comparison/` (read-only prototype; results regenerable and not committed, per the foi/cso experiments convention), plus a frozen, LFS-backed corpus snapshot so the comparison regression test is reproducible in CI.
- `detection_method` gains a new published value `toc` (it flows into `public/documents/*/meta.json` and `index.json`). This is a MINOR bump of the bundle contract (`CONTRACT_VERSION` 1.1.0 → 1.2.0) per `publish_bundles`' own SemVer note, plus a `public/CHANGELOG.md` entry — downstream consumers (web-repo schema/badges) must be checked before release.
- Frontmatter keys are unchanged, but a strategy switch can change node slugs (published URL segments) and orphan existing `override.json` entries; slug preservation is reported per document and a document is only switched when its slugs/overrides are preserved or re-mapped.
- Golden Markdown may be regenerated where splits improve, with review.
