# Pipeline Steps

The authoritative step order is defined in [`../pipeline.json`](../pipeline.json). Steps run sequentially. Each step writes its output to `<step>/output.json` for the next step to consume.

## Step sequence

| # | Step | What it does |
|---|---|---|
| 1 | [`find_public_bodies`](find_public_bodies/) | Scrapes gov.ie to build the master list of Irish public bodies. It resolves stub portal URLs to real homepages. |
| 2 | [`find_public_bodies_subject_to_foi`](find_public_bodies_subject_to_foi/) | Filters the master list to bodies without an `exclusion_reason`. These are the bodies that FOI legislation actually covers. |
| 3 | [`resolve_website_urls`](../../cso_pipeline/steps/resolve_website_urls/) | Resolves each body's website URL, including gov.ie stub pages, and returns the first candidate URL that fetches successfully. |
| 4 | [`validate_websites`](validate_websites/) | Sends an HTTP request to each public body's website and records reachability and HTTP status. |
| 5 | [`find_foi_pages`](find_foi_pages/) | Crawls each reachable website to locate its FOI page, using a homepage crawl, then a secondary crawl. |
| 6 | [`find_foi_pages_search`](find_foi_pages_search/) | Searches for FOI pages for bodies where the crawl failed, using a single batched Apify run (`APIFY_TOKEN` required). |
| 7 | [`check_foi_pages`](check_foi_pages/) | Sends an HTTP request to each discovered FOI page URL and makes sure that it is still reachable. |
| 8 | [`get_foi_emails`](get_foi_emails/) | Scrapes each FOI page and extracts the FOI contact email address. |
| 9 | [`find_disclosure_pages`](find_disclosure_pages/) | Locates the disclosure log page for each body using domain-specific rules or a crawl fallback. |
| 10 | [`find_disclosure_files`](find_disclosure_files/) | Crawls each disclosure log page and collects links to PDF/XLSX/XLS files. |
| 11 | [`transform_disclosure_files`](transform_disclosure_files/) | Downloads spreadsheet and PDF files and converts them into JSON row arrays. PDF tables use structure-based extraction, and the Mistral OCR cache is one scored candidate (live OCR requires opt-in via `--allow-paid-ocr`). |
| 11a | [`assess_table_structure`](assess_table_structure/) | Fail-closed gate: it scores PDF table structure and empties structurally unreliable PDFs (logged as `TableStructureUnreliable`). |
| 12 | [`normalize_disclosure_cells`](normalize_disclosure_cells/) | Normalizes string cell values in extracted disclosure log data (removes CID artifacts, normalizes whitespace). |
| 13 | [`extract_disclosures_detect_header_row`](extract_disclosures_detect_header_row/) | Detects which spreadsheet row is the header using a 2-non-empty-cell heuristic. |
| 14 | [`extract_disclosures_normalize_header`](extract_disclosures_normalize_header/) | Repairs null cells in the detected header row by merging continuation rows and forward-filling merged-cell spans. |
| 15 | [`extract_disclosures_normalize_rows`](extract_disclosures_normalize_rows/) | Normalizes all date values in disclosure rows to ISO 8601 format (YYYY-MM-DD), replacing unparseable values with null. |
| 16 | [`extract_disclosures_canonicalize`](extract_disclosures_canonicalize/) | Maps raw column headers to canonical field names and emits flat FOI request records. |
| 17 | [`extract_disclosures_canonicalize_rows`](extract_disclosures_canonicalize_rows/) | Normalizes decision_status field values to a canonical set of seven status values. |
| 18 | [`extract_disclosures_deduplicate`](extract_disclosures_deduplicate/) | Removes duplicate FOI records by treating `foi_reference_id` as a unique identifier per public body. |
| 19 | [`export_status`](export_status/) | Fan-in step: merges all step outputs into a unified per-body status report and writes the public JSON files consumed by the website. |
| 20 | [`generate_topics`](generate_topics/) | Matches canonical FOI records to keyword-defined topics and writes `public/topics.json`. |
| 21 | [`db_upload`](db_upload/) | Clears the six pipeline-data tables in the libSQL database and re-populates them from all upstream step outputs. |

> Stub: [`extract_disclosures`](extract_disclosures/) is a placeholder step (not yet implemented) for future PDF extraction. It currently produces no output.

## Common files in each step directory

| File | Purpose |
|---|---|
| `process.py` | Entry point for the step |
| `output.json` | Step output, consumed by the next step |
| `errors.json` | Per-record errors (non-fatal warnings and failures) |
| `override.json` | Manually curated records that are never overwritten by automation |
| `dirty_ids.json` | Body IDs whose upstream data changed. The file signals downstream steps to reprocess those records |
| `pipeline-status.json` | Execution metadata written by the process script |
| `output_schema.json` | JSON Schema for validating `output.json` and `override.json` |

See the parent [`AGENTS.md`](../AGENTS.md) for how to run the pipeline, the override system, troubleshooting guidance, and the `--public-body` flag.

## Scoping a step to one public body

Every step accepts `--public-body <ID>` to reprocess only that body while leaving all other bodies byte-for-byte unchanged. Three implementation shapes handle this:

| Shape | Steps | Mechanism |
|-------|-------|-----------|
| §a evict | `resolve_website_urls`, `validate_websites`, `find_foi_pages`, `find_foi_pages_search`, `check_foi_pages`, `get_foi_emails`, `find_disclosure_pages`, `find_disclosure_files`, `transform_disclosure_files`, `assess_table_structure`, `normalize_disclosure_cells`, `extract_disclosures_detect_header_row`, `extract_disclosures_normalize_header` | `IncrementalWriter(target_public_body=ID)` evicts the body on load and marks it dirty, so downstream steps cascade automatically. |
| §b merge-back | `extract_disclosures_normalize_rows`, `extract_disclosures_canonicalize`, `extract_disclosures_canonicalize_rows`, `extract_disclosures_deduplicate` | Filters input to the target body, processes it, then merges the new records back over the existing output (replacing only that body's rows). |
| §c filter-reads | `export_status`, `generate_topics`, `db_upload` | Aggregator/publisher steps filter every consumed read to the target body. Output is derived or best-effort, so run a full pipeline before publishing. |

`find_public_bodies` is confirm-only when scoped: it makes sure that the body exists and leaves its output untouched.
