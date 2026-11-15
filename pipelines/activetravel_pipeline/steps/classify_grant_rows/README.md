# classify_grant_rows

Gives every extracted row exactly one kind from a closed vocabulary.

The column roles in this document family are fixed (code, name, amount) and
repeated on every page; what varies from row to row is the *kind* of row. So
classification is row-oriented, not header-detection-based: a table does not
reach the project stage just because it has three columns.

## The closed vocabulary

| Kind | What it is | A real example |
|---|---|---|
| `document_title` | The running title, or a `Table A: …` section title | `Active Travel Investment Grants: 2026 Allocations`, `Table A: Dublin City Council` |
| `column_header` | The column header row, repeated on every page | `Project Code` / `Project Name` / `2026 Allocation` (`Project C ode:` in 2022; `Agency` on summary pages) |
| `recipient_heading` | One recipient's name alone on a row | `Dublin City Council`, `Campuses, Hospitals, Educational Institutions and Others` |
| `stream_divider` | The block heading for another funding stream | `Allocations Through Other NTA Funding Streams` |
| `project` | A project row: code, name, amount | `WCC/25/0003` / `Vale Road Pedestrian Improvement Scheme, Arklow` / `€ 350,000` |
| `anchor` | A `Subtotal` / `Total` / `Totals` row | `Subtotal:` / `€6,700,000`; also `['', 'Total:', '€ 3,000,000']` |
| `footnote` | A note row, starting `*` | `* Scheme to be designed by NTA consultants under different project code` |
| `blank` | A row with no cells | (the separator between blocks) |

Recognition rules worth knowing:

- The column header is matched on letters and digits only, so `Project C ode:`,
  `Project\nCode` and the 2022 `Project (cid:10)Code:` all match.
- An anchor is recognised by its label in *any* cell (`['', 'Total:',
  '€ 3,000,000']` in 2026 Longford) and its amount is the last non-empty cell,
  which is how the two-cell Kerry page and the column-shifted anchors are read.
- A row with exactly one non-empty cell that is not a title is a recipient
  heading; `Table A: …` and the running title are document titles.

## Unknown rows are reported, not guessed

A row that fits no kind — for example a code-less row carrying a name and an
amount — is not coerced into `project`. It is removed from the row stream and
recorded as `UnknownRowKind` with its raw cells, document, page and row index:

```json
{"error_type": "UnknownRowKind",
 "error_message": "nta-active-travel-2022 page 59 row 17 matches no known row kind",
 "context": {"cells": ["", "Some Scheme", "€ 5,000"], "page": 59, "row_index": 17}}
```

Nothing unclassified can reach the project stage: the next step only reads rows
whose `kind` is `project` or `anchor`, and every later step reads only rows it
was given. The classified stream also carries each row's matched detail (code,
name, anchor label, amount cell), so no later step has to re-guess which cell
holds the money.
