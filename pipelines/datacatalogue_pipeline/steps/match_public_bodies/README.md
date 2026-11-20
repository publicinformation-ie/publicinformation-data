# match_public_bodies

Fuzzy-matches each organisation's `datacatalogue_name` against the canonical public-body list using `src/lib/body_matching.py` (same normalisation and `MATCH_THRESHOLD` as the other link pipelines).

- **Input:** `fetch_datacatalogue_orgs/output.json`.
- **Candidates:** `pipelines/cso_pipeline/steps/resolve_website_urls/output.json` (must exist; run `cso_pipeline` through `resolve_website_urls` first).
- **Output:** `output.json` (each record plus `public_body_id`, null when below threshold) and `match_log.json` (normalised name, best candidate id and score for every organisation).
- **Resume:** keyed on `datacatalogue_slug` via `IncrementalWriter`, so an interrupted run continues where it stopped.
- Unmatched organisations are expected and never fail the step.
