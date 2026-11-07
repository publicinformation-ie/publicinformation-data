# Tasks

## 1. Reading-order line extraction (D3)

- [ ] 1.1 Add page-fixture `pages_two_column.json` (real SMP foreword page 6 raw spans, where raw span order puts footer before header); add the `READING_ORDER_Y_GRID` module constant and implement the `(y0 rounded, x0, block/line)` stable sort in `page_lines()`; verify the fixture asserts header-then-body-then-footer order and that same-baseline lines sort left-to-right — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k reading_order`
- [ ] 1.2 Verify existing strategy tests still pass with the sort in place (no fixture relied on raw span order) — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -q`
- [ ] 1.3 Record each document's current TOC match rate before any other change (from the existing audit/eval output) as the baseline task 7.2 compares against — `PYTHONPATH=".:../../src" python experiments/2026-11-07-structure-corruption-audit/audit.py --head > /tmp/structure-audit-baseline.txt`

## 2. TOC page filtering + entry collection (D5)

- [ ] 2.1 Extend `_parse_toc_page` to skip bare-number lines at any x on a flagged TOC page, skip running-header lines (thread the already-computed running-header set in), and start collection after the `contents` title line in reading order; add `pages_smp_toc.json` fixture (real SMP page 4) asserting no entry from the footer `2` and no entry from the running header — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_filtering`
- [ ] 2.2 Assert the fixture's parsed entries start with `Foreword` and that `Table of contents` produces no entry — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_filtering`
- [ ] 2.3 Assert on the same fixture that the skipped footer line contributes no `x0` bucket: `_infer_levels` returns signal `none` and every entry is level 1 (the SMP all-level-2 failure, fixed at its cause) — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_filtering`

## 3. TOC pages excluded from the legacy strategies (D5b)

- [ ] 3.1 Thread the detected TOC page set from `parse_toc` through `detect_structure` into `_legacy_cascade` and `_supplement_numbered_nodes`, and skip those pages in `from_numbering` and `from_font_hierarchy`; add `pages_emra_toc.json` fixture (real emra page 2) asserting no node is produced from its dot-leader TOC lines — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_page_exclusion`
- [ ] 3.2 Assert the exclusion applies on the fallback path too (TOC detected, match rate below the gate → `numbering`/`font` still skip the TOC pages), since that is where the affected documents actually land — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_page_exclusion`
- [ ] 3.3 Assert `_supplement_numbered_nodes` adds no node from a TOC-page line on a `toc`-method document — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_page_exclusion`

## 4. Title normalization (D6)

- [ ] 4.1 Add a shared title-cleanup (strip leading `|`/`-` fragments, trailing dot leaders with a glued page number, control characters) applied wherever a title or slug source is accepted; fixtures: nifti TOC page (`| Investing in Transport` → `Investing in Transport`), ev-infrastructure matched heading (`\x07` stripped) — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k title_cleanup`
- [ ] 4.2 Assert interior dot leaders are **not** stripped: a line such as `Landscape and Visual ......... 23` reaching the numbering or font strategy is rejected by `is_heading_candidate` and produces no node, rather than being cleaned into a passing title — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k title_cleanup`

## 5. Legacy-cascade heading guard (D7)

- [ ] 5.1 Apply `is_heading_candidate` to every candidate in `from_font_hierarchy` and `from_numbering`; fixture `pages_smp_opener.json` (real SMP page 9) asserts no node titled `1` and that `Introduction` survives — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k cascade_guard`
- [ ] 5.2 Add glyph/numeral/cover-text fixtures (SMP page 28 `”`, action-plan cover `2040`, gda-cycle map glyph `l`) asserting no node is titled by any of them — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k cascade_guard`
- [ ] 5.3 Implement the same-style line join behind a named `HEADING_JOIN_MAX_GAP` constant (≤2 lines, same rounded size + bold class, adjacency within the constant, first line not sentence-ending) with two-directional fixtures: join succeeds on action-plan page 3 (`Safe and Green` + `Mobility` → one node), does not join on SMP page 6's two pull-quote columns — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k cascade_guard`

## 6. Split validation + production wiring (D1, D2)

- [ ] 6.1 Add the level invariant to `validate_split` itself — a non-empty node set with no level-1 node is an issue, unconditionally, with an all-level-1 flat tree valid; unit-test an all-level-2 tree (issue raised), a flat all-level-1 tree (no issue), and confirm the two existing `validate_split` tests still pass unchanged — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k validate_split`
- [ ] 6.2 Wire `validate_split()` into `process()` post-`merge_overrides`, appending `InvalidStructure` entries (doc_slug, failing check, offending value) to `errors.json` without altering the tree, and still writing the record to output; test that a failing document is written *and* flagged — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k validation_gate`
- [ ] 6.3 Confirm `steps/detect_structure/eval/compare.py` still reports correctly now that `validate_split` can return a level issue (its issue counts change for affected documents) — run it on one document and check the output reads sensibly
- [ ] 6.4 Update `steps/detect_structure/README.md`: add `InvalidStructure` to the error table and note that validation always runs in production and that an unresolved entry blocks the merge — `uv run pytest pipelines/document_pipeline/tests -q && uv run pyright`

## 7. Corpus regeneration + audit (D8, D9)

- [ ] 7.1 Re-run the document pipeline from `detect_structure` on this branch — `cd pipelines/document_pipeline && uv run python process.py --from detect_structure --force --stop-on-error` — and confirm zero steps errored and `errors.json` is reviewed
- [ ] 7.2 Re-run the corpus audit and diff it against the 1.3 baseline — `PYTHONPATH=".:../../src" python experiments/2026-11-07-structure-corruption-audit/audit.py --head --published` — confirming (a) every document validates clean or carries an explicit `InvalidStructure`, (b) no document's TOC match rate fell against the baseline, and (c) the level distributions show whether any document still genuinely needs the deferred `Chapter N` anchor (D4); if one does, record it as a follow-up change rather than adding the rule here
- [ ] 7.3 For residual documents (expected: `national-cycle-network-plan` and any emra / recreational-craft stragglers), hand-write `steps/detect_structure/override.json` entries per the D8 decision table, commit them, re-run scoped (`--doc <slug> --force`, paired per AGENTS.md), and confirm the trees validate clean
- [ ] 7.4 Review the regenerated `public/` diff (bundle paths + meta.json chapters), confirm no schema/`detection_method`-enum change, check for orphaned published URLs vs `override.json`, and confirm **zero unresolved `InvalidStructure` entries** (the D1 merge criterion) before merging to `main`

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied (archive applies the delta to `openspec/specs/document-structure-detection/spec.md`, replacing the three MODIFIED requirements in full and appending the ADDED ones).
- Verify the archived result: `openspec validate --strict`, plus one final `--published` audit run against the merged artifact.
