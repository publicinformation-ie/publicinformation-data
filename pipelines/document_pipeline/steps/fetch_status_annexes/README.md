# fetch_status_annexes

Downloads each report's declared `status_annex` workbook (xlsx) from `documents.yml`.

- Validates the **payload** (zip magic `PK\x03\x04`, then openpyxl `read_only` load), not the Content-Type; `application/octet-stream` is fine.
- Errors per document, no record written, so the document is retried: `AnnexUnreachable`, `AnnexWrongFormat` (expected and received), `AnnexUnreadable`.
- Listed in `always_run`: a record is reused only while its `status_annex` (url, format) still matches `documents.yml`; otherwise it is refetched.
- Output: `{doc_slug, status_annex, annex_path, source_sha256, bytes, sheet_names, fetched_at}`.
