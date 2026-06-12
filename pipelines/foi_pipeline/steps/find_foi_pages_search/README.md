# find_foi_pages_search

Searches for FOI pages for bodies where crawl failed, using a single batched Apify run.

## What it does

1. **Pass-through** — records from `find_foi_pages/output.json` (crawl successes) are copied unchanged.
2. **Batch search** — for each body in `find_foi_pages/errors.json`, builds the query `site:<domain> <name> freedom of information` and submits all queries in a single Apify `google-search-scraper` Actor run.
3. **URL filtering** — for each body, picks the first search result whose URL path contains an FOI keyword (`foi`, `freedom-of-information`, etc.). gov.ie bodies also require the result path to start with the body's path prefix.
4. **Output** — records with `source_method: "crawl"` (pass-through) or `source_method: "apify"` (search-found); bodies still not found go to `errors.json`.

Supports **incremental resumption**, **`--force`**, and **`--public-body`**.

## Environment

`APIFY_TOKEN` — required. Set to your Apify API token. Raises clearly if missing.

## Input

`find_foi_pages/output.json` (crawl successes, via `--input`)
`find_foi_pages/errors.json` (crawl failures, read directly from sibling step directory)

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `official_website_url` | Body's website |
| `foi_page_url` | Discovered FOI page URL |
| `source_method` | `crawl` (pass-through) or `apify` (search-found) or `manual` (override) |

## Notable files

- `errors.json` — bodies where neither crawl nor Apify search found an FOI page.
- `override.json` — manually verified FOI page URLs that take precedence over automated results.
- `output_schema.json` — JSON Schema for the output format.

## Relationship to `find_foi_pages`

`find_foi_pages` performs crawl-only discovery. This step extends coverage by searching for bodies that crawl could not resolve. Downstream steps read from this step's `output.json`, not `find_foi_pages/output.json`.
