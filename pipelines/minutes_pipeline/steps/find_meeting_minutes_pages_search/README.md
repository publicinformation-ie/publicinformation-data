# find_meeting_minutes_pages_search

Searches for meeting minutes pages for bodies where crawl failed, using a single batched Apify run.

## What it does

1. **Pass-through** — records from `find_meeting_minutes_pages/output.json` (crawl successes, incl. multi-record bodies like Meath) are copied unchanged, keyed on `minutes_page_url`.
2. **Batch search** — for each failed body in `find_meeting_minutes_pages/errors.json` (one search per body; bodies already holding a page record are skipped), builds the query `site:<domain> <name> council meeting minutes` (names from `find_local_authorities/output.json`) and submits all queries in a single Apify `google-search-scraper` Actor run.
3. **URL picking** — each body's results are scored with the crawl step's own tiered vocabulary (`minutes`+`meeting` 100 … `meeting` bare 50, threshold 60; `/ga/` and unsafe URLs skipped). No gov.ie path-prefix rule — every council has its own domain and `site:` already constrains results.
4. **Output** — records with `source_method: "crawl"`/`"override"` (pass-through) or `"apify"` (search-found, `municipal_district: null`); bodies still not found go to `errors.json` (`MinutesPageNotFound`); bodies with no usable website go to `errors.json` (`MissingWebsiteUrl`) with no Apify call.

Supports **incremental resumption**, **`--force`**, and **`--public-body`**.

## Environment

`APIFY_TOKEN` — required whenever at least one body needs searching (fully-passing-through runs make no Apify call). Set to your Apify API token. Raises clearly if missing.

## Input

`find_meeting_minutes_pages/output.json` (crawl successes, via `--input`)
`find_meeting_minutes_pages/errors.json` (crawl failures, read directly from sibling step directory)
`find_local_authorities/output.json` (body names/websites for query building, read directly from sibling step directory)

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Authority body id |
| `municipal_district` | District name, or `null` (all `apify` records are `null` — per-body granularity) |
| `minutes_page_url` | Discovered minutes page URL |
| `source_method` | `override`/`crawl` (pass-through), `apify` (search-found), or `manual` (override) |
| `overridden` | `true` only on override records |

## Notable files

- `errors.json` — `MinutesPageNotFound` (search misses) and `MissingWebsiteUrl` (null/invalid website, no search attempted).
- `override.json` — manually verified minutes page URLs that take precedence over automated results.
- `output_schema.json` — JSON Schema for the output format.

## Relationship to `find_meeting_minutes_pages`

`find_meeting_minutes_pages` performs override-first / crawl-only discovery. This step extends coverage by searching for bodies that crawl could not resolve. Downstream steps read from this step's `output.json`, not `find_meeting_minutes_pages/output.json`.

## Limitation

Per-body granularity: if a body holds some district pages but is missing others, this step does not backfill the missing districts (the body is treated as resolved). Upgrade to per-(body, district) queries if district-level gaps appear.
