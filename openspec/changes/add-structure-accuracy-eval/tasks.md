# Tasks

## 1. Detection snapshot covers the whole corpus

- [x] 1.1 Extend `steps/detect_structure/eval/make_input.py` to record `spans_sha256` (canonical JSON of each page's spans plus the outline) and `source_sha256` (from `fetch_pdfs` output) for every document; verify a new unit test builds a two-document snapshot from fixture sidecars and asserts both fields are present and stable across two runs
- [x] 1.2 Rebuild `eval/input.json` for all 40 documents; verify `doc_count` is 40, the file is still LFS-tracked (`git check-attr filter`), and the 24 previously present documents keep identical span fingerprints
- [x] 1.3 Refresh `eval/expected.json` with `compare.py --refresh-expected`; verify the diff only adds the 16 new rows and `uv run pytest pipelines/document_pipeline/tests/test_comparison.py -q` passes

## 2. Gold format, validation and guideline

- [x] 2.1 Write `eval/gold/GUIDELINE.md` (rules D3, the no-TOC rule, a worked example) and add an "Accuracy evaluation" section to `steps/detect_structure/README.md` that links to it; verify both render and the README's commands match the script's flags
- [x] 2.2 Implement gold loading and validation: required fields, non-decreasing `pdf_page`, `reviewed` flag, and the `no_toc.json` register. Malformed, unreviewed and no-TOC documents are excluded with reasons. Verify with unit tests covering each exclusion scenario in the spec
- [x] 2.3 Implement the gold consistency warnings (page-offset jump without a note, title missing from its start page's text layer, shared `pdf_page` without a note); verify unit tests reproduce the spec's "page offset jump" and "title not on its start page" scenarios, and that a `notes` entry clears the offset warning

## 3. Scoring

- [x] 3.1 Implement predicted-chapter extraction (nodes with no resolvable parent); verify a unit test with an orphaned level-2 node counts it as a chapter
- [x] 3.2 Implement monotonic boundary matching (exact and ±1); verify unit tests cover the "two chapters on one page", "off by one page" and determinism scenarios
- [x] 3.3 Implement boundary P/R/F1, page attribution (front matter as a chapter on both sides), normalised title accuracy and "fully correct"; verify unit tests reproduce the spec's "over-split", "swallowed pages", "fully correct" and "title comparison" scenarios with exact expected values
- [x] 3.4 Implement the corpus summary (macro and micro averages, fully-correct count, excluded list); verify a unit test where one large document does not dominate the macro average

## 4. Report

- [x] 4.1 Implement `eval/score.py`: run detection on the snapshot via the production `detect_structure` and `merge_overrides`, score raw and post-override, print the per-document table and summary, `--json PATH`; verify an end-to-end test on a fixture snapshot plus gold prints both raw and post-override rows for an overridden document
- [x] 4.2 Add `--live` (score local `extract_pages` output), the snapshot drift warning and the gold/PDF sha256 mismatch exclusion; verify unit tests cover the drift and mismatch scenarios
- [x] 4.3 Add `--baseline` diff and `--refresh-baseline`; verify a test where one document improves and another regresses shows both per-document changes
- [x] 4.4 Add `--compare-gold A B` (scores one gold file against another with the same metrics and lists every disagreeing chapter); verify a test with two gold files differing by one boundary and one title reports both
- [x] 4.5 Verify read-only behaviour: a test runs the report without `--refresh-baseline` and asserts no file under the repository changed (compare mtimes or hashes of the step dir and `eval/`)

## 5. Annotation of the initial 10 documents

- [x] 5.1 Add the annotation helper (renders contents pages and candidate start pages to a gitignored scratch dir; writes a draft gold file from the contents pages' text layer with `reviewed: false`, never from detector output); verify it produces a draft and images for `national-roads-2040-final-report`
- [x] 5.2 Annotate and review the 10 documents in design D1, recording judgement calls in `notes`; verify every file passes gold validation with `reviewed: true`, `pdf_sha256` matches the snapshot, and every consistency warning is either fixed or explained in `notes`
- [x] 5.3 At least a week after 5.2, blind re-annotate `national-cycle-network-plan` and `all-island-strategic-rail-review-final-report` into a gitignored scratch file without opening the committed gold, then run `score.py --compare-gold`; verify the agreement figures and the resolution of each disagreement (a new guideline rule, a corrected gold file, or a recorded ambiguity) are written to `GUIDELINE.md` — **dropped on 2026-11-22 by maintainer decision: not required for this change.** The `--compare-gold` capability it would exercise is implemented and tested; the exercise can be run later if a second reading is wanted.

## 6. Baseline

- [x] 6.1 Run `score.py --refresh-baseline` and commit `eval/baseline.json`; verify the report scores 10 documents, excludes none, and the known-bad cases (`national-cycle-network-plan`, `climate-action-plan-2023`, `climate-action-plan-2025-annex-of-actions`) show low page attribution in the printed table
- [x] 6.2 Run the three test suites and `uv run pyright`; verify all pass

## Workflow follow-up

- Archive the change once the baseline is committed and reviewed.
- Later change, not this one: extend gold to the remaining 30 documents, and consider a CI gate once the gold has settled.
