# Design

## Context

`detect_structure` reads only `extract_pages` output (`pipeline.json` dependencies), so the spans and outline are its complete input. The existing harness in `steps/detect_structure/eval/` has three parts:

- `make_input.py` builds `input.json`, a spans-only snapshot in Git LFS covering 24 documents. A hash check on 2026-11-22 found all 24 identical to live output. The 16 Climate Action Plan documents are missing.
- `compare.py` and `expected.json` run the legacy-versus-TOC comparison, asserted by `tests/test_comparison.py`.
- Live `extract_pages` output (`output.json` plus about 180 MB of page sidecars) is gitignored, so it exists only in a checkout that has run the pipeline. CI checks out with `lfs: true`.

Published chapters are nodes with no resolvable parent (`assemble_sections._chapter_node`), not only level-1 nodes.

## Goals / Non-Goals

**Goals:**
- An objective, repeatable chapter-accuracy number per document and for the corpus, with a per-document diff against a baseline.
- Gold that is repeatable even with one annotator, the repo maintainer: the same person annotating the same document again gets the same answer.

**Non-Goals:**
- Section-level (level ≥ 2) accuracy. The gold format leaves room for it, but nothing scores it.
- A CI gate. The report is run by hand. Gating can be a later change once the gold has settled.
- Changing detection, including the "outline wins over the printed TOC" behaviour the report is expected to expose.
- Retiring `compare.py` / `expected.json`. It still guards the TOC strategy's diagnostics, and only its expected values are refreshed.
- Gold for all 40 documents. This change ships 10.

## Decisions

### D1. Initial gold subset

Ten documents, each verified to have a printed contents page. Together they cover every detection method and the worst known splits, plus two likely-good controls, so the baseline can show both failure and success:

| Document | Method today | Why it's in |
|---|---|---|
| `national-cycle-network-plan` | toc | junk `[approximately …kph]` and address chapters; one chapter covers 793 pages |
| `climate-action-plan-2023` | outline | single `Untitled` chapter; outline overrides the printed TOC (pp. 3–7) |
| `climate-action-plan-2025-annex-of-actions` | outline | single chapter covering pp. 8–96 |
| `sustainable-mobility-policy` | toc | history of all-level-2 and numeral-chapter corruption |
| `emra-regional-spatial-and-economic-strategy` | numbering | below-gate TOC (43%); has overrides |
| `all-island-strategic-rail-review-final-report` | toc | history of chapter-level misassignment |
| `gda-transport-strategy-2022-2042` | outline | has overrides; tests raw versus post-override |
| `connecting-ireland-rural-mobility-plan` | numbering | TOC match rate 20%; 5 chapters for 128 pages |
| `climate-action-plan-2024-q1-q2-progress-report` | toc | control: 100% match rate |
| `national-roads-2040-final-report` | outline | control: outline without overrides |

### D2. Gold file location and shape

The files go in `steps/detect_structure/eval/gold/<doc_slug>.json`, one per document, so diffs and reviews stay per document. They are committed as ordinary git (they're small), not LFS.

```json
{
  "doc_slug": "national-roads-2040-final-report",
  "pdf_sha256": "…",
  "toc_pdf_pages": [3],
  "annotator": "…",
  "annotated_on": "2026-11-23",
  "reviewed": true,
  "notes": "free text: anything the guideline had to decide",
  "chapters": [
    {"title": "Introduction", "printed_page": "1", "pdf_page": 7}
  ]
}
```

`pdf_sha256` is taken from `fetch_pdfs` output (`source_sha256`). `printed_page` is kept as a cross-check: a constant offset between printed and PDF pages that suddenly jumps is the cheapest way to spot a transcription error. A separate `gold/no_toc.json` lists documents without a printed TOC, each with a one-line reason. Adding a document there needs a check by eye, not a parser result. None of the initial ten belong there.

### D3. Annotation guideline

`gold/GUIDELINE.md` sets the rules:

- Use the top level of the first contents listing only. "Top level" is decided by the TOC's typography (indent, then numbering depth, then weight), in that order.
- Copy the title exactly as the TOC prints it, without its number.
- `pdf_page` is the page where the chapter's heading appears in the body, checked on the rendered page. It is not the printed number plus an offset.
- A TOC entry whose heading is missing from the body still gets a gold chapter, placed at the page the printed number points to, with a note.
- Front matter is never annotated.

A worked example will be taken from one of the ten.

### D4. Annotation workflow: pre-fill, then verify on images

A helper renders each document's contents pages, and each candidate start page, to PNG under a gitignored scratch directory. It also writes a draft gold file pre-filled from the **PDF's text layer of the contents pages**, never from `parse_toc` or detector output, with `reviewed: false`. A person then corrects the draft against the images and sets `reviewed: true`. *Alternative considered:* pre-filling from detector output. This was rejected because reviewers tend to accept whatever they are shown, which would bias the gold toward the thing being measured.

### D4a. Quality control with a single annotator

With no second annotator to compare against, gold quality is checked two other ways:

1. **Automatic consistency checks** (spec: Gold consistency checks). These catch slips, not judgement errors. The printed-to-PDF page offset should be constant, or change only where `notes` explain it (inserted maps, roman-numeral front matter). Each title should appear in the text layer of its start page. No two chapters should share a page without a note. They run on every report, so a careless edit surfaces at once.
2. **Delayed blind re-annotation** (spec: Gold re-annotation agreement). This catches inconsistent judgement. At least a week after first annotating them, re-annotate two documents from scratch into a gitignored scratch file, without opening the committed gold. Use one with an ambiguous TOC (`national-cycle-network-plan`) and one ordinary document (`all-island-strategic-rail-review-final-report`). Compare with `score.py --compare-gold`. Every disagreement either becomes a guideline rule or is recorded as a genuine ambiguity in the gold file's `notes`. The resulting agreement is recorded in `GUIDELINE.md` and acts as the noise floor: a detector change smaller than gold disagreement on that kind of document is not evidence.

**Decision (2026-11-22):** the delayed re-annotation is **not required for this change**. The capability it uses (`--compare-gold`) is implemented and tested, and the exercise can be run later if a second reading is wanted; the initial corpus was reviewed and approved without it. Gold quality for this change therefore rests on the guideline, the per-document `notes`, and the automatic consistency checks.

*Alternative considered:* using an LLM as a second annotator. It was rejected for this change. It adds a paid step, and its errors are correlated with the text-layer pre-fill, so it is not an independent check. It could be reconsidered once the corpus grows.

### D5. Boundary matching algorithm

Exact matching uses a monotonic alignment by page: a longest-common-subsequence style dynamic program over the two page sequences, where a pair counts only if the pages are equal. Tolerant matching runs the same program with |Δpage| ≤ 1. When two alignments are equally good, the earlier pairing is preferred. *Alternatives:* greedy nearest-neighbour matching (order-dependent, so it can mis-pair on dense pages) and Hungarian assignment (ignores document order). The dynamic program is deterministic and keeps the order. Matching uses page only. `start_y` is not used, because gold records page only and page is what the reader experiences.

### D6. Page attribution

For pages 1..N, each page gets a gold label (front matter, or gold chapter *i*) and a predicted label (front matter, or predicted chapter *j*). A page is correct when both labels are front matter, or when *j* is exact-matched to *i*. N is the snapshot's `page_count`. This is the metric that captures "one junk chapter covers 793 pages", which boundary F1 counts as a single false positive.

### D7. Running the detector inside the report

The report calls the same public functions production uses (`detect_structure`, `merge_overrides`) on snapshot pages, the way `compare.py` already does. That makes the raw and post-override trees exactly what `process()` would produce, without touching step outputs. Overrides are read from the committed `steps/detect_structure/override.json`.

### D8. Report location and output

The report lives in `steps/detect_structure/eval/score.py`. It prints a per-document table and a corpus summary to stdout. `--json PATH` writes the machine-readable result. `--baseline` diffs against `eval/baseline.json`, which is committed, and `--refresh-baseline` rewrites it. `--live` scores local `extract_pages` output. It runs from `pipelines/document_pipeline` like `compare.py` (`PYTHONPATH=".:../../src"`).

### D9. Snapshot rebuild

`make_input.py` is extended to include all documents and to record `spans_sha256` (a hash of the canonical JSON of each page's spans plus the outline) and `source_sha256`. The drift check in `--live` mode compares these fingerprints. After the rebuild, `expected.json` is refreshed with `compare.py --refresh-expected`, and the 24 existing rows are checked to be unchanged before the refresh is committed.

## Risks / Trade-offs

- [The gold reflects one person's reading of an ambiguous TOC, with no one to cross-check it] → Mitigation: the guideline fixes the order of tie-breakers; `notes` records each judgement call; automatic consistency checks catch slips; delayed blind re-annotation (D4a) measures judgement consistency and sets the noise floor for reading results. Remaining risk: a consistent personal bias is not detectable this way. It is limited by the "TOC is the definition" rule, which leaves little room for interpretation.
- [Re-annotating from memory rather than blind] → Mitigation: wait at least a week, use a scratch file, and don't open the committed gold. The comparison is only as honest as the discipline behind it, which is why it is recorded rather than enforced.
- [Ten documents is a small sample; a heuristic tuned on them may not generalise] → Mitigation: report per-document results, not only averages, and annotate new `documents.yml` entries before looking at their output, so they serve as held-out documents.
- [The snapshot grows LFS storage with every rebuild] → Mitigation: rebuild only when the corpus or `extract_pages` changes. The drift warning shows when a rebuild is due.
- [Outline-method documents may score badly by definition, because the outline is not the printed TOC] → This is intended. It is the cost the report is meant to make visible. Interpret the score with the detection method alongside it, which the report prints.
- [A re-fetched PDF silently invalidates page numbers] → Mitigation: `pdf_sha256` mismatch excludes the document from scoring (spec: Gold PDF mismatch).
