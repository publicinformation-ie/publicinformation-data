# Run report — 2026-11-15

The first complete run of `activetravel_pipeline` over all six declared documents
(the five editions plus the 2022 Annex 1), with the error queue triaged and the
outcome recorded. Numbers below are from that run.

## Funnel

| Stage | Count |
|---|---|
| Documents declared / available | 6 / 6 (all from cache; no network) |
| Pages extracted / accepted by the gate | 358 / 358 |
| Rows extracted (project-table pages) | 6,754 |
| Rows classified | 6,753 (1 unknown) |
| Amounts read / withheld | 6,719 / 34 |
| Manual repairs applied | 9 |
| Sections segmented / resolved | 159 / 159 |
| Sections published (of 159) | 148 (11 funding streams withheld) |
| Summary totals compared (2025 + 2026) | 61, all agreeing |
| Published allocations | **4,875** |
| Published allocations (€) | **1,661,375,921** |

Per year: 990 (2022), 1,156 (2023), 833 (2024), 913 (2025), 983 (2026).

## The extracted figures agree with the publishers' own totals

Two independent cross-checks fell out of the run:

- **2025**: the extracted active-travel total is €294,430,134 — exactly the
  `Total:` the 2025 document prints in its own front summary.
- **2022**: the published total plus the two withheld 2022 streams
  (€365,165,751 + €18,158,485 + €4,440,000) = **€387,764,236**, which is the
  sum of the 2022 document's 32 printed `Total:` rows.

## Withheld streams (the review queue)

Eleven recipient streams did not reconcile and are **not** in the dataset. Each
is also reported in the run's errors with both sums and the difference.

| Year | Recipient | Stream | Extracted | Declared | Cause |
|---|---|---|---|---|---|
| 2022 | South Dublin County Council | active_travel | 17,858,485 | 18,158,485 | One project row (`SDCC/21/0011`) is printed with **no project name**, so it cannot be classified or named. €300,000 of the total is therefore unaccounted for. |
| 2022 | Wexford County Council | active_travel | 4,440,001 | 4,440,000 | The rows are **one euro over** the declared total (source rounding). |
| 2024 | Fingal County Council | active_travel | 16,000,000 | 21,500,000 | Three rows print **no amount** (two blank cells, one `€ -`); €5,500,000 of the total has no printed row. |
| 2024 | Campuses, Hospitals, Educational Institutions and Others | active_travel | 8,630,172 | 8,630,171 | Rows are **one euro over** the declared total. |
| 2025 | Kerry County Council | other_nta_streams | 0 | 600,000 | The document declares €600,000 for other NTA streams but prints **no rows** for them. |
| 2025 | Longford County Council | other_nta_streams | 0 | 500,000 | Same: declared, not printed. |
| 2025 | Wexford County Council | other_nta_streams | 32,000 | 582,000 | Prints one €32,000 row against a €582,000 subtotal. |
| 2026 | Dublin City Council | other_nta_streams | 2,850,000 | 6,700,000 | Prints four rows against a €6,700,000 subtotal. |
| 2026 | Wicklow County Council | other_nta_streams | 115,974 | 615,974 | Prints two rows against a €615,974 subtotal. |
| 2026 | Cork County Council | other_nta_streams | 0 | 2,285,000 | Declared, not printed. |
| 2026 | Waterford City and County Council | active_travel | 8,499,999 | 8,500,000 | Rows are **one euro under** the declared subtotal. |

Nothing else is missing: every other recipient stream in every year reconciles
to the last euro, and every 2025/2026 recipient that has a front-summary line
agrees with it.

### What a human should decide about these

1. **Mislabelled rather than missing?** In the six "declared, not printed"
   cases the document's *subtotal* covers funding lines it does not itemise.
   The current rule withholds the stream. The alternative — publish the listed
   rows and note the shortfall — would break the "adds up" guarantee, so it was
   not done. This is the single most valuable decision for a reviewer.
2. **One-euro mismatches** (2022 Wexford, 2024 Others, 2026 Waterford) are
   arithmetic slips in the source. Withholding is deliberate; a `row_repairs`
   entry could pin the row that carries the slip, but that requires confirming
   which row is wrong.
3. **South Dublin 2022** is withheld for one nameless row. A repair action that
   supplies a confirmed project name does not exist yet; the row is identifiable
   (`SDCC/21/0011`, €300,000) and is the only thing standing between the section
   and publication.
4. **Fingal 2024** prints three rows with no amount. Nothing can be inferred.

## Repairs applied (9)

All are cells where a project name overflows into the amount column, so the
printed figure is interleaved with text and the amount parser rejects it by
design. Each value was confirmed against its section's declared total — the
section reconciles exactly once the repair is applied.

| Document | Page | Row | Code | Value | Confirmation |
|---|---|---|---|---|---|
| 2022 | 6 | 18 | `CCC/21/0012` | 150,000 | Cork City then totals €46,291,010 |
| 2022 | 8 | 14 | `CCC/22/xxxx` | 60,000 | idem |
| 2022 | 26 | 12 | `FCC/20/0006` | 1,500,000 | Fingal then totals €25,535,000 |
| 2022 | 27 | 10 | `FCC/22/xxxx` | 925,000 | idem |
| 2022 | 27 | 12 | `FCC/22/xxxx` | 500,000 | idem |
| 2022 | 76 | 16 | `NTA` | 200,000 | the block then totals €6,960,000 |
| 2026 | 75 | 5 | `WH/25/0010` | 200,000 | Westmeath then totals €3,500,000 |
| 2026 | 75 | 6 | `WH/25/0011` | 5,000 | idem |
| 2026 | 75 | 13 | `WH/26/xxxx` | 10,000 | idem |

## Withheld rows that are not stream failures

- **31 rows printed `N/A*`** (2025): the document states the scheme will be
  designed under a different project code and prints no allocation. They are not
  published, and because the sections' totals exclude them, no section fails
  because of them.
- **1 unclassifiable row** (2022 South Dublin, above).
- **34 unreadable amounts** in total, including 2024 Sligo's `€ -` row, which the
  section total excludes — so Sligo publishes.

## Verification

| Check | Result |
|---|---|
| `uv run python pipelines/activetravel_pipeline/status.py --all` | all five editions flow; annex reported as "not extracted (programme summary)" |
| `uv run pyright` | 0 errors |
| `uv run pytest pipelines/activetravel_pipeline/tests -q` | 107 passed |
| `uv run pytest tests/ -q` | 442 passed, 1 failed (pre-existing: the built `foi-disclosures.csv` is absent) |
| `uv run pytest pipelines/document_pipeline/tests -q` | 499 passed |
| `uv run python scripts/generate_pipeline_docs.py --check` | clean |
| `uv run pytest pipelines/foi_pipeline/tests -q` | **not run** — the suite is slow, no FOI code was touched, and the run was stopped pending permission |

The dataset tests pin the published counts: the README's per-year table must
equal the CSV, the CSV must have as many rows as the JSON-LD `@graph`, and
`latest/` must mirror the versioned release byte for byte.

## Publication

`scripts/transform_active_travel_allocations.py` published 4,875 allocations to
`public/v1.0.0/active-travel-allocations/` and mirrored it to
`public/latest/active-travel-allocations/`. A second run with unchanged input
rewrote nothing and left `dct:modified` untouched. Merging that `public/` change
is what publishes it.
