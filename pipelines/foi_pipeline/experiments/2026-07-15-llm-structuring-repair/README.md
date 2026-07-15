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
2. `extract.py` → arm B with two-layer caching (OCR markdown + parsed JSON, keyed by `sha256(file_url)`); captures arm A; records tokens + cost → `arms.json`. Requires a byte server over `ocr_cache/` at `MISTRAL_OCR_PDF_BASE_URL`.
3. Hand-label ~8–10 files spanning all three defects into `ground_truth.json` (label from the PDF, not from arm B).
4. `compare.py` → `results.json`:
   - **Structural** (all 30, automated): repair-rate + regression-flags via the reused `has_newline_split_row` / `has_null_column` / `has_null_first_row` predicates.
   - **Fidelity** (labelled subset): per-field precision/recall, value-fidelity violations (altered printed values), invented/dropped rows.
   - **Cost:** total + mean tokens/cost, extrapolated to the full 323-file `newline_split` tail.

## Reproduce

```bash
# from pipelines/foi_pipeline/
uv run python experiments/2026-07-15-llm-structuring-repair/sample.py
# start byte server over ocr_cache/ dir; export MISTRAL_API_KEY + MISTRAL_OCR_PDF_BASE_URL
uv run python experiments/2026-07-15-llm-structuring-repair/extract.py
# hand-label ground_truth.json, then:
uv run python experiments/2026-07-15-llm-structuring-repair/compare.py
```

## Results

_Filled from `results.json` after the run._

- Structural repair-rate: **TBD (fill from results.json)** (repaired / broken)
- Regressions introduced: **TBD**
- Fidelity — altered values: **TBD**; invented rows: **TBD**; dropped rows: **TBD**
- Per-field precision/recall: **TBD**
- Measured cost: **$TBD** over the sample; extrapolated full-tail (323 files): **$TBD**

## Go / No-Go Recommendation

_Adopt-signal (all must hold): strong-majority structural repair, no new
`null_column`/`null_first_row` regressions, and — on the labelled subset — high
per-field precision/recall with **zero invented rows and zero altered values**.
Cleaning structure while altering values is an explicit **reject**._

**Recommendation: TBD (fill after run).**

Any invented row or altered value on the labelled subset is a red flag and is
called out here explicitly.
