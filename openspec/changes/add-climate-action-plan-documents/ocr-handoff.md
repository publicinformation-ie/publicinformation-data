# Handoff: OCR for two image-only Climate Action Plan progress reports

## Status
Two curated documents are in `documents.yml` but are NOT published. They appear under `public/documents/index.json` `failed` with `reason: not_publishable`:

| doc_slug | gap pages (no extractable text) | pages |
|---|---|---|
| `climate-action-plan-2025-q1-progress-report` | 1, 20, 24 | ? (see PDF) |
| `climate-action-plan-2025-q4-progress-report` | 1, 4, 6, 7, 9, 10, 11, 12, 13, 15, 16, 18, 19, 20, 21, 23 | ? |

Cause: those pages are full-page raster images. `extract_pages` finds zero text blocks and zero figures, so `assemble_sections` reports a coverage gap and `publish_bundles` withholds the document.

## What has been established
- tesseract / pytesseract (installed locally) shows the gap pages are REAL content: narrative, KPI charts and action tables.
- Do NOT add these pages to `steps/assemble_sections/override.json` (furniture). That would silently drop real content and violates the repo's fail-closed principle.
- No actions or statuses are extracted from these reports (`policy_role: progress-report`, `status_source: annex`), so OCR only affects the bundled text/sections.

## Suggested approach
1. Look at how `minutes_pipeline/steps/ocr_minutes_files` does OCR and whether it can be reused or shared in `src/lib`.
2. Add an OCR fallback in `document_pipeline/steps/extract_pages` for pages with no text layer. Mark OCR-derived blocks (e.g. `source: "ocr"`) so downstream steps and the bundle can say the text is machine-read. Make it deterministic; log low-confidence pages to `errors.json` for human review rather than guessing.
3. Re-run scoped: `cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error --doc <slug>`. Snapshot `steps/*/errors.json` after each run (it is overwritten).
4. Do NOT use a scoped run for the final publish: a scoped `publish_bundles` deletes other documents' bundles. Revert experiments with `git checkout -- public/documents && git clean -fdq public/documents`.
5. Check that existing bundles stay byte-identical unless intentionally republished (see below).

## Gotchas
- Existing published bundles were built before the 2026-10-17 TOC-name detection and 2026-11-07 text-repair commits. A full pipeline run changes 12 of them. That republish should be its own reviewed commit, so splice rather than accept it wholesale.
- Index changes must land in the same commit as the `documents.yml` change (`tests/test_documents_dataset.py` asserts `published ∪ failed == curated`).
- Hand-stamp `dct:modified` in `public/catalog/dataset-documents.ttl` and add a `public/CHANGELOG.md` entry when the bundles are published. No `owl:versionInfo` change needed.
- curl to gov.ie is blocked (403), but `assets.gov.ie` PDFs download with `curl -A "Mozilla/5.0"`.
- Related and similarly withheld: `climate-action-plan-2023` (structure detection collapses it to two chapters; see the comment in `documents.yml`).
