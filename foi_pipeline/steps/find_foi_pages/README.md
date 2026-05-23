# find_foi_pages

Locates the FOI (Freedom of Information) page for each reachable public body website using a three-stage crawl strategy.

## What it does

For each reachable body:

1. **Homepage crawl** — fetches the body's homepage and scans for links whose href or anchor text contains FOI keywords (`foi`, `freedom of information`, etc.). Also checks whether the homepage itself IS the FOI page (URL path contains an FOI keyword and body text mentions FOI).
2. **Secondary crawl** — if no FOI link is found on the homepage, follows a contact/about page link and repeats the scan.
3. **Serper fallback** — if crawling fails, queries the Serper web search API with `site:<domain> <name> freedom of information` and picks the first result whose URL path contains an FOI keyword. Requires `SERPER_API_KEY` to be set.

After all bodies are processed, a **uniqueness pass** drops any automated results where the same `foi_page_url` was matched by multiple bodies (a sign of a false positive). Override records (`overridden: true`) always survive URL collisions.

A URL blocklist (`FOI_PAGE_BLOCKLIST`) prevents matching the generic gov.ie FOI topic page.

Supports **incremental resumption** and **`--retry`** mode (re-processes only bodies listed in `errors.json`).

## Input

`validate_websites/output.json` (only `is_reachable: true` records are processed)

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `official_website_url` | Body's website |
| `foi_page_url` | Discovered FOI page URL |
| `source_method` | `crawl` or `serper` |

## Notable files

- `errors.json` — bodies where no FOI page was found, or where a blocklisted/duplicate URL was detected.
- `override.json` — manually verified FOI page URLs that take precedence over automated results.
- `output_schema.json` — JSON Schema for the output format.
