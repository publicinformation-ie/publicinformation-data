# fetch_pdfs

Downloads (or reuses a cached copy of) each document's source PDF and writes one metadata record per document. First step in `document_pipeline`.

## What it does

For each document in `documents.yml` (via `documents.load_documents()`):

1. If `pdfs/<doc_slug>.pdf` already exists, its sha256 matches the previous run's `source_sha256`, and a conditional `HEAD` request confirms the remote is unchanged, reuses the cached file and record as-is instead of re-downloading. Any ambiguity in that check (no prior record, hash mismatch, failed/inconclusive `HEAD`) re-downloads — correctness over cleverness.
2. Otherwise fetches the PDF via `lib.http_utils.fetch` (UA string, SSRF guard, rate limiting, and bot-challenge detection already applied) and streams it to `pdfs/<doc_slug>.pdf`.
3. Validates the downloaded content actually is a PDF (magic-bytes check), then opens it with `pymupdf` to record `page_count` and `encrypted`, closing the document immediately — this step does not interpret PDF content beyond that.

None of the four failure conditions below is fatal: each logs to `errors.json` and skips that one document, and the step's overall exit code is 0 even if every document fails.

| `error_type` | Cause |
|---|---|
| `FetchFailed` | Network/transport failure, non-2xx, or a non-PDF `Content-Type` header |
| `NotAPdf` | Downloaded bytes do not start with `%PDF-` |
| `EncryptedPdf` | PDF opens but is password-protected |
| `UnreadablePdf` | `pymupdf` cannot open the downloaded file |

Supports **incremental resumption** via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`).

## Input

`documents.yml`, via `documents.load_documents()` (this pipeline's only hand-authored input — no upstream step).

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, from `documents.yml` |
| `title`, `url`, `publisher`, `public_body_id`, `published_date` | Carried through from `documents.yml` |
| `pdf_path` | Path to the cached PDF, relative to this step's directory (resolve downstream as `Path(fetch_pdfs_dir) / record["pdf_path"]`) |
| `source_sha256` | sha256 of the downloaded bytes |
| `bytes` | Size of the downloaded file |
| `page_count` | From `pymupdf` |
| `encrypted` | From `pymupdf` (`needs_pass` or `is_encrypted`) |
| `fetched_at` | UTC ISO timestamp of the download (unchanged on a cache hit) |

Also produces `pdfs/<doc_slug>.pdf` for each successfully-fetched document.

## Notable files

- `errors.json` — one entry per skipped document; see the `error_type` table above. Truncated to `[]` at the start of every run.
- `pdfs/` — cached source PDFs, one per successfully-fetched `doc_slug`.

## Flags

- `--local-pdf SLUG=PATH` — repeatable; substitutes a local file for `SLUG`'s download instead of fetching its `url`. Test-only escape hatch so end-to-end tests never touch the network. Works because `download()` also accepts `file://` URLs, which `documents.load_documents()` itself rejects in `documents.yml` — this is the sanctioned way in.
