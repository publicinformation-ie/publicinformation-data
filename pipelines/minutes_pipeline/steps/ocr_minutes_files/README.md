# ocr_minutes_files

OCRs image-only minutes PDFs (scanned documents with no text layer) so motions can be extracted downstream.

## What it does

1. It reads each record from `transform_minutes_files/output.json`.
2. It passes through records whose stripped `text` is at least `MIN_TEXT_CHARS` (200) unchanged (preserving `text` and `extractor`, and performing no OCR).
   Records with `extractor: docx` are never OCR'd. If their text is unusable, the step quarantines them directly.
3. For blank or near-empty texts, it renders each page to an image with `pymupdf` (300 dpi). It runs `pytesseract.image_to_string` on each page (`lang="eng"`, with the default page segmentation of Tesseract). It then joins the page texts in page order. Blank pages contribute nothing. A near-empty text layer can sit beside recoverable scanned pages, so these get an OCR attempt too.
4. It emits one merged record per input file (keyed on `file_url` via `IncrementalWriter`). Successfully OCR'd records carry `extractor: "tesseract"`. Records still below the threshold after OCR are quarantined (see below) and never emitted.
5. On a normal (not `--force`) run, it evicts pre-existing output records that fail the threshold. Older runs emitted them before the gate existed. It logs a quarantine error for each one.

## Fail-closed policy

- OCR still unusable → no record emitted, plus an `EmptyTextExtraction` (blank throughout) or `NearEmptyText` (some text but under threshold, with char counts) entry that names the `file_url`. The step adds the `file_url` to `quarantined_ids.json`, so it never re-attempts it (OCR is the pipeline's heaviest CPU cost). Delete that file to force re-attempts, or run with `--force` for a clean slate.
- OCR raises (transient infrastructure failure) → no record emitted, plus an `OcrFailed` entry that names the `file_url`. The step does not quarantine it, so the next run retries it.
- The step never emits unusable text downstream and never silently drops a record. It logs every newly quarantined record to `errors.json`, and it rewrites that file at the start of each run.

## Prerequisites

- Python dependency: `pytesseract`. It is pinned in `pipelines/document_pipeline/requirements.txt`. Install it with `uv pip install -r pipelines/document_pipeline/requirements.txt`.
- System binary: `tesseract` must be on `PATH` (e.g. `brew install tesseract` on macOS). Unit tests stub `pytesseract`, so the suite runs without the binary. Only a live OCR run needs the binary.

## Running

The step supports incremental resumption (`IncrementalWriter`, `key_field="file_url"`), `--force`, `--public-body` and `--verbose`. `--workers N` bounds concurrent downloads and renders (default 2).

## Input

- `transform_minutes_files/output.json` (generated upstream)

## Output

`output.json` is `{ metadata, results: [...] }`, with one record per input file. Each record holds the input fields plus:

| Field | Description |
|---|---|
| `text` | OCR'd prose text (`extractor: "tesseract"`) or the original pass-through text |
| `extractor` | The upstream value (`"pdfplumber"`, `"html"` or `"docx"`) for pass-through records, `"tesseract"` for successfully OCR'd records |

## Notable files

- `errors.json`: per-file OCR failures (`EmptyTextExtraction` / `NearEmptyText` / `OcrFailed`).
- `quarantined_ids.json`: `file_url`s with deterministically unusable text, skipped on subsequent runs.
- `pdf_cache/`: local cache for PDFs fetched when the upstream `transform_minutes_files/pdf_cache` entry is missing (the step prefers the upstream cache to avoid re-downloading).
