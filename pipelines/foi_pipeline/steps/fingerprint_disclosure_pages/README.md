# fingerprint_disclosure_pages

Fetches every disclosure log page on each run and hashes the set of file links found. Bodies whose hash changed since the last run are written to `dirty_ids.json`, which tells `find_disclosure_files` which pages to re-crawl.

## What it does

For each body:
1. Fetches the disclosure page.
2. Calls `find_file_links` (shared with `find_disclosure_files`) to extract file links.
3. Computes SHA-256 of the sorted, deduplicated set of file URLs.
4. Compares to the hash stored from the previous run.
5. If changed (or new body): adds the body ID to the dirty set.
6. On fetch error: preserves the previous hash and does **not** mark the body dirty.

## Input

`find_disclosure_pages/output.json`

## Output

`output.json` — one record per body:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `disclosure_page_url` | Page that was fingerprinted |
| `page_hash` | `sha256-<hex>` of the sorted file URL set |
| `file_count` | Number of file links found (0 on error or no files) |

`dirty_ids.json` — sorted list of body IDs whose pages changed. Consumed by `find_disclosure_files` via `IncrementalWriter`'s `upstream_dirty_path`.

## Notable files

- `errors.json` — network errors fetching disclosure pages.
- `dirty_ids.json` — body IDs to re-process downstream.
- `output_schema.json` — JSON Schema for the output format.
