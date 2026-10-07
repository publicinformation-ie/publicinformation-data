# ocr_minutes_files

OCRs image-only minutes PDFs (scanned documents with no text layer) so motions can be extracted downstream.

## What it does

1. Reads each record from `transform_minutes_files/output.json`.
2. Passes through records whose stripped `text` is at least `MIN_TEXT_CHARS` (200) unchanged (preserving `text` and `extractor` — no OCR performed).
3. For blank or near-empty texts, renders each page to an image with `pymupdf` (~300 dpi), runs `pytesseract.image_to_string` per page, and joins page texts in page order. Blank pages contribute nothing. A near-empty text layer can sit beside recoverable scanned pages, so these get an OCR attempt too.
4. Emits one merged record per input file (keyed on `file_url` via `IncrementalWriter`): successfully OCR'd records carry `extractor: "tesseract"`. Records still below the threshold after OCR are quarantined (see below) and never emitted.
5. Evicts pre-existing output records that fail the threshold (emitted by older runs before the gate existed), logging a quarantine error for each.

## Fail-closed policy

- OCR still unusable → no record emitted, plus an `EmptyTextExtraction` (blank throughout) or `NearEmptyText` (some text but under threshold, with char counts) entry naming the `file_url`. The url is added to `quarantined_ids.json` so it is never re-attempted (OCR is the pipeline's heaviest CPU cost); delete that file to force re-attempts, or run with `--force` for a clean slate.
- OCR raises (transient infra failure) → no record emitted, plus an `OcrFailed` entry naming the `file_url`. Not quarantined: retried on the next run.
- Never emits unusable text downstream, never silently drops a record (every quarantine has an `errors.json` entry).

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

- `errors.json` — per-file OCR failures (`EmptyTextExtraction` / `NearEmptyText` / `OcrFailed`).
- `quarantined_ids.json` — `file_url`s with deterministically unusable text, skipped on subsequent runs.
- `pdf_cache/` — local cache for PDFs fetched when the upstream `transform_minutes_files/pdf_cache` entry is missing (the step prefers the upstream cache to avoid re-downloading).
