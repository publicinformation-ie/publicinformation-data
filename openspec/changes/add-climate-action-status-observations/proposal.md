# Proposal

> Split out of `add-climate-action-plan-actions` on 2026-11-09. That change is archived (2026-11-10), so its dependencies are met. Decisions D-B to D-F were elaborated on 2026-11-10 against the code and against all eleven workbooks, re-read that day (design.md, "Source facts").

## Why

`add-climate-action-plan-actions` published the CAP23–25 declared actions. The remaining value is the quarter-by-quarter status the Department of the Taoiseach publishes for them: the State's own record of which statutory climate commitments slipped. It is published as machine-readable XLSX annexes, which are better source material than anything the pipeline currently reads for status.

## What Changes

- A progress report entry may declare its companion workbook as `status_annex: {url, format: xlsx}`. The workbook is an attachment of the report, not a corpus document, so it never enters the PDF steps.
- Two new document_pipeline steps:
  - `fetch_status_annexes` acquires each declared workbook, validating it as a zip payload that openpyxl can read, not by content type.
  - `extract_annex_status` parses every sheet against a reviewed table of exact header layouts and emits status observations, failing closed.
- `reports_on` may name **a list** of plans. Each CAP report lists the Annex of Actions it observes: its own year's, plus earlier editions for legacy actions. An observation is attributed to the listed plan that **declares** its reference. It is excluded and logged if none does, and never assigned to the report's own plan as a fallback.
- `resolve_action_identity` reads annex observations as a second sibling input, alongside `extract_action_status`, and resolves them by reference.
- Each existing CAP progress report's `reports_on` is repointed from its Plan PDF to the annex list. The Q1&Q2 2026 legacy report joins the corpus, listing the 2023–2025 annexes.
- Undated reports get a curated, evidenced `published_date`. Any report still undated publishes no observations and is logged.
- Observations publish through `public-body-actions` **3.1.0** (MINOR: no field or vocabulary changes).

## Capabilities

### New Capabilities

- `action-annex-ingestion`: declaring, acquiring and parsing a report's status annex, attributing its observations across editions, and dating them.

### Modified Capabilities

None textually.
- `climate-action-plan-corpus` "Reports whose status detail is published elsewhere" still holds as written: PDF status extraction keeps skipping declared reports, and the annex is read by the new capability.
- `public-body-actions-dataset` gains records only, no requirement changes. "Actions belong to the edition that declares them" is what the attribution rule relies on.

## Decisions (resolved; detail in design.md)

- **D-B, attribution.** Resolve by reference within the plans the report lists. The code year breaks ties only when several listed plans declare the same reference.
- **D-C, spanning plan years.** `reports_on` becomes a list. The 2026 legacy report lists the 2023, 2024 and 2025 annexes, so no 2026 plan is needed.
- **D-D, plumbing.** The workbook is a `status_annex` attribute read by two new steps, so no PDF step needs to skip anything. The second input arrives by the existing sibling-path convention; shared-runner fan-in stays out of scope.
- **D-E, colour.** Status is read from cell text only and fill is ignored. No workbook carries a colour key, and no row conveys status by fill alone.
- **D-F, legacy-exercise workbook.** Not ingested. Its 102 rows are exactly the Q4 2023 Delayed rows, and no report dates it.
- **Discontinued.** Two rows say `Discontinued`, which the closed vocabulary cannot express. They are excluded and logged. Extending the vocabulary is a separate reviewed change.

## Source material (re-read 2026-11-10)

Eleven XLSX annexes under `https://assets.gov.ie/static/documents/`, all returning 200. The gov.ie listing page returns 403 to scripted clients.

| Report (doc_slug suffix) | Annex file | Sheets |
|---|---|---|
| 2023-q1 | `climate-action-plan-2023-q1-actions.xlsx` | 1 |
| 2023-q2 | `climate-action-plan-2023-q2-actions.xlsx` | 1 |
| 2023-q3 | `climate-action-plan-2023-q3-actions.xlsx` | 1 |
| 2023-q4 | `climate-action-plan-2023-q4-actions.xlsx` | 1 |
| *(none; not ingested, D-F)* | `legacy-actions-from-climate-action-plan-2023.xlsx` | 1 |
| 2024-q1-q2 | `climate-action-plan-2024-q1-q2-and-legacy-2023-actions.xlsx` | Q1 & Q2, Legacy |
| 2024-q3-q4 | `Climate_Action_Plan_2024_-_Q3_and_Q4_Annex_of_Actions.xlsx` | Q3 & Q4, Q1 & Q2, Legacy |
| 2025-q1 | `Q1_CAP25_Progress_Report_Annex_of_Actions_-_Final.xlsx` | Q1, Legacy |
| 2025-q2-q3 | `702c6fd6/Climate_Action_Plan_2025_Q2_and_Q3_Annex.xlsx` | Q3, Q2, Q1, Legacy |
| 2025-q4 | `595303db/Climate_Action_Plan_2025_Q4_Annex.xlsx` | Q4, Q3, Q2, Q1, Legacy |
| 2026-q1-q2 legacy *(new)* | `fd00ce2a/Climate_Action_Plan_Q1__Q2_2026_Annex.xlsx` | Sheet1 |

The new report PDF is `e23ebb44/Climate_Action_Plan_Q1__Q2_2026_Progress_Report_on_Legacy_Actions.pdf` (27 pages). It covers 74 legacy actions from CAP23, CAP24 and CAP25: 10 complete and 64 delayed, matching its annex.

## Dependencies

- `add-climate-action-plan-actions` (archived 2026-11-10): annex documents, coded identities, out-of-edition log, `public-body-actions` 3.0.0.
