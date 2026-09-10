# transform_minutes_files

Downloads each minutes PDF and extracts prose text for LLM motion extraction, mirroring the `transform_disclosure_files` fetch-then-extract shape with a `key_field="file_url"` incremental writer.

## What it does

1. For each `file_url` from `find_minutes_files`, downloads the PDF.
2. Extracts text with **pdfplumber** (image-only scans yield empty text — they are OCR'd downstream in `ocr_minutes_files`).
3. Emits one record per PDF: all input fields plus `text` (the extracted prose) and `extractor` (`"pdfplumber"`).

The `key_field` is `file_url` so each PDF is processed exactly once across resumable runs.

## Input

- `find_minutes_files/output.json` (generated upstream)

## Output

`output.json` — `{ metadata, results: [...] }`, one record per PDF with the input fields plus:

| Field | Description |
|---|---|
| `text` | Extracted prose text from the PDF |
| `extractor` | `"pdfplumber"` |

## Notable files

- `errors.json` — download/extraction failures per file URL.
- `pdf_cache/` — local cache directory for downloaded PDFs.
