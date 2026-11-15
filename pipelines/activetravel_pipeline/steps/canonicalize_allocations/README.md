# canonicalize_allocations

Gives every allocation its stable identity.

## The grammar

```
https://data.publicinformation.ie/allocation/<recipient-slug>/<year>/<funding-stream>/<key>
```

- `<recipient-slug>` is the permanent slug of the local authority (from the
  public-bodies seed), or the slugified printed name for the
  non-local-authority block.
- `<year>` is the allocation year from the committed publication list.
- `<funding-stream>` is `active_travel` or `other_nta_streams`.
- `<key>` is the **lowercased project code** with punctuation collapsed to `-`
  when the document prints a real code, and the **slugified project name** when
  the code is a placeholder.

| Input | `@id` |
|---|---|
| Wicklow 2026, `WCC/25/0003` | `…/wicklow-county-council/2026/active_travel/wcc-25-0003` |
| Carlow 2022, `CW/21/0001` | `…/carlow-county-council/2022/active_travel/cw-21-0001` |
| 2026 provisional `WCC/26/XXXX`, "Arklow MD Permeability Links" | `…/wicklow-county-council/2026/active_travel/arklow-md-permeability-links` |
| The same code in 2025 and 2026 | two `@id`s, one per year |
| `NTA/15/0001` twice in one section | `…/nta-15-0001`, `…/nta-15-0001-2` |

## Why provisional codes never identify a record

15–40% of rows per year print a placeholder (`WCC/26/XXXX`, `DCC/25/00xx`) that
repeats within a section and is explicitly "to be assigned". Using it as a key
would collapse several distinct projects into one `@id`, so the printed project
name is the key instead and `project_code_provisional` is published as `true`.
Only real codes should be used to follow a project across years.

## Duplicates

Keys that repeat within one recipient, year and stream are suffixed `-2`, `-3`
in document order. Document order is deterministic, so identity is stable across
re-runs of unchanged documents.

A row that is an exact duplicate of an earlier row (same recipient, year,
stream, code, name and amount) is dropped: the source printed the same
allocation twice. Dropped rows are listed in `duplicates` with the page of the
row that was kept, and counted in `metadata.duplicates_dropped`.

## Fatal conditions

A local-authority row with no `public_body_id` stops publication. `@resolve_recipients`
already refuses to emit one; this is the second, defensive check, because a
record whose body link is missing or invented must never be published.

## Output

`results` — the reconciled rows plus `@id`, `project_code`,
`project_code_provisional` and `project_name` — and `duplicates`. Metadata
records the result count, the number of provisional codes and the documents
represented.
