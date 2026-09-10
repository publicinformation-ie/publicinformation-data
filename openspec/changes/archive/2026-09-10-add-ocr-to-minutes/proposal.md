## Why

78 of the 1030 minutes PDFs in the minutes pipeline are scanned, image-only documents with no embedded text layer. `pdfplumber` (which reads the text layer) returns empty text for them, so the downstream `extract_motions` LLM step has nothing to extract motions from. The pipeline's intended OCR path — `marker-pdf` — is dead code: `_extract_marker` imports `marker.output.text.TextOutput`, which no longer exists in the installed `marker-pdf 1.10.2`, so it raises on every file and the `pdfplumber` fallback is always used.

## What Changes

- Add a new `ocr_minutes_files` step to `minutes_pipeline`, inserted between `transform_minutes_files` and `extract_motions`, that OCRs image-only records with Tesseract (`pytesseract`).
- The new step passes through records that already have non-empty text and OCRs only the empty-text records (rendering pages to images with `pymupdf`, then `pytesseract.image_to_string`), emitting a single merged list keyed on `file_url`.
- Remove the broken `marker-pdf` extraction path (`_extract_marker`) from `transform_minutes_files`, leaving `pdfplumber` as its sole extractor. `marker-pdf` and `surya-ocr` remain installed in the venv but are no longer imported by this pipeline.
- Add `pytesseract` as a new pip dependency; document the `tesseract` system-binary prerequisite.
- Wire `extract_motions` to read from `ocr_minutes_files/output.json` instead of `transform_minutes_files/output.json`.
- Update `minutes_pipeline/pipeline.json`, the step `README.md`s, and the pipeline `README.md` step table.

## Capabilities

### New Capabilities

- `minutes-ocr`: optical character recognition of image-only council meeting minutes PDFs, producing text that feeds the existing motion-extraction flow.

### Modified Capabilities

(none — no specs exist for the minutes pipeline yet)

## Impact

- **Code**: new step `pipelines/minutes_pipeline/steps/ocr_minutes_files/`; edit `transform_minutes_files/process.py` (remove `_extract_marker`); edit `extract_motions` input wiring via `pipeline.json`.
- **Dependencies**: add `pytesseract` to `pipelines/document_pipeline/requirements.txt` (the incremental file that extends the root venv; `pymupdf` and `pillow` are already pinned there). `tesseract` is a system binary — documented, not pip-tracked.
- **Tests**: new cases in `pipelines/minutes_pipeline/tests/` covering non-empty passthrough, empty→OCR, and OCR-still-empty→error; `transform_minutes_files` tests updated for the removed marker path.
- **No new database, network, or publishing side effects.** OCR is local CPU processing; the existing `extract_motions` LLM step is unchanged.
