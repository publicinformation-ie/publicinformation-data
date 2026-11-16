# segment_funding_streams

Groups project rows into recipient sections and anchor-bounded blocks, and gives
each block a funding stream.

## Sections

A section is one recipient's table. It starts at a recipient heading and is
closed by its declared total. A heading that repeats on a later page is the same
section continuing, not a new one — every page of a long table repeats the
running title, the recipient name and the column header.

A row that arrives with no heading at all opens a *heading-less* section,
which `resolve_recipients` attributes from the project-code prefix. That is not
a fallback for convenience: the 2024 Fingal table and the 2026 Galway City and
Clare tables have no `Table A:` title and no heading anywhere in the PDF, so
position is the only thing that could have been used — and position is never
trusted.

## Blocks and funding streams

Within a section, the money anchors decide the blocks:

- The **last anchor** in a section is the section total. It is the first
  `Total`/`Totals` row that directly follows another anchor, or, when the
  section is closed by the next heading, the last anchor seen.
- Every **earlier anchor** closes a block (usually a printed `Subtotal:`).
- A `stream_divider` row also closes a block, so a block that opens with a
  divider is not joined to the rows above it.

The **block index** then decides the stream: the first block is the recipient's
`active_travel` allocation, every later block is `other_nta_streams`. Page
position is never used, which is why the two shapes this document family
produces are both handled correctly:

| Shape | Real example | Result |
|---|---|---|
| A block opens with no divider heading | 2026 Wicklow, page 23: rows then `Subtotal:` then `Total:` | Those rows are `other_nta_streams`, because their anchors bracket them after the first block closed |
| A section's first block closes on a `Subtotal:` rather than a `Total` | 2026 Dublin City, page 6: `Subtotal: €35,950,000`, then the divider | The first block is `active_travel`, the second `other_nta_streams` |
| A block has no printed subtotal at all | 2026 Westmeath: rows, divider, one row, `Subtotal:`, `Total:` | The first block is still `active_travel`; the section total is what confirms it |
| A section's table has no total | 2024 Galway County, page 34 | `UnbracketedBlock`: no row from it can be confirmed |

## Rows no anchor brackets are withheld

When a section has no declared total at all, none of its rows can be confirmed,
so all of them are withheld as `UnbracketedBlock` and named in errors with their
page and cells. Nothing is assigned a stream.

## Output

`rows` (each project row now carrying `section_id`, `section_heading`,
`block_index`, `funding_stream`), `sections` (heading, title, first page,
section total anchor, per-block declared anchor and row count), and
`withheld_rows`.
