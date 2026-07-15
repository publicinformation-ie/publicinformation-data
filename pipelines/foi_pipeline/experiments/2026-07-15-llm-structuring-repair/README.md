# LLM-Structuring Repair Experiment (2026-07-15)

## Hypothesis

Does an **OCR-markdown → `mistral-large` structuring** pass repair the FOI-table
PDFs that `transform_disclosure_files` currently mangles (clean_extraction_rate
≈ 0.728), **without hallucinating** field values?

Scoped as **targeted repair on the failing tail** — not a pipeline replacement.
XLS/other files are out of scope. No production code changes.

## Arms

- **A — baseline:** current prod `rows` from `transform_disclosure_files/output.json` (the known-broken reference).
- **B — LLM repair:** Mistral OCR (**inline** markdown — `table_format` omitted) → `chat.parse(model="mistral-large-latest", response_format=DisclosureLog)`.

## Method

1. `sample.py` → frozen seeded stratified draw of 30 broken PDFs (`sample.json`): 22 `newline_split_row`, 6 `null_column`, 2 `null_first_row`.
2. `extract.py` → arm B with two-layer caching (OCR markdown + parsed JSON, keyed by `sha256(file_url)`); captures arm A; records tokens + cost → `arms.json`. Requires a byte server at `MISTRAL_OCR_PDF_BASE_URL` that serves raw PDF bytes as `{MISTRAL_OCR_PDF_BASE_URL}/{sha256(file_url)}.bytes` — this is a separate source PDF store, not `ocr_cache/` (which holds already-computed `{sha}.json` OCR results, not PDF bytes).
3. Hand-label ~8–10 files spanning all three defects into `ground_truth.json` (label from the PDF, not from arm B).
4. `compare.py` → `results.json`:
   - **Structural** (all 30, automated): repair-rate + regression-flags via the reused `has_newline_split_row` / `has_null_column` / `has_null_first_row` predicates.
   - **Fidelity** (labelled subset): per-field precision/recall, value-fidelity violations (altered printed values), invented/dropped rows.
   - **Cost:** total + mean tokens/cost, extrapolated to the full 323-file `newline_split` tail.

## Reproduce

```bash
# from pipelines/foi_pipeline/
uv run python experiments/2026-07-15-llm-structuring-repair/sample.py
# start a byte server serving raw PDF bytes as {sha256(file_url)}.bytes (NOT ocr_cache/,
# which holds OCR results, not PDF bytes); export MISTRAL_API_KEY + MISTRAL_OCR_PDF_BASE_URL
uv run python experiments/2026-07-15-llm-structuring-repair/extract.py
# hand-label ground_truth.json, then:
uv run python experiments/2026-07-15-llm-structuring-repair/compare.py
```

## Results

**Never run.** `extract.py` requires a byte server exposing raw PDF bytes at
`MISTRAL_OCR_PDF_BASE_URL` (a piece of throwaway test infrastructure this
experiment depends on but never stands up itself) — that server was never
started, so `extract.py` never produced `arms.json`, `ground_truth.json`
was never hand-labelled (still all-empty placeholders), and `compare.py`
was never run. No structural, fidelity, or cost data exists for this
experiment.

## Go / No-Go Recommendation

**No-go — closed without a result.** Not rejected on quality grounds; the
experiment simply stalled before producing data. Revisiting would mean
standing up the byte server, running `extract.py` end-to-end, hand-labelling
`ground_truth.json`, then running `compare.py` — effectively starting the
measurement phase from scratch. See the parallel
`2026-07-15-local-ocr-comparison` experiment's README for the sibling
PDF-extraction screening effort, also closed without adoption; the current
pdfplumber/Mistral OCR baseline remains in production unchanged.

_Original adopt-signal (unchanged, for whoever resumes this): strong-majority
structural repair, no new `null_column`/`null_first_row` regressions, and —
on the labelled subset — high per-field precision/recall with **zero
invented rows and zero altered values**. Cleaning structure while altering
values is an explicit reject._
