# find_disclosure_pages

Locates the FOI disclosure log page for each public body — the page that lists what FOI requests have been released.

## What it does

For each body, tries two strategies in order:

1. **Domain-specific logic** (`domains.py`) — hardcoded rules for known site structures (e.g. gov.ie path patterns). Returns a URL directly without an HTTP request if the domain is recognised.
2. **Crawl fallback** — fetches the FOI page and scans for links whose href or anchor text contains disclosure keywords (`disclosure`, `log`, `request`). Excludes false positives: annual reports and protected disclosures pages.

If neither strategy finds a distinct disclosure page, the FOI page URL itself is used as the disclosure page (common when a body publishes its log directly on the FOI page).

Supports **incremental resumption** and propagates upstream `dirty_ids` to invalidate stale downstream results when a body's FOI page changes.

## Input

`get_foi_emails/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `foi_page_url` | The body's FOI page |
| `disclosure_page_url` | The discovered disclosure log page |

## Notable files

- `domains.py` — domain-specific URL resolution rules.
- `override.json` — manually verified disclosure page URLs.
- `errors.json` — network or validation errors.
- `output_schema.json` — JSON Schema for the output format.
