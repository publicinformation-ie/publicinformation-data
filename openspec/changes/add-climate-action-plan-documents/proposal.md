# Proposal

## Why

Ireland's Climate Action Plans (CAP) are the State's statutory roadmap for meeting legally binding carbon budgets, and the Department of the Taoiseach publishes a quarterly progress report against each one. None of that corpus is ingested or published today, because the document pipeline's curated policy inventory is transport-scoped: `policy_id` validation cannot resolve a climate record, so no climate document can enter `documents.yml` at all.

This change opens the pipeline to the CAP23–CAP25 corpus **as documents**: published, searchable, section-structured bundles with figures and cleaned text, exactly as the transport corpus is published today. Extracting the actions those plans declare, and the per-quarter status data the Taoiseach publishes in spreadsheet annexes, is deferred to a follow-up change — see *Deferred scope*.

## What Changes

- Add a **second, climate-domain policy inventory** (`input_plans_climate.md`) so `policy_id` validation can resolve climate records. `policies.py` discovers every `input_plans_<domain>.md` and merges them into one validation namespace; the transport file and every transport `policy_id` are untouched.
- **Scope published policy datasets by domain.** `scripts/transform_transport_policies.py` currently publishes everything `load_policies()` returns, so a merged inventory would silently add climate rows to the Transport Policies dataset. The transform filters to its own domain, and the published transport CSV must come out byte-identical.
- Extend the **document_pipeline corpus** with twelve PDFs: the Climate Action Plan 2023, 2024 and 2025 (from the DCEE listing page) and the nine quarterly progress reports published under them (from the Taoiseach progress-reports listing page). All twelve publish as document bundles.
- Add a **`status_source: annex` declaration** for progress reports whose machine-readable status detail is published in a companion spreadsheet, not in the PDF. `extract_action_status` skips those reports by declaration instead of filling `errors.json` with `UnknownReportFormat` for nine documents it was never going to read.
- Publishing is a **content addition only**: new bundles under `public/documents/`, a regenerated `index.json`, and a `dct:modified` stamp on `dataset-documents.ttl`. No field names, types or vocabularies change, so **no `owl:versionInfo` bump** anywhere.

## Capabilities

### New Capabilities

- `policy-inventory`: the curated multi-domain policy inventory contract — what an inventory file must look like, how domain files are merged for `policy_id` validation, and how a published dataset built from the inventory stays scoped to its own domain. Today this behaviour is implicit in `documents.py` + `policies.py` over one transport file.
- `climate-action-plan-corpus`: the composition of the CAP23–CAP25 document corpus — which documents exist per plan year, slug/title/date conventions, how reports link to the plan they report on, and how a report whose status detail lives outside its PDF is declared.

### Modified Capabilities

- *(none — `document-structure-detection`, `minutes-ocr` and `motions-dataset` are untouched)*

## Impact

- `pipelines/document_pipeline/`: new `input_plans_climate.md`; `policies.py` (merge domain inventories, record `domain`); `documents.py` (`status_source` field); `extract_action_status` (honour the declaration); `documents.yml` (12 entries); `README.md`; tests.
- `scripts/transform_transport_policies.py` + `tests/test_transport_policies_dataset.py`: domain scoping, with the published CSV unchanged.
- `pdf_candidates.py` also calls `load_policies()`; as a review aid it benefits from seeing climate policies and needs no change beyond confirming it still runs.
- `tests/test_documents_dataset.py` asserts `public/documents/index.json` covers exactly the curated set, so the `documents.yml` entries and the regenerated `index.json` must land in the same commit.
- Published artifacts: 12 new bundles under `public/documents/` (Git LFS tracked), `index.json`, `index.html`, a `dct:modified` stamp on `public/catalog/dataset-documents.ttl`, and a `public/CHANGELOG.md` entry.
- Source URLs on gov.ie are listing pages, not direct PDFs — candidates are enumerated from the pages and curated by hand; `pdf_candidates.py` stays the review aid.
- Ops: scoped `--doc` runs with `--force --stop-on-error`; `errors.json` triage per step; `public/` diff review before the commit that publishes.
- Unchanged by this change: `actions_pipeline`, `public-body-actions`, `fetch_pdfs`' PDF-only payload validation, and `src/lib/pipeline_runner.py`.

## Deferred scope

A follow-up change covers the CAP action data. It is deferred because it is blocked on decisions this change does not need to make, each of which is already evidenced:

1. **CAP action numbers are not integers.** They are sector codes (`EL/23/1`, `MA/23/5`) with sub-actions (`EL/23/6/A`). `resolve_action_identity` mints `{plan_slug}#{int}` from a leading ordinal (`strip_leading_ordinal`, `process.py:57,71-89`) and skips anything else as `UnresolvedActionNumber`; `public/schemas/public-body-actions.schema.json:27` requires `action_number` to be an integer ≥ 1, and the permanent action URI is `/action/{plan_slug}/{action_number}`. Widening that field is a **MAJOR** dataset change, so the follow-up must choose deliberately between widening it, adding an `action_code` alongside, or minting synthetic integers (which would break citability).
2. **Cross-plan attribution has no implementation.** `build_observations` resolves every observation through `mint_action_id(record["reports_on"], number)` with no cross-plan matching anywhere in the repo, so attributing a carried-over action to the plan that declared it is an `actions_pipeline` code change, not a curation rule.
3. **Reports that span plans cannot be expressed.** `climate-action-plan-2024-q1-q2-and-legacy-2023-actions.xlsx` carries CAP24 and CAP23 legacy rows in one workbook, and the Q1&Q2 2026 report covers legacy actions from three plans with no CAP2026 plan published at all. `documents.py:103-152` requires every report to name exactly one `reports_on` plan sharing its `policy_id`.
4. **Spreadsheet intake is unbuilt.** `fetch_pdfs` validates PDF payloads; `extract_pages` and the four steps after it open every fetched file with pymupdf; `src/lib/pipeline_runner.py:99-105` maps a step to a single input step, so there is no fan-in for a second action source. CAP annexes also convey some status by cell fill colour ("Colour key for Annex of Actions"), which needs an explicit fail-closed stance.

Also deferred, because they belong with that work: the three **Annex of Actions PDFs** (they exist to be action sources — declaring them `policy_role: action-plan` is what activates the actions path) and the **Q1&Q2 2026 legacy progress report** (blocked on item 3).
