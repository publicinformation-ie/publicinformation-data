# check_foi_pages

Verifies that each discovered FOI page URL is currently reachable by performing a live HTTP check.

## What it does

For each body with a discovered `foi_page_url`, performs a GET request (following redirects) and records:
- `is_reachable` — `true` if the response is 2xx.
- `http_status` — the final HTTP status code (or `null` on connection error).
- `checked_at` — ISO 8601 timestamp of the check.

Bodies whose FOI page is unreachable are still included in the output (with `is_reachable: false`) so that downstream steps can filter them.

This step is intentionally narrow: it only checks reachability. Content validation (e.g. confirming the page actually contains FOI content) is out of scope here.

Supports **incremental resumption**.

## Input

`find_foi_pages/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Passes through all fields from the input and adds:

| Field | Description |
|---|---|
| `is_reachable` | Whether the FOI page returned a successful HTTP response |
| `http_status` | HTTP status code |
| `checked_at` | Timestamp of the check |

## Notable files

- `errors.json` — connection or timeout errors per body.
- `output_schema.json` — JSON Schema for the output format.
