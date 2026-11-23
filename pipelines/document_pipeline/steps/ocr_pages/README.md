# ocr_pages

Reads image-only pages that the curator lists, with Tesseract, so that they have a text layer. It is the third step in `document_pipeline`, right after `extract_pages`. It does one thing, and `extract_pages` is not aware of it.

## What it does

OCR (optical character recognition, the reading of text from an image) is opt-in per page. The curator lists 1-based page numbers under `ocr_pages` in `documents.yml`. `documents.py` validates the list, and the list reaches this step through `fetch_pdfs/output.json`. The step OCRs no other page.

- A document with no `ocr_pages` passes through, and the step does not open its PDF.
- A full-page raster image is one image that covers at least `OCR_MIN_IMAGE_COVERAGE` = 75% of the page. A listed page can be a full-page raster image with at most `OCR_MAX_NATIVE_LETTERS` = 20 letters of native text. A printed page number is fine. For such a page, the step renders the page at 300 dpi and OCRs it (`src/lib/ocr.py`: `--psm 3`, `eng`, deterministic).
- The step does not OCR a listed page that fails that test, because it has a real text layer or no full-page image. It also does not OCR a page beyond the page count. In both cases it logs `OcrPageNotScanned`.
- Each OCR line becomes a span in the native shape (`font: "tesseract-ocr"`, `size` = median word height in pt, plus `source: "ocr"`). Native spans are kept, and OCR words that sit on them are skipped. The page JSON gains `ocr: {engine, lang, psm, dpi, word_count, mean_confidence}`.

## Prerequisites

- Python dependencies: `pytesseract` and `pymupdf` (pinned in `pipelines/document_pipeline/requirements.txt`).
- System binary: `tesseract` must be on `PATH` (for example, `brew install tesseract` on macOS). The tests stub OCR, so the suite runs without the binary. Only a live run needs it.

## Input / output

Input: `extract_pages/output.json` (`--input`). The step also reads `fetch_pdfs/output.json` directly, for the `pdf_path` and the curated `ocr_pages` list of each document (`documents.py` validates them as unique 1-based positive integers). Output: `output.json` with the same record shape. `extract_pages/pages/*` is never modified. Each entry's `file` is resolved against the directory of this step (as `clean_text` does against the parent of its input), so:

- A page that the step does not OCR points at the upstream file, for example `../extract_pages/pages/<slug>/004.json`.
- A page that the step OCRs is a merged copy at `pages/<slug>/NNN.json` here, with `span_count` updated.

`clean_text` reads the output of this step (`pipeline.json` `input_steps`). `detect_structure` and `extract_figures` stay on `extract_pages`. The `source: "ocr"` marker flows through the `clean_text` blocks to the section note and to `meta.json` `ocr_pages`.

The step supports incremental resumption (a later run continues from earlier work and does not redo it) via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping. It rebuilds the `pages/<slug>/` directory of a reprocessed document from scratch. It removes the stale OCR page directory of a document that no longer lists pages.

## errors.json

| `error_type` | Cause |
|---|---|
| `OcrPageNotScanned` | The listed page is not a scanned full-page image, or it is out of range, so the step does not OCR it. Fix `documents.yml` |
| `OcrEmpty` | Tesseract found no text. The page stays uncovered. Review the page |
| `OcrLowConfidence` | The mean word confidence is less than `OCR_MIN_CONFIDENCE` (60). The step still emits the text. Review it |
| `OcrFailed` | The PDF is missing, or Tesseract raised an error. The document gets no record, because the step fails closed |

## Flags

`--input`, `--doc SLUG`, `--force`, `--verbose`, `--output`.
