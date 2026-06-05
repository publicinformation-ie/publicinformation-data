# Pipeline Steps

The authoritative step order is defined in [`../pipeline.json`](../pipeline.json). Steps run sequentially; each writes its output to `<step>/output.json` for the next step to consume.

## Step sequence

| # | Step | What it does |
|---|---|---|
| 1 | [`find_public_bodies`](find_public_bodies/) | Scrapes gov.ie to build the master list of Irish public bodies, resolving stub portal URLs to real homepages. |
| 2 | [`resolve_website_urls`](resolve_website_urls/) | Second-pass resolution of any remaining gov.ie stub pages that weren't resolved in step 1. |
| 3 | [`validate_websites`](validate_websites/) | HTTP-checks each public body's website and records reachability and HTTP status. |
| 4 | [`find_foi_pages`](find_foi_pages/) | Crawls each reachable website to locate its FOI page using homepage crawl → secondary crawl. |
| 5 | [`find_foi_pages_search`](find_foi_pages_search/) | Searches for FOI pages for bodies where crawl failed, using a single batched Apify run (`APIFY_TOKEN` required). |
| 6 | [`check_foi_pages`](check_foi_pages/) | HTTP-checks each discovered FOI page URL to confirm it is still reachable. |
| 7 | [`get_foi_emails`](get_foi_emails/) | Scrapes each FOI page and extracts the FOI contact email address. |
| 8 | [`find_disclosure_pages`](find_disclosure_pages/) | Locates the disclosure log page for each body using domain-specific rules or crawl fallback. |
| 9 | [`find_disclosure_files`](find_disclosure_files/) | Crawls each disclosure log page and collects links to PDF/XLSX/XLS files. |
| 10 | [`transform_disclosure_files`](transform_disclosure_files/) | Downloads spreadsheet files and converts them into JSON row arrays; PDFs are passed through unmodified. |
| 11 | [`normalize_disclosure_cells`](normalize_disclosure_cells/) | Normalizes string cell values in extracted disclosure log data (removes CID artifacts, normalizes whitespace). |
| 12 | [`extract_disclosures_detect_header_row`](extract_disclosures_detect_header_row/) | Detects which spreadsheet row is the header using a 2-non-empty-cell heuristic. |
| 13 | [`extract_disclosures_canonicalize`](extract_disclosures_canonicalize/) | Maps raw column headers to canonical field names and emits flat FOI request records. |
| 14 | [`extract_disclosures_canonicalize_rows`](extract_disclosures_canonicalize_rows/) | Normalizes decision_status field values to a canonical set of seven status values. |
| 15 | [`extract_disclosures_deduplicate`](extract_disclosures_deduplicate/) | Removes duplicate FOI records by treating `foi_reference_id` as a unique identifier per public body. |
| 16 | [`export_status`](export_status/) | Fan-in step: merges all step outputs into a unified per-body status report and writes the public JSON files consumed by the website. |
| 17 | [`generate_topics`](generate_topics/) | Matches canonical FOI records to keyword-defined topics and writes `public/topics.json`. |
| 18 | [`db_upload`](db_upload/) | Clears the six pipeline-data tables in the libSQL database and re-populates them from all upstream step outputs. |

> **Stub:** [`extract_disclosures`](extract_disclosures/) is a placeholder step (not yet implemented) for future PDF extraction. It currently produces no output.

## Common files in each step directory

| File | Purpose |
|---|---|
| `process.py` | Entry point for the step |
| `output.json` | Step output, consumed by the next step |
| `errors.json` | Per-record errors (non-fatal warnings and failures) |
| `override.json` | Manually curated records that are never overwritten by automation |
| `dirty_ids.json` | Body IDs whose upstream data changed; signals downstream steps to reprocess those records |
| `pipeline-status.json` | Execution metadata written by the process script |
| `output_schema.json` | JSON Schema for validating `output.json` and `override.json` |

See the parent [`AGENTS.md`](../AGENTS.md) for how to run the pipeline, the override system, troubleshooting guidance, and the `--public-body` flag.

## Scoping a step to one public body

Every step accepts `--public-body <ID>` to reprocess only that body while leaving all other bodies byte-for-byte unchanged. Three implementation shapes handle this:

| Shape | Steps | Mechanism |
|-------|-------|-----------|
| §a evict | `resolve_website_urls`, `validate_websites`, `find_foi_pages`, `find_foi_pages_search`, `check_foi_pages`, `get_foi_emails`, `find_disclosure_pages`, `find_disclosure_files`, `transform_disclosure_files`, `normalize_disclosure_cells`, `extract_disclosures_detect_header_row` | `IncrementalWriter(target_public_body=ID)` evicts the body on load and marks it dirty so downstream steps cascade automatically. |
| §b merge-back | `extract_disclosures_canonicalize`, `extract_disclosures_canonicalize_rows`, `extract_disclosures_deduplicate` | Filters input to the target body, processes it, then merges the new records back over the existing output (replacing only that body's rows). |
| §c filter-reads | `export_status`, `generate_topics`, `db_upload` | Aggregator/publisher steps filter every consumed read to the target body. Output is derived/best-effort — run a full pipeline before publishing. |

`find_public_bodies` is confirm-only when scoped: it verifies the body exists and leaves its output untouched.
