# fetch_grant_documents

Reads the committed publication list and fetches each document into a local
cache.

## What it does

1. Loads `publications.json` (the only ingestion source — see below).
2. For each document, computes the cache file from the document URL:
   `pipelines/activetravel_pipeline/cache/<first 16 hex of sha256(url)>.pdf`
   (git-ignored).
3. If the file exists and is non-empty, reads it and makes no network request.
   Otherwise downloads it once and writes it there.
4. Records the observed SHA-256 and byte size, and passes the cache path to the
   extraction step.

`--doc <document_id>` fetches only that document.

## Output

```json
{
  "metadata": {"step": "...", "documents": 6, "available": 6},
  "documents": [
    {"document_id": "nta-active-travel-2026", "year": 2026,
     "kinds": ["project_table", "recipient_summary"],
     "publication_page": "https://www.nationaltransport.ie/…",
     "url": "https://www.nationaltransport.ie/…pdf",
     "title": "Active Travel Investment Grants: 2026 Allocations",
     "cache_file": "cache/5ff8df0349faf01f.pdf",
     "available": true, "source": "cache", "sha256": "…", "byte_size": 530438}
  ]
}
```

A document that is neither cached nor reachable is listed with
`available: false` and an `error`, and an error of type `DocumentFetchError`
names it. No records are ingested from it.

## Committed input: `publications.json`

One entry per year, each with its publication page and one or more documents:

```json
{"year": 2025,
 "publication_page": "https://www.nationaltransport.ie/news/active-travel-investment-grants-2025-allocations/",
 "documents": [{"document_id": "nta-active-travel-2025",
                "url": "…/Full-Allocations-Table-130125.pdf",
                "kinds": ["project_table", "recipient_summary"]}]}
```

- `kinds` is a list because one PDF can carry both the project tables and the
  per-recipient summary in its front matter (2025 and 2026 do).
- `programme_summary` marks the 2022 Annex 1, which is cached but never
  extracted as project rows.
- Adding a year is an edit here, with no code change. The allocation year always
  comes from this file, never from page text.

## Why the digest is recorded, not pinned

The publisher reissues these PDFs from time to time. A pinned checksum would
block the annual run behind a code change, so the observed digest is recorded in
this step's output and on every published record instead: a reissue then shows
up as a digest change in the run output and in the published data diff, which is
the review point before merging. `source_document_sha256` is what makes a record
traceable to the exact issue it came from.

`publications.json` is validated on load: duplicate years, duplicate document
ids, reused URLs, an unknown kind, or a year with no `project_table` document is
process-fatal rather than silently skipped.
