# extract_grant_tables

Extracts every page's table and gates it structurally before any of its rows are
used.

## The gate

A page contributes rows only when all of these hold:

| Check | Passes when | Fails as |
|---|---|---|
| text layer | `page.extract_text()` is not blank | `PageHasNoText` |
| table present | `extract_table()` returns at least one row | `TableStructureUnreliable` (`no_table`) |
| column count | every row has 2 or 3 cells, at most 3 | `TableStructureUnreliable` (`column_count`) |
| width uniformity | on pages of 2+ rows, `lib.table_structure`'s `width_uniformity` ≥ 0.4 | `TableStructureUnreliable` (`width_uniformity`) |

The column count is the check that catches a layout change, because the rest of
the pipeline is written against a (code, name, amount) table. The width
tolerance is deliberately loose: this document family legitimately has pages
where a total row ends a block (two cells) beside full three-column rows, and
some pages are a single total row (`Total:` with the amount in the second
column). A page that fails the gate yields no rows and is recorded as an error
naming the page and the failed checks.

**A single cell's imperfect text never rejects a page.** A run-together word or a
name overflowing into the amount column is a cell-level defect: the page is
used, and the affected row is handled (or withheld) further down the chain.

## Parts of a document

Pages are assigned to `project_table` or `recipient_summary` from the page's own
column header (`Project Code…` or `Agency`). A page with no header of its own
keeps the part of the page before it, which is how a table running over a page
break stays whole. Summary rows go to `summary_rows`; everything else to `rows`.
A `programme_summary` document is not extracted at all.

## Output

```json
{
  "metadata": {"pages": 358, "pages_accepted": 358, "rows": 6754, "summary_rows": 78},
  "documents": [ … from fetch_grant_documents … ],
  "pages": [{"document_id": "…", "year": 2026, "page": 7, "part": "project_table",
             "accepted": true, "failed_checks": [],
             "rows": 12, "max_columns": 3, "min_columns": 2,
             "width_uniformity": 1.0, "modal_width": 3, "composite": 0.9}],
  "rows": [{"document_id": "…", "year": 2026, "page": 7, "row_index": 4,
            "part": "project_table", "cells": ["DCC/25/0036", "…", "€ 1,000,000"]}],
  "summary_rows": [ … same shape, from the front-matter summary … ]
}
```

Every page is recorded, accepted or not, with the measurements the gate used, so
a rejected page can be diagnosed from `output.json` alone.

## Error types emitted

- `PageHasNoText` — no text layer (the pipeline never OCRs: an image-only page
  is a human review task).
- `TableStructureUnreliable` — `no_table`, `column_count` or `width_uniformity`.
