# Source notes (tasks 0.1 / 0.2)

Recorded 2026-11-09. XLSX files were downloaded to a scratch directory outside the repo and opened read-only with openpyxl.

## Status: 0.1 incomplete, 0.2 done, D2 contradicted

**Result: STOP.** The XLSX annexes print action references that fall outside the D2 character set `[A-Za-z0-9]` segments joined by `/`. Under D2 as written, 60 of roughly 500 CAP23/CAP24 actions would be excluded. The design needs a decision before section 2 starts.

## 0.1 Annex of Actions PDFs: not done

The DCEE listing pages (`gov.ie/en/department-of-climate-energy-and-the-environment/publications/climate-action-plan-<year>/`) and the Department of the Taoiseach page return `403` from CloudFront to a plain `curl` client. The annex PDF URLs are only discoverable on those pages (none is recorded anywhere in the repo), so the PDF URLs, titles, dates, printed reference format, parent rows and legacy-row placement could not be read. Someone with a browser needs to supply the three direct PDF URLs, titles and publication dates. `assets.gov.ie` itself serves plain requests (`200`), so the PDFs download fine once the URLs are known.

## 0.2 Taoiseach XLSX annexes: downloaded and readable

All ten files named in `add-climate-action-status-observations/proposal.md` return `200` from `https://assets.gov.ie/static/documents/<file>`. (The Q1&Q2 2026 workbook was not fetched; it is out of scope.)

Layout is consistent: one header row, columns `Chapter | Theme | Measure | Action Number | Action(s) | Step(s) | Output | Timeline` (the Q1 2025 annex also adds trailing columns), one action per row, several sheets per workbook (per quarter, plus `Legacy`). Column 4 is the reference; column 5 is the action text. Readable for reconciliation (D5).

| Workbook | Sheets |
|---|---|
| `climate-action-plan-2023-q1..q4-actions.xlsx` | one sheet each (Q4 has 203 rows) |
| `legacy-actions-from-climate-action-plan-2023.xlsx` | `2023 Q4 Legacy Final` |
| `climate-action-plan-2024-q1-q2-and-legacy-2023-actions.xlsx` | `Q1 & Q2 Actions`, `Legacy Actions` |
| `Climate_Action_Plan_2024_-_Q3_and_Q4_Annex_of_Actions.xlsx` | `Q3 & Q4 Actions`, `Q1 & Q2 Actions`, `Legacy Actions` |
| `Q1_CAP25_Progress_Report_Annex_of_Actions_-_Final.xlsx` | `Q1`, `Legacy` |
| `Climate_Action_Plan_2025_Q2_and_Q3_Annex.xlsx` | `Q3`, `Q2`, `Q1`, `Legacy` |
| `Climate_Action_Plan_2025_Q4_Annex.xlsx` | `Q4`, `Q3`, `Q2`, `Q1`, `Legacy` |

## Reference format findings (XLSX only; the PDF may differ)

Distinct references after whitespace removal, by year segment: `/23/` 288, `/24/` 126, `/25/` 82. These are close to the published headline counts (290/125/82).

**Held (D4):**
- The plan year is embedded: `EL/23/1`, `AG/24/26`, `LU/25/4`.
- Legacy rows are distinguishable by the year segment. The `Legacy` sheets of the 2024 and 2025 workbooks carry `/23/` and `/24/` codes, and the CAP24 workbook's `Legacy Actions` sheet carries `/23/` codes.
- Sub-actions use a trailing `/<letter>` segment (`CZ/23/3/A`, `AD/23/14/A`, `GV/23/2/C`): 78 in CAP23, 1 in CAP24, none in CAP25.

**Contradicted or underspecified (D2/D3):**
1. **`(TF)` suffix.** 32 CAP23 and 28 CAP24 references carry a literal `(TF)` flag, for example `BE/24/15(TF)`, `TR/23/46(TF)`, `BE/23/33/A(TF)`, and once with a space (`TR/24/4 (TF)`). `(` and `)` are outside the D2 set. The flag is not part of the identity: `TR/23/46` appears both with and without `(TF)` across workbooks. All 60 are Transport and Built Environment (and one Agriculture, `AG/23/13(TF)`) actions. Whether the Annex PDFs print `(TF)` too is unverified (0.1).
2. **Letter without a slash.** `EL/23/10A`, `EL/23/10B`, `LU/23/7A`: sub-action letters printed without the `/` separator. Three references.
3. **Whitespace noise.** Non-breaking spaces and doubled spaces are common (`LU/25/5\xa0`, `LU/25/1\xa0\xa0`). Whitespace normalisation handles these; they are not a contradiction.
4. **Parent rows (D3).** Of 34 distinct CAP23 parents implied by sub-action codes, only 16 appear as rows in any workbook. These workbooks list only actions due in a period, so this is not conclusive for the PDFs.

Options the design owner could choose between (not implemented): treat `(TF)` as a stripped flag recorded elsewhere (a new field, which widens the contract); keep it in the reference and widen the D2 set to allow `(`/`)` (then URIs need escaping, which D2 rejects); or exclude `(TF)` rows and log them (loses roughly 60 actions, which reconciliation would then flag as missing).
