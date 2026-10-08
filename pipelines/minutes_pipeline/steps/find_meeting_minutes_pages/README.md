# find_meeting_minutes_pages

Locates the page(s) that publish meeting minutes for each authority — one per municipal district plus the full council, as applicable. Mirrors `find_disclosure_pages`' override-first / crawl-scoring fallback shape.

## What it does

1. **Override first** — reads the committed `override.json`; any entry keyed by `public_body_id` (+ optional `municipal_district`) wins outright with `source_method: "override"` and no HTTP.
2. **Crawl fallback** — for every (body, district) pair *not* covered by an override, fetches the authority's `official_website_url`, tokenises each link's href + anchor text, and scores candidates against a tiered vocabulary:

   | Signal | Score |
   |---|---|
   | `minutes` + `meeting` | 100 |
   | `minutes` + `district` | 90 |
   | `minutes` (e.g. "Council Minutes") | 80 |
   | `meeting` + `municipal` | 70 |
   | `meeting` (bare, e.g. "Meeting stuff") | 50 |
   | any `NEGATIVE_TOKENS` except `agenda(s)` (login, annual, report, …) | 0 (disqualify) |
   | `agenda(s)` without a `minutes` token | 0 (disqualify) |

   The highest-scoring link wins only if it reaches `ACCEPT_THRESHOLD = 60`. An explicit minutes link always clears it — including combined "Minutes & Agendas" listings (`agenda` disqualifies only agenda-only pages); a bare generic meeting page (50) is rejected — a `municipal`-district meeting page (70) is kept. No qualifying link → an error entry is written (never a silent skip).

## Input

- `find_local_authorities/output.json` (generated upstream)
- `override.json` (committed, this step's directory)

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Authority body id |
| `municipal_district` | District name, or `null` for the full-council page |
| `minutes_page_url` | URL of the minutes page |
| `source_method` | `"override"` or `"crawl"` |
| `overridden` | `true` only on override records |
| `walk` | Optional, override records only: listing-walk config passed through to `find_minutes_files` (`detail_url`, `detail_text`, optional `file_text` (regex on PDF link text, to keep one body's minutes off a page that bundles several), optional `html_selector` (CSS selector; emit HTML minutes records per detail page instead of PDFs), `paginate`, `max_listing_pages`) |

## Notable files

- `override.json` — committed, hand-authored. Never overwritten by automation.
- `errors.json` — crawl failures and below-threshold outcomes, keyed by body/district.
- `output_schema.json` — JSON Schema for the output format.
