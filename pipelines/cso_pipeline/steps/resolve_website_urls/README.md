# resolve_website_urls

Re-checks each public body's website URL and resolves any remaining gov.ie stub portal pages to the body's real external website.

## What it does

Some bodies are listed on gov.ie with a page that only says "There is a separate website for [Body Name]" and links out to the real site. `find_public_bodies` handles most of these, but this step provides a second pass in case any stubs were missed (e.g. if the initial fetch timed out).

For each body:
1. Fetches `official_website_url` with redirect-following enabled.
2. If the response HTML contains the stub marker text, extracts the outbound link and replaces the URL.
3. Skips bodies marked `not_subject_to_foi`.

Supports **incremental resumption**: already-processed body IDs (tracked via `IncrementalWriter`) are skipped on re-run.

## Input

`find_public_bodies/output.json`

## Output

`output.json` — same structure as the input but with `official_website_url` updated where stubs were resolved.

## Notable files

- `errors.json` — network or parsing errors per body.
- `output_schema.json` — JSON Schema for the output format.
