# Proposal

## Why

The document pipeline has no way to measure whether its chapter split is correct. `validate_split` checks the tree's shape, and `eval/compare.py` reports whether the output changed. Neither compares a split with the right answer. Clearly wrong splits pass both today: `national-cycle-network-plan` has a `[approximately 110kph]` chapter covering 793 pages, and `climate-action-plan-2023` is a single `Untitled` chapter. Without a ground truth, a detector change can't be shown to help, and a regression can't be caught.

## What Changes

- **Gold chapter lists.** Hand-authored and committed, for an initial subset of 10 documents. Each one transcribes the top level of the document's main printed table of contents, the definition of its chapter structure, and ties each entry to the PDF page where it starts.
- **An annotation guideline**, so that the same document yields the same gold file whenever it is annotated. There is a single annotator, so gold quality is checked in two ways: automatic consistency checks on every gold file, and a delayed blind re-annotation of two documents, scored with the same metrics as the detector.
- **A read-only accuracy report.** It scores each gold document's detected chapters against its gold file, on both the raw detector output and the output after `override.json` is applied. It reports boundary precision, recall and F1 (exact page, and ±1 page), page attribution accuracy, title accuracy, and how many documents are fully correct. Results are given per document and for the corpus, as macro and micro averages.
- **A committed baseline report**, so a later detector change shows up as a per-document diff.
- **A rebuilt detection snapshot** (`steps/detect_structure/eval/input.json`) covering all 40 documents, up from 24. Each document records a fingerprint of its extracted spans and its PDF's sha256. The report runs off the snapshot by default, with a `--live` option. It warns when live output no longer matches the snapshot, and refuses to score a document whose gold PDF hash differs from the one being scored.
- The report is **not a CI gate** in this change. It is run by hand before and after a detector change.

## Capabilities

### New Capabilities

- `document-structure-evaluation`: ground-truth evaluation of the document pipeline's chapter split. Covers the gold chapter-list format and annotation rules, the accuracy metrics, the report and its baseline, and the detection snapshot the report scores.

### Modified Capabilities

(none — detection behaviour is unchanged; the existing `TOC comparison metrics` requirement and its regression test stay as they are, with `expected.json` refreshed for the larger snapshot)

## Impact

- New: `pipelines/document_pipeline/steps/detect_structure/eval/gold/` (10 gold files plus `GUIDELINE.md`), a scoring script and its baseline report in the same `eval/` directory, and unit tests in `pipelines/document_pipeline/tests/`.
- Changed: `eval/make_input.py` (all documents, span fingerprint, PDF sha256), `eval/input.json` (rebuilt; Git LFS, roughly 35 MB → 70–90 MB), and `eval/expected.json` (refreshed for the 16 added documents).
- No pipeline step output, `override.json`, or published artifact changes. No network or paid calls.
- Docs: `steps/detect_structure/README.md` and `pipelines/document_pipeline/README.md` gain a section on how to run the report and add gold files.
