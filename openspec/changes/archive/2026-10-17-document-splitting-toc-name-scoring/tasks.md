## 0. Experiment (refinement gate — precedes all implementation)

- [x] 0.1 Create `pipelines/document_pipeline/experiments/README.md` (index) and `pipelines/document_pipeline/experiments/2026-10-17-toc-splitting-comparison/` with a README (hypothesis) and a read-only `run.py` prototype, following the foi/cso experiments convention; add the `experiments/**/results/` gitignore rule for document_pipeline
- [x] 0.2 Prototype `parse_toc`, occurrence matching (exact; exact with number-prefix tolerance), and scoring; run the prototype plus the legacy cascade over all 24 documents' cached `extract_pages` pages; touch no pipeline outputs
- [x] 0.3 Record per-document results in the experiment README: TOC detection outcome/signal, entry shapes (separate-line numbers, right-hand page numbers, Unicode dot leaders, multi-TOC), non-heading furniture share, repeated-title rate, match rates per rule (over all entries and over plausible body-heading entries), level signals, running-header interference, issue counts, node counts, and slug/override preservation for both strategies
- [x] 0.4 Review results; refine this change's design/spec thresholds (matching rule, gate, TOC-page detection, multi-TOC handling, level inference, score floor, `toc` confidence) — the implementation sections below start only after this

## 1. Helpers and guards

- [x] 1.1 Implement `normalize_heading_text` (lowercase, collapse whitespace, strip trailing punctuation/dots including Unicode `…`)
- [x] 1.2 Implement `is_heading_candidate` guard (letters, length, no dot leaders, no bullets, no currency-first)
- [x] 1.3 Implement `running_header_texts` (lines appearing on >=25% of pages), used to exclude occurrences and supplement nodes
- [x] 1.4 Implement `validate_split(nodes, page_count)` with heading, uniqueness, and first-boundary-to-last-page coverage checks

## 2. TOC parsing and occurrence scoring

- [x] 2.1 Implement `parse_toc(pages)` returning `{title, level}` entries and classifying non-heading furniture (abbreviations, glossary, list-of-figures) for the match-rate denominator, handling the entry shapes the experiment documented
- [x] 2.2 Implement `find_occurrences(pages, toc_title)` joining k=1..3 lines, using the matching rule refined from the experiment, resolved per distinct TOC entry
- [x] 2.3 Implement `score_occurrence(line, body, on_toc_page)` with a monotonic size term (larger scores higher), boldness/isolation bonuses, TOC-page penalty, and running-header exclusion
- [x] 2.4 Implement `from_toc(pages, body)` building nodes per distinct TOC entry (repeated titles resolve separately), recovering `number` via `_split_number` and the full vertical span for joined headings, with the refined score floor and `toc` confidence constant

## 3. Cascade integration

- [x] 3.1 Insert `from_toc` between `outline` and `numbering` in `detect_structure`
- [x] 3.2 Add supplement rule (legacy nodes not in the TOC set, dedup by (page, y), running headers excluded)
- [x] 3.3 Add the match-rate gate (refined value, computed over plausible body-heading entries) with `LowTocMatchRate` fallback; log `TocEntryUnmatched` / `TocEntryNoHeading` to errors.json
- [x] 3.4 Record TOC metrics (entry count, matched count, match rate) in output records
- [x] 3.5 Check downstream consumers of `detection_method` (web-repo badges, `public/documents/*/meta.json`, `index.json`) handle the new `toc` value
- [x] 3.6 Bump `publish_bundles`' `CONTRACT_VERSION` to 1.2.0 and add a `public/CHANGELOG.md` entry for the new `toc` `detection_method` value

## 4. Tests and comparison

- [x] 4.1 Add unit tests for `parse_toc`, `find_occurrences`, `score_occurrence`, `validate_split` (hand-written page fixtures, millisecond-fast, per the module's test identity)
- [x] 4.2 Commit a frozen, LFS-backed corpus snapshot (mirroring foi's `eval/input.json`) so the comparison test is reproducible in CI; add a comparison regression test reporting issue counts, node counts, match rates, and slug preservation per document for both strategies
- [x] 4.3 Run full suite; regenerate golden files only where splits improve, with review

## 5. Documentation

- [x] 5.1 Update `steps/detect_structure/README.md` with the new strategy, thresholds, and metrics; note the new `toc` value and the contract version bump wherever `detection_method` is documented (including `assemble_sections` and `publish_bundles`)
