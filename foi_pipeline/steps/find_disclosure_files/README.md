# find_disclosure_files

Crawls each body's disclosure log page and collects links to downloadable disclosure log files (PDF, XLSX, XLS).

## What it does

For each body:
1. Fetches the disclosure page.
2. Scans all links for files with `.pdf`, `.xlsx`, or `.xls` extensions.
3. Also follows links whose anchor text looks like a year (e.g. "2023", "2022") — these often lead to per-year sub-pages that contain the actual file links. Sub-pages are crawled one level deep.
4. Filters out false positives: links whose URL or anchor text matches "annual report" or "protected disclosure".

Produces one output record per file found (so a body with 5 disclosure files produces 5 records).

Supports **incremental resumption** and propagates upstream `dirty_ids`.

## Input

`find_disclosure_pages/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `disclosure_page_url` | Page the file was found on |
| `file_url` | Direct URL to the disclosure log file |
| `file_type` | `pdf`, `xlsx`, or `xls` |
| `link_text` | Anchor text of the link pointing to this file (empty string for direct-file URLs) |

## Notable files

- `errors.json` — network errors fetching disclosure pages.
- `output_schema.json` — JSON Schema for the output format.
