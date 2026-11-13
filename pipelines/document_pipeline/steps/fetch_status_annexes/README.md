# fetch_status_annexes

Downloads each report's declared `status_annex` workbook (xlsx) from `documents.yml`.

- Validates the **payload** (zip magic `PK\x03\x04`, then openpyxl `read_only` load), not the Content-Type; `application/octet-stream` is fine.
- Errors per document, no record written, so the document is retried: `AnnexUnreachable`, `AnnexWrongFormat` (expected and received), `AnnexChecksumMismatch` (declared and observed sha256), `AnnexUnreadable`.
- Listed in `always_run`: a record is reused only while its `status_annex` (url, format, sha256) still matches `documents.yml`; otherwise it is refetched.
- `annexes/` is a **git-ignored download cache, not committed data**. Each annex is declared by `url` + `sha256` in `documents.yml`; a cached file with the declared checksum is reused with no network request, anything else is downloaded and verified. To accept a changed upstream file, update the declared `sha256` (a deliberate curation edit).
- Output: `{doc_slug, status_annex, annex_path, source_sha256, bytes, sheet_names, fetched_at}`.
