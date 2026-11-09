# Proposal

> **Status: scaffold.** This change is deliberately not elaborated. It exists to hold the context and the blocking decisions discovered while scoping `add-climate-action-plan-documents`, so none of that evidence has to be rediscovered. **Do not start implementation until `add-climate-action-plan-documents` is complete**, and elaborate the open decisions below (via `openspec-update-change` or `openspec-explore`) before writing code.

## Why

`add-climate-action-plan-documents` publishes the Climate Action Plan 2023–2025 plans and quarterly progress reports as document bundles, but deliberately stops short of the data those documents are about: the actions each plan declares, and the quarter-by-quarter status the Department of the Taoiseach publishes for them. That status data is the point of the corpus — it is the State's own record of which statutory climate commitments slipped — and it is published as machine-readable spreadsheets, which is better source material than anything the pipeline ingests today.

It was deferred because it is blocked on four questions that the documents-only change did not need to answer, two of which touch a published dataset contract.

## What Changes

Indicative, pending the decisions below:

- Ingest the **CAP Annex of Actions PDFs** (one per plan year) as each plan edition's action source, repointing each progress report's `reports_on` from the Plan PDF to its year's annex.
- Ingest the **quarterly XLSX action annexes** and derive dated status observations from them, fail-closed.
- Extend **`actions_pipeline`** so CAP actions carry a citable identity and carried-over ("legacy") actions are attributed to the plan year that declared them.
- Publish CAP actions and observations through the **`public-body-actions`** dataset.

## Capabilities

### New Capabilities

- `action-annex-ingestion`: how an action annex is acquired and parsed fail-closed into action and status records, and what must hold for a published action's identity. Only the parts that hold under every resolution of the open decisions are specified; the rest waits on those decisions.

### Modified Capabilities

- `climate-action-plan-corpus` — the corpus gains the Annex of Actions documents, so "Plan documents are not action sources in this corpus" is superseded, and the Q1&Q2 2026 legacy report becomes expressible.
- *(to be confirmed during elaboration: whichever capability ends up owning action identity and attribution — no spec covers `actions_pipeline` today.)*

## Decisions required before implementation

**D-A. CAP action numbers are not integers, and the published schema says they are.**
CAP actions are sector codes — `EL/23/1`, `MA/23/5` — with sub-actions `EL/23/6/A`, `EL/23/6/B`. But `resolve_action_identity` mints `{plan_slug}#{int}` from a leading ordinal (`strip_leading_ordinal`, `process.py:57,71-89`) and skips anything else as `UnresolvedActionNumber`; `public/schemas/public-body-actions.schema.json:27` requires `action_number` to be an integer ≥ 1 and required; and the permanent action URI is `/action/{plan_slug}/{action_number}` (`transform_public_body_actions.py:232`). Options, none free:
- widen `action_number` to a string → **MAJOR** version bump on `public-body-actions`;
- add an `action_code` field alongside a synthetic integer → MINOR, but two identity namespaces and a decision about what the action URI means;
- mint sequential integers → breaks citability, since "CAP action EL/23/1" is how these are cited in public.
Sub-action hierarchy (`/A`, `/B`) has no representation under any of the three.

**D-B. Cross-plan attribution has no implementation.**
`build_observations` resolves every observation through `mint_action_id(record["reports_on"], number)` with no cross-plan matching anywhere in the repo, and an observation that misses is `UnresolvedActionNumber` — skipped, by design. Attributing a carried-over action to the plan that declared it is therefore an `actions_pipeline` code change, not a curation rule. The earlier draft of this work assumed it was free; it is not.

**D-C. Reports and annexes that span plan years cannot be expressed.**
`climate-action-plan-2024-q1-q2-and-legacy-2023-actions.xlsx` carries CAP24 and CAP23 legacy rows in one workbook. The Q1&Q2 2026 legacy report covers 74 legacy actions from three plan years, and no CAP2026 plan was published. `documents.py:103-152` requires every `role: report` to name exactly one `reports_on` plan sharing its `policy_id`. Keeping all CAP documents under one `climate-action-plan` policy (decided in the documents change, D3) is a precondition for solving this but not a solution.

**D-D. Spreadsheet intake is unbuilt, and the fan-in does not exist.**
`fetch_pdfs` validates PDF payloads (`_PDF_CONTENT_TYPES`, `_PDF_MAGIC`); `extract_pages:254-258` opens every fetched file with pymupdf, as do the four steps after it, so a spreadsheet entry needs an explicit rule in each. `src/lib/pipeline_runner.py:99-105` maps a step to a single input-step **string** and passes one `--input`, and `resolve_action_identity` finds its second input by sibling convention (`process.py:326-329`) — so a second action source means either changing the shared runner (used by all ten pipelines) or extending that convention. `foi_pipeline`'s fail-closed header chain is a technique to copy, not shared code; `openpyxl`/`xlrd` pins live in `foi_pipeline/requirements.txt` and are already in the shared venv.

Additionally: CAP annexes carry a **colour key** ("Colour key for Annex of Actions"), so some status is conveyed by cell fill rather than text. Decide explicitly whether fill-only status is an error or a reviewed source — the repo's data-handling principle says never guess.

## Impact

Scope sketch only, to be confirmed on elaboration: `pipelines/document_pipeline/` (`documents.yml`, `documents.py`, `fetch_pdfs`, the PDF-only middle steps, a new annex-parsing step, `pipeline.json`), `pipelines/actions_pipeline/` (identity and attribution), possibly `src/lib/pipeline_runner.py`, `public/schemas/public-body-actions.schema.json`, `scripts/transform_public_body_actions.py`, `public/catalog/dataset-public-body-actions.ttl`, `public/CHANGELOG.md`, and tests in all three suites.

## Source material (verified from the listing pages, 2026-11-07)

Department of Climate, Energy and the Environment — one Annex of Actions PDF per plan year, published separately from the plan (CAP23's on 7 March 2023); enumerate exact URLs at curation time. Reserved slugs: `climate-action-plan-<year>-annex-of-actions`.

Department of the Taoiseach, `publications/climate-action-plan-progress-reports/` — eleven XLSX annexes under `assets.gov.ie/static/documents/…`:

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

Published counts, useful as invariant candidates but to be re-read from the sources at curation time: CAP23 290 actions due in 2023 (65% complete by Q4 2023, 47 remaining into 2024); CAP24 125 actions (80 complete, 64%); CAP25 82 actions (46 complete, 56%); 64 CAP23+CAP24 legacy actions carried into 2025, 25 completed; 74 legacy actions into 2026, 10 delivered in H1.

## Dependencies

- `add-climate-action-plan-documents` must be complete and archived: it establishes the climate inventory, the single `climate-action-plan` policy, the twelve published documents, and the `status_source: annex` declaration that this change gives operational meaning.
