# export_allocations

Emits the flat, publishable allocation records: one record per project
allocation, in the fixed shape `scripts/transform_active_travel_allocations.py`
publishes.

Withholding already happened upstream — this step only decides shape and order,
and records the counts the publisher and the review use.

## The record

| Field | Type | Notes |
|---|---|---|
| `@id` | URI | `…/allocation/<recipient-slug>/<year>/<stream>/<key>` — the grammar in `canonicalize_allocations` |
| `@type` | String | `Allocation` |
| `year` | Integer | from the committed publication list |
| `public_body` | URI or null | the local authority's public-bodies `@id`; null for a non-local-authority recipient |
| `public_body_id` | Integer or null | join key; null for a non-local-authority recipient |
| `recipient_name` | String | as printed |
| `funding_stream` | String | `active_travel` or `other_nta_streams` |
| `project_code` | String | as printed, possibly a placeholder |
| `project_code_provisional` | Boolean | true when the code is a placeholder |
| `project_name` | String | as printed |
| `allocation_eur` | Integer | whole euro, non-negative |
| `source_document_url` | URI | the document the record was read from |
| `source_document_sha256` | String | SHA-256 of that document's bytes |
| `source_page` | Integer | 1-based page |

Both body fields are `null` together or present together; the publisher omits
them for the non-local-authority block rather than publishing empty strings.

## Output

`results` plus metadata: `total_records`, `total_allocations_eur`, and
`counts_by_year` (records, allocations, recipient count, and the totals per
funding stream) — the numbers the dataset README and the review use.

`withheld_rows` and `sections` are carried through from the reconciliation
steps so a single file shows both what was published and what was not.
