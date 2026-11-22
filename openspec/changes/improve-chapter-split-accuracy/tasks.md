# Tasks

Run from `pipelines/document_pipeline` with `PYTHONPATH=".:../../src" ../../.venv/bin/python steps/detect_structure/eval/score.py …`. "Measure" means following design D0: compare against the baseline, write the `eval/RESULTS.md` entry with a reason for each regression, run `compare.py` over all 40 documents, refresh the baseline, and commit. A step that fails D0 is reverted rather than tuned.

## 0. Prerequisite

- [x] 0.1 Archive `fix-document-structure-corruption` so that the main `document-structure-detection` spec carries its requirements. Verify that `openspec list` no longer lists it, and that `openspec validate improve-chapter-split-accuracy` passes.

## 1. Held-out gold and eval support (D9)

- [x] 1.1 Add optional boolean `held_out` to gold validation in `eval/gold.py`, and add the separate held-out, tuning and all summaries to `score.py`, including the table marker and the baseline payload. Verify with unit tests that reproduce the spec scenarios "Separate summaries" and "Held-out flag absent".
- [x] 1.2 Create `eval/RESULTS.md` with the entry template (step, commit, tuning, held-out and all summaries before and after, per-document diff, reasons for regressions, and `compare.py` notes on the 30 documents without gold). Verify it is linked from the "Accuracy evaluation" section of `steps/detect_structure/README.md`.
- [x] 1.3 **Maintainer:** annotate the first four D9 candidates that have a printed TOC, with `annotate.py` and the review page, without running `score.py` or opening detector output for them, and set `held_out: true` and `reviewed: true`. Record any candidate without a TOC in `no_toc.json`. Verify that `score.py --check-gold` passes and every consistency warning is fixed or explained in `notes`.
- [x] 1.4 Refresh the baseline with the held-out documents included and commit. Verify that the report scores 14 documents (10 tuning, 4 held out) and excludes none without a reason. Record this as the starting entry in `RESULTS.md`.

## 2. One detection entry point (D1)

- [x] 2.1 Extract `detect_document_structure` in `process.py` (outline filter, position resolution, and the cascade), and route `process()` through it with no change to `errors.json` output. Verify the existing detect_structure tests pass unchanged.
- [x] 2.2 Make `score.detect_document` call it. Verify with a new test that `process()` and `score_document` produce identical raw trees on one fixture whose outline has an `_Hlk` bookmark and a one-page-late entry (spec: "Same tree in production and evaluation", "Outline preparation applied").
- [x] 2.3 Measure, and label the entry in `RESULTS.md` a **measurement correction**. Verify that national-roads has no `_Hlk` chapter in its predicted list and that GDA's boundaries moved. This baseline becomes the post-D1 reference used in D10.

## 3. Outline entry normalisation (D2)

- [x] 3.1 Collapse whitespace before the number split in `from_outline`. Verify with a unit test of the "Multi-line outline title loses its number" scenario.
- [x] 3.2 Merge wrapped same-page outline fragments, verifying each join against the page's text. Verify with unit tests of the "Wrapped outline fragments are merged" and "Unverified fragments stay separate" scenarios, plus a two-headings-on-one-page fixture that stays split.
- [ ] 3.3 Document the outline normalisation in `steps/detect_structure/README.md`, then measure. Verify that GDA's `Freight, Delivery and Servicing` and `Enviromental Assessment` are single predicted chapters.

## 4. Outline plausibility (D3)

- [x] 4.1 Reject outlines with fewer than two entries at their shallowest level, fall through the cascade, and log `OutlineNotUsed`. Verify with unit tests of the "Single-entry outline is not chapter evidence", "Single-root outline is not chapter evidence" and "Outline still wins" scenarios.
- [x] 4.2 Update the strategy table and the `errors.json` types in the README, then measure. Verify that `climate-action-plan-2023` is no longer `outline`. Record in `RESULTS.md` the method change for every document without gold whose outline fails the check.

## 5. TOC parsing (D5), measured as three sub-steps

- [x] 5.1 Capture printed page numbers per TOC entry (arabic as int, others kept as printed), and join continuation lines. Verify with unit tests of the "Wrapped TOC entry joined", "Separate entries stay separate", "Right-column page number recorded" and "Roman page number not used" scenarios. Then measure (5a).
- [x] 5.2 Parse `Chapter N` labels on the same line and on the line above, and add the `label` level signal. Verify with unit tests of the three "TOC chapter labels" scenarios and that the existing "Missing level signal yields a flat tree" test still passes. Then measure (5b).
- [x] 5.3 Detect TOC continuation pages. Verify with unit tests of "Untitled second contents page parsed" and "Later part TOC still ignored". Document 5.1 to 5.3 in the README's TOC-strategy paragraph, then measure (5c).

## 6. Gate denominator and heading codes (D6, D7)

- [x] 6.1 Classify unpaged entries and exclude them from the gate denominator. Verify with unit tests of both "Unpaged TOC entries excluded from the gate" scenarios, then measure.
- [x] 6.2 Treat pipe-separated codes as heading numbers in `_split_number`. Verify with unit tests of "Code prefix matched across TOC and body" and "Ordinary pipe kept", and a slug test (`re-research-and-innovation`). Document the rule in the README, then measure. Check the slug changes on the other CAP annexes in `compare.py`'s output.

## 7. Supplement confinement (D4)

- [ ] 7.1 Derive TOC chapter numbers (own number, or the shared lead of their numbered children), confine supplemented headings to level-2+ sections under the matching chapter, and log `SupplementHeadingRejected`. Verify with unit tests of "Supplemented heading cannot become a chapter" and "Supplemented section under its own chapter is kept".
- [ ] 7.2 Update the README's supplement description, then measure. Verify that national-cycle's predicted chapters are the 8 TOC chapters.

## 8. Guarded placement by printed page (D8)

- [ ] 8.1 Place unmatched top-level entries when both neighbours' offsets agree, with `toc_placed` confidence and a `TocEntryPlacedByPageNumber` error, and keep placed entries out of the gate. Verify with unit tests of the four "Guarded placement by printed page" scenarios.
- [ ] 8.2 Add `toc_placed` to the README's confidence notes and errors list, then measure. Verify in `RESULTS.md` that every placement made on a gold document lands on its gold page, and list any placement that does not.

## 9. Acceptance and integration

- [ ] 9.1 Read the held-out summary against the post-D1 reference, and write the final `RESULTS.md` entry comparing the post-D1 and final results for tuning, held-out and all documents. Verify every D10 criterion (a) to (e) holds, or record which one fails and why.
- [ ] 9.2 Refresh `eval/expected.json` with `compare.py --refresh-expected` and review the diff. Verify that `uv run pytest pipelines/document_pipeline/tests -q`, `uv run pytest tests/ -q`, `cd pipelines/foi_pipeline && uv run pytest tests/ -q` and `uv run pyright` all pass.
- [ ] 9.3 List every `override.json` entry that the new trees orphan (from `compare.py`), and re-point or remove each one in a reviewed commit. Verify that `merge_overrides` reports no unmatched slug for any document.

## Workflow follow-up

- The maintainer regenerates `document_pipeline` from `detect_structure` (`--force --stop-on-error`) and reviews the bundle diff before merging.
- Archive the change once the results log and the final baseline are reviewed.
- Later changes: reconcile the outline with the printed TOC (GDA PART A/B); flag garbled text layers; extend gold to the remaining documents.
