## Context

The minutes pipeline extracts prose text in `transform_minutes_files`, then an LLM reads that text in `extract_motions`. Today `transform_minutes_files` tries `marker-pdf` then falls back to `pdfplumber`, but the marker path is broken (`marker.output.text.TextOutput` no longer exists in `marker-pdf 1.10.2`), so every file falls through to `pdfplumber`. Scanned, image-only PDFs have no text layer, so `pdfplumber` returns empty text and `extract_motions` receives nothing to read (see proposal.md — Why).

Environment facts that shape the approach: Python 3.14; `pymupdf 1.28.0` and `pillow` already pinned for the repo; `tesseract` binary already installed at `/opt/homebrew/bin/tesseract`; `surya-ocr 0.17.1` present only as a transitive dependency of the (broken) marker-pdf.

## Goals / Non-Goals

**Goals:**

- Give image-only minutes PDFs a text path so motions can be extracted downstream.
- Keep the change additive and confined to the minutes pipeline.
- Follow the repo's fail-closed principle: never drop, null, or guess a record.

**Non-Goals:**

- Fixing or re-enabling `marker-pdf` (it is removed, not repaired).
- Replacing the downstream LLM motion extraction.
- OCR-ing any file that already has a text layer.
- Reconstructing layout/tables; OCR output is plain per-page text joined in page order.

## Decisions

### D1: New dedicated step rather than a fallback inside `transform_minutes_files`

Add `ocr_minutes_files` between `transform_minutes_files` and `extract_motions`. It reads `transform_minutes_files/output.json`, OCRs empty-text records, passes the rest through, and emits one merged list.

**Alternative considered:** a third fallback inside `extract_text`. Rejected (user decision): a dedicated step keeps OCR separable, gives it its own incremental writer and error file, and makes the merge point explicit.

### D2: Tesseract via `pytesseract`

**Alternative considered — surya-ocr:** already installed, better on degraded scans, but heavy (torch + transformers), slow on CPU, and a ~GB model download on first run. Rejected for a first pass over 78 printed documents.
**Alternative considered — repairing marker-pdf:** it wraps surya for OCR, but the API-drift fix plus the heavy dependency makes surya-direct strictly simpler; and the goal here is removal, not repair.
Chosen: `pytesseract` — the binary is already present, the pip package is tiny, output on printed scans is more than adequate for the LLM downstream, and it has no model downloads or GPU requirement.

### D3: Render pages with `pymupdf`, OCR per page, join in page order

For an empty-text record, render each page to a ~300 dpi pixmap, convert to a PIL image, run `pytesseract.image_to_string`, and join page results with newlines. `pymupdf` and `pillow` are already pinned; rendering at 300 dpi is the conventional sweet spot for Tesseract accuracy on printed pages. Language defaults to `eng`.

**Alternative considered:** OCR the PDF directly with Tesseract's PDF mode, or use `pdf2image`. Rejected: the former hides per-page control and is harder to test; the latter adds a `poppler` system dependency for no gain over `pymupdf`.

### D4: Merged output with `extract_motions` re-wired to read it

The new step emits the full list (pass-through + OCR'd), keyed on `file_url` for the existing `IncrementalWriter` resumability. `extract_motions` input moves from `transform_minutes_files/output.json` to `ocr_minutes_files/output.json`. Downstream steps are untouched.

### D5: Remove the broken `marker-pdf` path

Delete `_extract_marker` from `transform_minutes_files/process.py`, leaving `pdfplumber` as the sole extractor. This removes a dead import and makes the `extractor` field honest (`"pdfplumber"`, plus the new `"tesseract"`). `surya-ocr`/`marker-pdf` remain in the venv but are no longer imported here.

### D6: Dependency placement

Add `pytesseract==<latest>` to `pipelines/document_pipeline/requirements.txt` (the incremental file extending the root venv; `pymupdf` and `pillow` are already there). The `tesseract` binary is a system prerequisite, documented in the step `README.md` rather than pip-tracked; tests must not require the binary.

### D7: Error policy

If OCR still produces empty text for an image-only record, or OCR raises, emit the record with empty `text` and write an error (`EmptyTextExtraction` / `OcrFailed` naming the `file_url`). No guessing, no silent drop — consistent with `transform_minutes_files`.

## Risks / Trade-offs

- **[Tesseract accuracy on degraded/handwritten scans]** → These are printed council minutes, not handwriting; accuracy is expected to be sufficient for LLM motion extraction. If specific pages come back garbled, they surface as downstream LLM extraction errors rather than silent failures.
- **[`tesseract` binary required in CI]** → Unit tests stub `pytesseract.pytesseract.tesseract_cmd` (or mock `image_to_string`) so the suite runs without the binary; only a live OCR run needs it.
- **[Irish-language text]** → Default `eng` handles Latin-script Irish; a `gle` language pack is an available follow-up if Irish-only pages appear, without changing the spec.
- **[OCR cost / time]** → ~78 documents × ~7 pages at 300 dpi on CPU is bounded and one-off; resumable via the `file_url` keyed writer.
- **[`extract_motions` input change forces a downstream re-run]** → Expected; `extract_motions` and later steps must be re-run after this lands. No data migration, rollback = revert the step + `pipeline.json` change.

## Migration Plan

1. Add the `ocr_minutes_files` step and `pytesseract` dependency; remove the marker path; re-wire `extract_motions` via `pipeline.json`.
2. Run `transform_minutes_files` (unchanged results) → `ocr_minutes_files` (fills the 78 empty records) → `extract_motions` onward.
3. Review the 78 OCR'd records' text and the resulting motions before publishing.

Rollback: revert the code and `pipeline.json`; `transform_minutes_files` output is unchanged, so no artifact cleanup is needed.

## Open Questions

None.
