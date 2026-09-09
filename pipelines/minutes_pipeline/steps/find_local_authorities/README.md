# find_local_authorities

Joins the committed hand-authored list of the 31 Irish local authorities against the CSO register output to emit one enriched record per authority. This is the pipeline's `body_list_step` (the list `--public-body` validates against).

## What it does

1. Reads the committed `local_authorities.json` name list (the source of truth for *which* bodies are local authorities — never a naive "council" name predicate, which would wrongly capture bodies like `Dublin City Council Culture Company CLG`).
2. Joins each name by exact match to `resolve_website_urls/output.json`, attaching the CSO `public_body_id` and `official_website_url`.
3. Emits one record per authority carrying its slug and (for Meath) its municipal districts.
4. **Fails closed:** any committed name missing from the CSO output is written to `errors.json` (`UnmatchedAuthorityName`) and the step exits non-zero — a rename/removal needs human attention, it is never silently dropped.

## Input

- `local_authorities.json` (committed, this step's directory)
- `pipelines/cso_pipeline/steps/resolve_website_urls/output.json` (generated upstream)

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | CSO body identifier |
| `name` | Authority name (exactly as in the CSO output) |
| `slug` | Stable URL/path slug for the authority |
| `official_website_url` | Authority website (may be `null`) |
| `municipal_districts` | List of municipal district names (empty for non-MVP bodies) |

## Notable files

- `local_authorities.json` — committed, hand-authored source of truth. Never overwritten by automation.
- `errors.json` — unmatched committed authority names (fatal).
- `output_schema.json` — JSON Schema for the output format.
