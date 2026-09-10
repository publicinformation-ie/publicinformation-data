## 1. Dependencies

- [x] 1.1 Add `pytesseract==<latest>` to `pipelines/document_pipeline/requirements.txt`
- [x] 1.2 Install into the venv (`uv pip install -r pipelines/document_pipeline/requirements.txt`) and verify `import pytesseract` succeeds
- [x] 1.3 Document the `tesseract` system-binary prerequisite in the new step `README.md`

## 2. New `ocr_minutes_files` step

- [x] 2.1 Scaffold `pipelines/minutes_pipeline/steps/ocr_minutes_files/` (`process.py`, `README.md`, `output_schema.json`, `__init__.py`) following an existing step's shape
- [x] 2.2 Implement `process.py`: read input, render empty-text records' pages to images via `pymupdf` (~300 dpi), OCR each page via `pytesseract.image_to_string`, join in page order
- [x] 2.3 Pass through non-empty-text records unchanged (preserve `text` and `extractor`)
- [x] 2.4 Set `extractor: "tesseract"` on successfully OCR'd records; emit the merged list keyed on `file_url` via `IncrementalWriter`
- [x] 2.5 Fail closed: on empty OCR result write `EmptyTextExtraction`, on exception write `OcrFailed` (naming `file_url`) and emit the record with empty `text`
- [x] 2.6 Add `output_schema.json` matching the `transform_minutes_files` record shape (with `tesseract` as a new allowed `extractor` value)

## 3. Remove marker-pdf

- [x] 3.1 Delete `_extract_marker` from `transform_minutes_files/process.py`, leaving `pdfplumber` as the sole extractor
- [x] 3.2 Update `transform_minutes_files/README.md` (remove the marker-pdf-first description)

## 4. Wire the pipeline

- [x] 4.1 Insert `ocr_minutes_files` into `pipelines/minutes_pipeline/pipeline.json` between `transform_minutes_files` and `extract_motions`
- [x] 4.2 Update `pipelines/minutes_pipeline/README.md` step table (new step + `extract_motions` input note)
- [x] 4.3 Re-run `scripts/generate_pipeline_docs.py` and commit the regenerated AGENTS.md pipeline overview

## 5. Tests

- [x] 5.1 Add `tests/test_ocr_minutes_files.py`: non-empty passthrough, empty→OCR (stub `pytesseract.pytesseract.tesseract_cmd` / mock `image_to_string`), OCR-still-empty→error logged, per-page join
- [x] 5.2 Update `tests/test_transform_minutes_files.py` for the removed marker path (pdfplumber-only expectations)
- [x] 5.3 Run `uv run pytest pipelines/minutes_pipeline/tests -q` and `uv run pyright`

## 6. Verify end-to-end

- [x] 6.1 Run the pipeline scoped to Meath (`--public-body 1511 --force --stop-on-error`) and confirm the 78 previously-empty records now carry OCR text
- [ ] 6.2 Spot-check OCR quality on a few image-only records and confirm `extract_motions` produces motions for them
- [x] 6.3 Review `ocr_minutes_files/errors.json` for unresolved reconstructions before any publish
