# FOI Page Discovery via Sitemap

**Date:** 2026-04-30
**Status:** Approved

## Problem

`get_foi_pages_for_public_bodies.py` currently finds FOI pages by scanning homepage anchor text for "foi" or "freedom of information". 174 of 286 public bodies have no email or disclosure URL in `public_body_foi_details.csv` because their homepages do not link to their FOI page using those exact words.

Investigation confirmed all sites return HTTP 200 — there is no bot-protection blocking. The issue is purely link discovery.

## Solution

Replace the homepage anchor-text scan with a sitemap-based discovery strategy. The script interface, input/output files, and CSV schema are unchanged.

## Discovery Strategy (per body)

1. Fetch `robots.txt` → extract all `Sitemap:` directive URLs
2. If none found, try `/sitemap.xml` then `/sitemap_index.xml`
3. Attempt to parse the response as XML; if parsing fails (e.g. site returns HTML at that path), treat as "no sitemap"
4. If the sitemap is an index (`<sitemapindex>`), recurse into child `<sitemap>` entries — one level deep, capped at 10 child sitemaps
5. Scan all collected `<loc>` URLs for FOI keywords: `foi`, `freedom-of-information`, `freedom_of_information`
6. Among matches, select the shortest URL path as the canonical FOI page (most root-level)
7. If no usable sitemap or no FOI URL found, write the row with `foi_page_url` blank

## Output Schema

Unchanged from current script:

```
public_body_id, public_body_name, foi_page_url, is_reachable, last_checked, last_modified
```

Field update rules:
- `last_checked` — always set to today's date
- `last_modified` — only updated when `foi_page_url` changes from its previously recorded value
- `is_reachable` — only checked (HEAD/GET) when a `foi_page_url` was found; otherwise left false
- Rows where `last_checked` is recent but `foi_page_url` is blank are the manual review candidates

## Identifying What Needs Manual Review

No extra column or status flag. After running the script, bodies needing attention are those where `last_checked` was updated by this run but `foi_page_url` remains blank. The gap between `last_checked` and `last_modified` makes these visible.

## CLI Interface

Identical to current script:

```bash
python3 get_foi_pages_for_public_bodies.py \
  --input-file public_bodies.csv \
  --output-file public_body_foi_pages.csv \
  [--force-check] \
  [--ignore-robots]
```

- `--force-check` — reprocess all rows, ignoring previous output
- `--ignore-robots` — skip robots.txt disallow checks (sitemap fetching still uses robots.txt for Sitemap: directives)

## Unchanged Behaviour

- SSL fallback (retry without verification on SSLError)
- Rate limiting (0.2s between requests)
- Resume logic (skip bodies already checked today unless `--force-check`)
- robots.txt disallow checking before fetching any page

## Future Fallback (not in scope)

If manual review reveals too many bodies still missing, add Serper.dev `site:<domain> freedom of information` as a fallback step. The API key is already available. This is deferred until the sitemap run completes and the gap is assessed.

## Files Changed

- `scripts/get_foi_pages_for_public_bodies.py` — replaced in-place
