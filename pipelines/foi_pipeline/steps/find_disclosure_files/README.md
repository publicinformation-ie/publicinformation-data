# find_disclosure_files

Crawls each body's disclosure log page and collects links to downloadable disclosure log files (PDF, XLSX, XLS).

## What it does

For each body:
1. Fetches the disclosure page.
2. Scans all links for files with `.pdf`, `.xlsx`, or `.xls` extensions.
3. Also follows links whose anchor text looks like a year (e.g. "2023", "2022") — these often lead to per-year sub-pages that contain the actual file links. Sub-pages are crawled one level deep.
4. Filters out false positives: links whose URL or anchor text matches "annual report" or "protected disclosure".

Produces one output record per file found (so a body with 5 disclosure files produces 5 records).

Supports **incremental resumption** and propagates upstream `dirty_ids`. Bodies with an `override.json` entry are never live-fetched — see `override.json` below.

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

- `override.json` — manually curated file links for bodies whose disclosure page returns a bot-protection challenge instead of real content (see `fingerprint_disclosure_pages`'s `BotChallengeError` handling). Populated by fetching the page with a real browser or a browser-like User-Agent and running the result through this step's own `find_file_links` for consistent filtering. Static snapshot — must be manually refreshed when the source page gets new entries, since these bodies never produce a `dirty_ids` signal.
- `errors.json` — network errors fetching disclosure pages.
- `output_schema.json` — JSON Schema for the output format.
