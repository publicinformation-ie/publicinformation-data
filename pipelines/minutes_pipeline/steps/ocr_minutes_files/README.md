# ocr_minutes_files

OCRs image-only minutes PDFs (scanned documents with no text layer) so motions can be extracted downstream.

## What it does

1. Reads each record from `transform_minutes_files/output.json`.
2. Passes through records that already have non-empty `text` unchanged (preserving `text` and `extractor` — no OCR performed).
3. For empty-text records, renders each page to an image with `pymupdf` (~300 dpi), runs `pytesseract.image_to_string` per page, and joins page texts in page order. Blank pages contribute nothing.
4. Emits one merged record per input file (keyed on `file_url` via `IncrementalWriter`): successfully OCR'd records carry `extractor: "tesseract"`.

## Fail-closed policy

- OCR still empty → record emitted with empty `text` plus an `EmptyTextExtraction` entry naming the `file_url`.
- OCR raises → record emitted with empty `text` plus an `OcrFailed` entry naming the `file_url`.
- Never drops, nulls, or guesses a record.

## Prerequisites

- Python dependency: `pytesseract` (pinned in `pipelines/document_pipeline/requirements.txt`; install with `uv pip install -r pipelines/document_pipeline/requirements.txt`).
- System binary: `tesseract` must be on `PATH` (e.g. `brew install tesseract` on macOS). Unit tests stub `pytesseract` so the suite runs without the binary; only a live OCR run needs it.

## Input

- `transform_minutes_files/output.json` (generated upstream)

## Output

`output.json` — `{ metadata, results: [...] }`, one record per input file with the input fields plus:

| Field | Description |
|---|---|
| `text` | OCR'd prose text (`extractor: "tesseract"`) or the original pass-through text |
| `extractor` | `"pdfplumber"` for pass-through records, `"tesseract"` for successfully OCR'd records |

## Notable files

- `errors.json` — per-file OCR failures (`EmptyTextExtraction` / `OcrFailed`).
- `pdf_cache/` — local cache for PDFs fetched when the upstream `transform_minutes_files/pdf_cache` entry is missing (the step prefers the upstream cache to avoid re-downloading).
