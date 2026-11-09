# Proposal

> **Status: scaffold.** This holds the context and the blocking decisions for CAP status observations, split out of `add-climate-action-plan-actions` on 2026-11-09. **Do not start implementation until `add-climate-action-plan-actions` is archived**, and elaborate the decisions below (via `openspec-update-change` or `openspec-explore`) before writing code.

## Why

Once `add-climate-action-plan-actions` publishes the CAP23–25 declared actions, the remaining value is the quarter-by-quarter status the Department of the Taoiseach publishes for them. This is the State's own record of which statutory climate commitments slipped. It is published as machine-readable XLSX annexes, which are better source material than anything the pipeline currently reads for status.

## What Changes

Indicative, pending the decisions below:

- Ingest the **quarterly XLSX annexes** and derive dated status observations from them, failing closed.
- Repoint each progress report's `reports_on` from its Plan PDF to its year's Annex of Actions, and give `status_source: annex` its operational meaning.
- Attribute observations of carried-over ("legacy") actions to the edition that declared them.
- Express reports and annexes that span plan years, including the Q1&Q2 2026 legacy report.
- Publish the observations through `public-body-actions` (a MINOR change if no field changes).

## Capabilities

### New Capabilities

- `action-annex-ingestion`: how an action annex is acquired and parsed into status records while failing closed. Only the parts that hold under every resolution of the open decisions are specified.

### Modified Capabilities

- `climate-action-plan-corpus`: XLSX annexes and the Q1&Q2 2026 legacy report join the corpus, and reports point at the annexes.
- `public-body-actions-dataset` (created by `add-climate-action-plan-actions`): attributing observations across editions. To be written as a delta once that spec is in `openspec/specs/`.

## Decisions required before implementation

**D-B. Cross-plan attribution has no implementation.**
`build_observations` resolves every observation through `mint_action_id(record["reports_on"], number)`, and nothing in the repo matches across plans. An observation that misses is skipped by design as `UnresolvedActionNumber`. Attributing a carried-over action to the plan that declared it is therefore an `actions_pipeline` code change. Coded references help: under `add-climate-action-plan-actions` D4, `EL/23/1` names its edition's year, and that change's out-of-edition log lists every legacy row.

**D-C. Reports and annexes that span plan years cannot be expressed.**
- `climate-action-plan-2024-q1-q2-and-legacy-2023-actions.xlsx` carries CAP24 and CAP23 legacy rows in one workbook.
- The Q1&Q2 2026 legacy report covers 74 legacy actions from three plan years, and no CAP2026 plan was published.
- `documents.py:103-152` requires every `role: report` to name exactly one `reports_on` plan sharing its `policy_id`.

**D-D. Spreadsheet intake is unbuilt, and there is no fan-in.**
- `fetch_pdfs` validates PDF payloads (`_PDF_CONTENT_TYPES`, `_PDF_MAGIC`).
- `extract_pages` and the five steps after it open every fetched file with pymupdf.
- `src/lib/pipeline_runner.py:99-105` maps a step to a single input step, and `resolve_action_identity` finds its second input by sibling convention (`process.py:326-329`).
- `foi_pipeline`'s fail-closed header chain is a technique to copy, not shared code. `openpyxl`/`xlrd` are already in the shared venv.

**D-E. Colour-coded status.** CAP annexes carry a "Colour key for Annex of Actions", so some status is conveyed by cell fill. Decide whether fill-only status is an error or a reviewed source. The repo's data-handling principle says never guess.

**D-F. The legacy-exercise workbook has no report to date it.** `legacy-actions-from-climate-action-plan-2023.xlsx` has no matching progress report among the curated nine, but `action-annex-ingestion` dates observations from their report.

## Source material (verified from the listing pages, 2026-11-07)

Department of the Taoiseach, `publications/climate-action-plan-progress-reports/`: eleven XLSX annexes under `assets.gov.ie/static/documents/…`:

| Plan year | Annex | File |
|---|---|---|
| 2023 | Q1 | `climate-action-plan-2023-q1-actions.xlsx` |
| 2023 | Q2 | `climate-action-plan-2023-q2-actions.xlsx` |
| 2023 | Q3 | `climate-action-plan-2023-q3-actions.xlsx` |
| 2023 | Q4 | `climate-action-plan-2023-q4-actions.xlsx` |
| 2023 | legacy exercise | `legacy-actions-from-climate-action-plan-2023.xlsx` |
| 2024 | Q1+Q2 **and 2023 legacy** | `climate-action-plan-2024-q1-q2-and-legacy-2023-actions.xlsx` |
| 2024 | Q3+Q4 | `Climate_Action_Plan_2024_-_Q3_and_Q4_Annex_of_Actions.xlsx` |
| 2025 | Q1 | `Q1_CAP25_Progress_Report_Annex_of_Actions_-_Final.xlsx` |
| 2025 | Q2+Q3 | `702c6fd6/Climate_Action_Plan_2025_Q2_and_Q3_Annex.xlsx` |
| 2025 | Q4 | `595303db/Climate_Action_Plan_2025_Q4_Annex.xlsx` |
| 2026 | Q1+Q2, legacy only | `fd00ce2a/Climate_Action_Plan_Q1__Q2_2026_Annex.xlsx` |

Plus the Q1&Q2 2026 legacy progress report PDF, `e23ebb44/Climate_Action_Plan_Q1__Q2_2026_Progress_Report_on_Legacy_Actions.pdf`.

Published headline counts, to be re-read at curation. They are "due in year" subsets, not annex totals:
- CAP23: 290 actions due in 2023 (65% complete by Q4 2023, 47 carried into 2024).
- CAP24: 125 actions (80 complete, 64%).
- CAP25: 82 actions (46 complete, 56%).
- 64 CAP23+CAP24 legacy actions carried into 2025, of which 25 were completed.
- 74 legacy actions carried into 2026, of which 10 were delivered in H1.

## Dependencies

- `add-climate-action-plan-actions` must be archived. It establishes the annex documents, the coded identities, the out-of-edition log and `public-body-actions` 3.0.0.
