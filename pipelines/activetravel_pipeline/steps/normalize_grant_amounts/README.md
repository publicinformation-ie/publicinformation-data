# normalize_grant_amounts

Reads every printed amount as whole euro, applying committed repairs and
recording every change it makes.

## Accepted formatting

These are formatting, not data, and produce no repair:

- the currency symbol: `€1,100,000`, `1,100,000`
- thousands separators: `€1,100,000`
- a zero cents part: `10,000.00`, `400.00` (2026 Offaly prints its amounts this way)

Whitespace *inside* the number is also accepted, but it is a defect in the
printed cell, so it is recorded as a repair naming the raw cell and the value
used:

| Printed | Value | Repair |
|---|---|---|
| `€ 2 0,000,000` | `20000000` | `whitespace_inside_number` |
| `€ 5 ,000` | `5000` | `whitespace_inside_number` |
| `1 60,000.00` | `160000` | `whitespace_inside_number` |

## The rejection set

| Printed | Error | Why |
|---|---|---|
| `€ -` | `no_digits` | no amount is printed |
| (empty) | `empty` | no amount is printed |
| `N/A*` | `letters` | the document says the scheme will be designed under a different code |
| `ection€60,000` | `letters` | a project name overflows into the amount column |
| `€ 1,234.56` | `sub_euro_amount` | not a whole number of euro |
| `€ 12,34,000` | `ambiguous_grouping` | separators are not groups of three |

A value is never harvested out of a cell that also holds letters: the mixed cell
fails instead of being mined, which is what keeps a name-overflow cell from
being read as `60,000` when the real figure is unknown.

## What is withheld, and what is not

- A **project row** whose amount cannot be read is withheld (`UnreadableAmount`)
  and its row is kept in `withheld_rows` for review. Losing the row makes its
  stream's sum fall short of the declared total, so the stream is withheld at
  reconciliation — which is the intended, visible outcome.
- An **anchor row** whose amount cannot be read stays in the stream with
  `amount_eur: null` and `amount_unreadable: true`, and is reported. Dropping it
  would silently detach a control total from the block it closes; keeping it lets
  segmentation still bracket the block and lets reconciliation say that the
  declared figure is unknown.

## Committed repairs

A `row_repairs.json` entry with `action: "set_amount"` is applied here, before
the printed cell is read, keyed by document, page and row index. The correction
is then reported as `RowRepairApplied` (raw cell, value used, reason), so it
stays visible in the run. Nine such repairs exist, for the 2022 and 2026 cells
where a project name overflows into the amount column; each is confirmed by the
section's declared total.

## Output

`rows` (amounts read, with `amount_repair` where one was needed),
`withheld_rows` (project rows kept out of the stream), and metadata counts of
rows, withheld rows, applied repairs and whitespace repairs.
