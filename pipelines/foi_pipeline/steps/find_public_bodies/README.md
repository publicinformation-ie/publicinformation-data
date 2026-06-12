# find_public_bodies

First step in the pipeline. Scrapes [gov.ie/en/departments/](https://www.gov.ie/en/departments/) to build the master list of Irish public bodies subject to FOI.

## What it does

1. Parses the departments page and collects all links from the `#departments`, `#agencies`, and `#local-authorities` sections.
2. For any body whose URL still points to a gov.ie stub page (i.e. the body has its own external site), resolves the real homepage URL by following the "there is a separate website for…" link.
3. Assigns each body a stable numeric `public_body_id` and initialises a `status` object (all fields `not_attempted`) that downstream steps progressively fill in.
4. Skips a small hardcoded blocklist of gov.ie entries that are not subject to FOI (e.g. Coillte, Criminal Assets Bureau).

Homepage resolution is parallelised with a `ThreadPoolExecutor` (10 workers) to keep the startup cost manageable.

## Output

`output.json` — `{ metadata, public_bodies: [...] }`. Each public body has:

| Field | Description |
|---|---|
| `public_body_id` | Stable integer ID (starts at 1001) |
| `name` | Display name as it appears on gov.ie |
| `official_website_url` | Resolved homepage URL |
| `category` | `government department`, `public service body`, or `local authority` |
| `status` | Per-step status object initialised to `not_attempted` |
| `not_subject_to_foi` | `true` if blocklisted (field absent otherwise) |

## Notable files

- `errors.json` — any fatal error fetching the source page.
- `output_schema.json` — JSON Schema for the output format.
