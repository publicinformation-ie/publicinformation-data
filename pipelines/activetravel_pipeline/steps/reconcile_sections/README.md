# reconcile_sections

Publishes a recipient's funding stream only when the document's own arithmetic
confirms it.

## The guarantee

> **Anything published is complete for its recipient, year and stream, and adds up.**

For each recipient *and* funding stream, the rows that would be published must
equal the total the document declares for that stream. A block whose own
subtotal is printed must equal that subtotal too. Any difference — one euro is a
difference — withholds that stream's rows and reports the recipient, the stream,
both sums and the delta.

The stream is the unit, not the recipient: a document that declares money for an
other-NTA-funding-streams block it does not print (Cork County 2026, Dublin City
2026, Wicklow 2026, Kerry 2025, Longford 2025, Wexford 2025) loses only that
block, and the authority's active-travel rows still publish.

## How the declared figures are found

1. The section's last anchor is the section total.
2. A block with a printed subtotal declares that amount.
3. A block with no printed subtotal declares what is left: section total minus
   the blocks that were declared. If more than one block is undeclared, or the
   declared blocks already exceed the section total, the section cannot be split
   and nothing from it is published.
4. Money left over after every block is accounted for is declared for an
   other-NTA-streams block with no printed rows, which is then withheld on its
   own (2025 Kerry's €600,000, 2026 Cork County's €2,285,000).

A stream with no readable declared figure is withheld too: a control that cannot
be read has not confirmed anything.

## Committed repairs

`row_repairs.json` entries with `action: "drop_row"` are applied here, for a row
the source really prints twice (or prints as an exact duplicate of another),
keyed by document, page and row index. Every applied repair is reported as
`RowRepairApplied` with the reason. `set_amount` repairs are applied upstream by
`normalize_grant_amounts`.

## Output

- `rows` — only the rows belonging to streams that reconciled.
- `sections` — each with `blocks`, `streams` (`extracted_eur`, `declared_eur`,
  `delta_eur`, `reconciled`, `reasons`), `withheld_streams` and `withheld`.
- `withheld_rows` — every row kept out of publication, with its reason.

## Errors

`SectionReconciliationMismatch` — one per withheld stream, with
`context.extracted_eur`, `context.declared_eur`, `context.delta_eur`,
`context.funding_stream`, the recipient and its first page. A section that could
not be split at all is reported once, with `funding_stream: null`.
`RowRepairApplied` — informational, for each applied `drop_row`.
