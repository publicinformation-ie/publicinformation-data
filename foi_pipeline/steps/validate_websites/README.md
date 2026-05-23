# validate_websites

HTTP-checks each public body's website to confirm it is reachable and records the response status.

## What it does

For each body, performs a GET request (following redirects) and records:
- `is_reachable` — `true` if the response status is 2xx.
- `http_status` — the final HTTP status code (or `null` on connection error).
- `checked_at` — ISO 8601 timestamp of the check.

Bodies whose websites are unreachable are still written to output (with `is_reachable: false`) so that the next step (`find_foi_pages`) can filter them out rather than failing silently.

Supports **incremental resumption**: already-checked body IDs are skipped on re-run.

## Input

`resolve_website_urls/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `official_website_url` | URL that was checked |
| `is_reachable` | Whether the site returned a successful HTTP response |
| `http_status` | HTTP status code |
| `checked_at` | Timestamp of the check |

## Notable files

- `errors.json` — connection or timeout errors (bodies still appear in output with `is_reachable: false`).
- `output_schema.json` — JSON Schema for the output format.
