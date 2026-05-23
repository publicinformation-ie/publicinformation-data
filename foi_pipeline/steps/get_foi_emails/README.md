# get_foi_emails

Extracts the FOI contact email address from each body's FOI page.

## What it does

For each reachable FOI page:
1. Fetches the page HTML.
2. Collects all email addresses from `mailto:` links and from regex matches in the visible text.
3. Applies a selection strategy:
   - If exactly one email is found, uses it.
   - If multiple emails are found, prefers any address containing `foi` or `freedom`.
   - If multiple emails are found but none match the keywords, records `email_status: multiple_found` (no email selected).
   - If no emails are found, records `email_status: not_found`.

Only processes bodies whose FOI page was reachable (`is_reachable: true` from the previous step).

Supports **incremental resumption**.

## Input

`check_foi_pages/output.json` (only `is_reachable: true` records are processed)

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `foi_page_url` | The FOI page that was scraped |
| `foi_email` | Extracted email address, or `null` |
| `email_status` | `found`, `not_found`, `invalid`, or `multiple_found` |

## Notable files

- `errors.json` — network errors fetching FOI pages.
- `output_schema.json` — JSON Schema for the output format.
