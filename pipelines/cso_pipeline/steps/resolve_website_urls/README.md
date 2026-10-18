# resolve_website_urls

Resolves each public body's website URL. This is the **only** place in the
pipeline that sets `official_website_url` for bodies the CSO register does not
supply one for, and that value is what the published `website` column is built
from (`find_public_bodies` → `export_status` → `src/lib/publish_public_bodies.py`).

## What it does

For each body, builds an ordered list of candidate URLs and returns the first
one that fetches successfully:

| Priority | Source | Notes |
|---|---|---|
| 1 | `apify_website_url` | Apify search result |
| 2 | `llm_website_url` | Only when `llm_url_type` is `direct` **and** `llm_confidence` is `high` |
| 3 | `official_website_url` | The gov.ie URL matched in `match_gov_urls` |
| 4 | `llm_website_url` | Any other type except `parent` (a parent URL is a different legal entity) |

On success the gov.ie stub page is expanded to the body's real external site via
`resolve_stub_url()`.

### Failure handling

A fetch failure proves only that *this fetch* failed — the host may not exist,
but it may equally be bot-blocked (HTTP 403 / WAF challenge), which is evidence
the site is alive. Therefore:

- A failed candidate does **not** end the search: the next candidate is tried.
- If no candidate resolves, the value the source already carried is left
  untouched (usually `None`) and the body is written to `errors.json` with the
  full attempt list. A failed fetch never nulls a value the body already had.

`errors.json` doubles as this step's retry list (a body listed there is evicted
and re-fetched on the next run), so a candidate failure that was *recovered* by
a lower-priority candidate is deliberately **not** logged as an error.

## Notable files

- `override.json` — hand-confirmed URLs (`"source_method": "manual"`,
  `"overridden": true`). These replace the automated record and are never
  re-fetched. Use this when a candidate is right but unreachable by the crawler
  (e.g. `https://www.hsa.ie/`, `https://www.rsa.ie/` — both serve a WAF
  challenge to non-browser clients), or when a candidate is demonstrably wrong
  (e.g. Forensic Science Ireland's LLM answer, `https://www.fsi.gov.ie`, is a
  domain that does not exist; the real site is `https://forensicscience.ie/`).
  Always look the `public_body_id` up in
  `pipelines/foi_pipeline/steps/find_public_bodies/output.json` — never type it
  from memory.
- `errors.json` — bodies where no candidate could be fetched, with the per-URL
  attempt details.
- `output_schema.json` — output contract (also used to validate `override.json`).