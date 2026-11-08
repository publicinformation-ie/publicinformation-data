# ocr_pages

Reads curator-listed image-only pages with Tesseract so they have a text layer. Third step in `document_pipeline`, right after `extract_pages`; it does one thing and `extract_pages` is unaware of it.

## What it does

OCR is **opt-in per page**. The curator lists 1-based page numbers under `ocr_pages` in `documents.yml` (validated in `documents.py`, carried to this step through `fetch_pdfs/output.json`). Nothing else is ever OCR'd.

- A document with no `ocr_pages` passes through; its PDF is not opened.
- A listed page that is a full-page raster image (one image covering at least `OCR_MIN_IMAGE_COVERAGE` = 75% of the page) with at most `OCR_MAX_NATIVE_LETTERS` = 20 letters of native text (a printed page number is fine) is rendered at 300 dpi and OCR'd (`src/lib/ocr.py`: `--psm 3`, `eng`, deterministic).
- A listed page that fails that test (real text layer, no full-page image) or is beyond the page count is not OCR'd and logs `OcrPageNotScanned`.
- Each OCR line becomes a span in the native shape (`font: "tesseract-ocr"`, `size` = median word height in pt, plus `source: "ocr"`); native spans are kept and OCR words that sit on them are skipped. The page JSON gains `ocr: {engine, lang, psm, dpi, word_count, mean_confidence}`.

## Input / output

Input: `extract_pages/output.json` (`--input`). Output: `output.json` with the same record shape. `extract_pages/pages/*` is never modified. Each entry's `file` is resolved against this step's directory (as `clean_text` does against its input's parent), so:

- not-OCR'd pages point at the upstream file, e.g. `../extract_pages/pages/<slug>/004.json`;
- OCR'd pages are merged copies at `pages/<slug>/NNN.json` here, with `span_count` updated.

`clean_text` reads this step's output (`pipeline.json` `input_steps`); `detect_structure` and `extract_figures` stay on `extract_pages`. The `source: "ocr"` marker flows via `clean_text` blocks to the section note and `meta.json` `ocr_pages`.

## errors.json

| `error_type` | Cause |
|---|---|
| `OcrPageNotScanned` | Listed page is not a scanned full-page image, or is out of range; not OCR'd. Fix `documents.yml` |
| `OcrEmpty` | Tesseract found no text; the page stays uncovered. Review it |
| `OcrLowConfidence` | Mean word confidence < `OCR_MIN_CONFIDENCE` (60); text is still emitted. Review it |
| `OcrFailed` | The PDF is missing or Tesseract raised; the document gets no record (fail closed) |

## Flags

`--doc SLUG`, `--force`, `--verbose`, `--output`.
