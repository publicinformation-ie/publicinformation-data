# Local OCR Model Comparison (2026-07-15)

## Hypothesis

Could a locally-run model (no per-page API cost) match or beat pdfplumber /
Mistral OCR on the FOI-table PDFs that `transform_disclosure_files` mangles?
Planned scope: qwen2.5vl:7b, granite-docling, marker-pdf, and PaddleOCR
(PP-StructureV3), scored on a 30-file sample via the pipeline's existing
`has_null_first_row` / `has_null_column` / `has_newline_split_row` flags,
with a win requiring a `clean_extraction_rate` strictly better than both
pdfplumber and Mistral on the same files (see
`docs/superpowers/plans/2026-07-15-local-ocr-comparison.md` for the full
original design).

## Status: closed, no adoption

Stopped after the first two systems raised enough concerns to justify a
scope cut; `score.py` (the automated comparison) was never built, so no
system was ever formally scored against pdfplumber/Mistral. Sample size for
qwen/marker was also shrunk from 30 files to 15 mid-run for time reasons —
findings below are directional, not a statistically solid verdict.

## Findings by system

- **qwen2.5vl:7b (vision, via Ollama) — paused, not adopted.** A single-file
  diagnostic (90 pages) looked good: coherent, no hallucination, ~49s/page.
  The full 15-file/211-page batch's raw row counts also looked fine
  (~±10% of baseline, no zeros). But running the real downstream pipeline
  steps on qwen's output told a different story: baseline was 0
  `canonicalize` errors / 9 `decision_status` errors / 8 dedup-removed
  duplicates; qwen was 1 / **49** (5.4x) / **57** (7.1x) over the same
  sample. The extra errors were concentrated almost entirely in the two
  largest, most complex files (both 40+ pages), which had zero errors at
  baseline — suggesting qwen degrades specifically on long, complex
  multi-page tables rather than uniformly. Nobody has pulled up the
  specific garbled rows to confirm whether that's genuine hallucination or
  a more mechanical failure (e.g. column-merging on a differently-shaped
  table). Also far slower than Mistral OCR. Left as a paused side branch,
  not ruled out for future revisiting on shorter documents.
- **granite-docling (via Ollama) — dropped, closed.** Unusable: its real
  table structure lives in DocTags tokens (`<otsl>`, `<fcel>`, etc.) that
  Ollama's OpenAI-compatible endpoint silently strips before returning
  `content`, leaving only bounding boxes and undelimited cell text. No
  post-processing (including `docling-core`'s own `DocTagsDocument` parser)
  can recover structure that's already gone by the time Ollama responds.
  Confirmed with IBM's documented trigger prompt directly — same stripped
  output, ruling out prompt wording. Getting real output would require
  bypassing Ollama and running docling's native pipeline directly, which is
  a different, larger piece of work than this screening experiment and was
  not pursued.
- **marker-pdf — code-complete, never scored.** `run_marker.py` ran cleanly
  on all 15 sample files (fast: low seconds to ~25s/file) and produced
  plausible-looking row counts, but was never compared against the
  pdfplumber/Mistral baseline or run through the real downstream pipeline
  steps the way qwen was (`score.py` was never built). No verdict — quality
  is unknown, not confirmed-good or confirmed-bad.
- **PaddleOCR (PP-StructureV3) — not attempted.** Planned as Task 5, never
  started.

## Reusable output

`pipeline_eval.py` runs any two sets of `transform_disclosure_files`-shaped
records (varying just `rows`) through the real downstream steps
(`detect_header_row` → `normalize` → `canonicalize` → `canonicalize_rows` →
`deduplicate`) via direct function imports into scratch step-dirs, and
diffs error counts per file. This is what surfaced qwen's degradation on
large files — raw row-count comparison alone missed it. Worth reusing for
any future PDF-extraction screening experiment rather than rebuilding
row-count-only scoring.

## Why closed rather than continued

None of the systems evaluated so far produced a clear win, and completing
the original design (PaddleOCR + automated `score.py` scoring across all
four systems) was a larger time investment than the signal collected so
far justified. Combined with the parallel `2026-07-15-llm-structuring-repair`
experiment (Mistral-based table repair, also closed without a result — see
that experiment's README), the working conclusion is that the current
pdfplumber/Mistral OCR baseline in `transform_disclosure_files` remains the
best available option; further PDF-extraction quality gains should look at
other angles (e.g. fixing specific known misalignment patterns, per
`docs/superpowers/plans/2026-07-03-phantom-row-filter.md`) rather than
swapping the underlying extraction engine.
