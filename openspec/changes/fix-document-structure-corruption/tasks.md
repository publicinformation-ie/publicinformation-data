# Tasks

## 1. Reading-order line extraction (D3)

- [ ] 1.1 Add page-fixture `pages_two_column.json` (real SMP foreword page 6 raw spans, where raw span order puts footer before header); implement y-then-x stable sort in `page_lines()` and verify the fixture asserts header-then-body-then-footer order — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k reading_order`
- [ ] 1.2 Verify existing strategy tests still pass with the sort in place (no fixture relied on raw span order) — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -q`

## 2. TOC page filtering + entry collection (D5)

- [ ] 2.1 Extend `_parse_toc_page` to skip bare-number lines at any x on a flagged TOC page, skip running-header lines (thread the already-computed running-header set in), and start collection after the `contents` title line in reading order; add `pages_smp_toc.json` fixture (real SMP page 4) asserting no entry from the footer `2` and no entry from the running header — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_filtering`
- [ ] 2.2 Assert the fixture's parsed entries start with `Foreword` and that `Table of contents` produces no entry — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k toc_filtering`

## 3. Structural level anchoring (D4)

- [ ] 3.1 Add the `^(chapter|section|part)\s+\d` anchor rule to `_infer_levels` (anchored → level 1, following entries → level 2 until next anchor; explicit `1.1`-depth still wins) and assert on the `pages_smp_toc.json` fixture that `Chapter 1 – Introduction` is level 1 with `Purpose of Policy` at level 2 — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k level_anchor`
- [ ] 3.2 Add a case asserting the no-prefix fallback is unchanged (existing `pages_toc.json`-style fixture still infers levels exactly as before) — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k level_anchor`

## 4. Title normalization (D6)

- [ ] 4.1 Add a shared title-cleanup (strip leading `|`/`-` fragments, dot leaders + trailing numbers, interior control chars) applied wherever a title or slug source is accepted; fixtures: nifti TOC page (`| Investing in Transport` → `Investing in Transport`), ev-infrastructure matched heading (`\x07` stripped) — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k title_cleanup`
- [ ] 4.2 Assert dot-leader lines resolve to either the clean title or a rejected candidate, and that `is_heading_candidate` remains the final accept/reject call — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k title_cleanup`

## 5. Legacy-cascade heading guard (D7)

- [ ] 5.1 Apply `is_heading_candidate` to every candidate in `from_font_hierarchy` and `from_numbering`; fixture `pages_smp_opener.json` (real SMP page 9) asserts no node titled `1` and that `Introduction` survives — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k cascade_guard`
- [ ] 5.2 Add glyph/numeral/coverage fixtures (SMP page 28 `”`, action-plan cover `2040`, gda-cycle map glyph `l`) asserting no node is titled by any of them — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k cascade_guard`
- [ ] 5.3 Implement the same-style line join (≤2 lines, same rounded size + font class, adjacency across block/line, first line not sentence-ending) with two-directional fixtures: join succeeds on action-plan page 3 (`Safe and Green` + `Mobility` → one node), does not join on SMP page 6's two pull-quote columns — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k cascade_guard`

## 6. Structural validation gate (D1, D2)

- [ ] 6.1 Wire `validate_split()` + the level invariant (fails when >1 level exists and no level-1 node) into `process()` post-`merge_overrides`, appending `InvalidStructure` entries (doc_slug, check, offending value) to `errors.json` without altering the tree; unit-test the invariant with an all-level-2 tree — `uv run pytest pipelines/document_pipeline/tests/test_detect_structure.py -k validation_gate`
- [ ] 6.2 Assert the end-to-end SMP sidecar tree (footers filtered, `Chapter N` anchored) validates clean and that the pre-fix sidecars would have failed — covered by fixture checks above plus the audit in §7
- [ ] 6.3 Update `steps/detect_structure/README.md` error table with `InvalidStructure` and note validation always runs in production — verify the README renders the new row and `uv run python scripts/generate_pipeline_docs.py` leaves no stale generated section (`CI check`)

## 7. Corpus regeneration + audit (D8, D9)

- [ ] 7.1 Run the full document pipeline from `detect_structure` on this branch — `cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error` — and confirm zero steps errored, `errors.json` reviewed
- [ ] 7.2 Re-run the corpus audit over regenerated sidecars and committed meta.json — `PYTHONPATH=".:../../src" python experiments/2026-11-07-structure-corruption-audit/audit.py --head --published` — and confirm every document now validates clean or carries an explicit `InvalidStructure`/`override.json` correction
- [ ] 7.3 For residual documents (expected: national-cycle-network-plan and any emra/recreational-craft stragglers), hand-write `steps/detect_structure/override.json` entries per the D8 decision table, commit them, re-run scoped (`--doc <slug> --force`), and confirm the trees validate clean
- [ ] 7.4 Review the regenerated `public/` diff (bundle paths + meta.json chapters), confirm no schema/`detection_method`-enum change, and check for orphaned published URLs vs `override.json` — merge gates per AGENTS.md before `main`

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied (archive copies the delta into `openspec/specs/document-structure-detection/spec.md`).
- Verify the archived result: `openspec validate --strict`, plus one final `--published` audit run against the merged artifact.
