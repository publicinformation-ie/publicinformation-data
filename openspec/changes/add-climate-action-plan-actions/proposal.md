# Proposal

## Why

`add-climate-action-plan-documents` (archived 2026-11-09) published the Climate Action Plan 2023–2025 plans and progress reports as documents, but none of their actions are in the `public-body-actions` dataset. These are the State's statutory climate commitments, and the dataset is where every other plan's actions are published and joined to public bodies.

Publishing the declared actions is blocked on one decision only, D-A below. The quarterly status data is blocked on four more decisions: cross-plan attribution, reports that span plans, spreadsheet intake and colour-coded status. That work is split into `add-climate-action-status-observations`, so the actions are not held hostage to the observations.

## What Changes

- Curate the three **Annex of Actions PDFs** (`climate-action-plan-<year>-annex-of-actions`) as `policy_role: action-plan`, making them the corpus's action sources. Plan PDFs and progress reports stay non-sources, and reports keep `reports_on` and `status_source: annex` unchanged.
- **Change the type of `action_number` from integer to text**, carrying the reference the plan prints: `EL/23/1`, or `12` for ordinal plans. This is a **BREAKING** change: `public-body-actions` goes **2.1.0 → 3.0.0**. Every existing `action_id` and action URI stays byte-identical, because both are built from the reference's text, which is the same for ordinal plans.
- Recognise CAP action codes in identity resolution, alongside leading ordinals. Rows that can't be read are excluded and logged, never numbered positionally.
- Action URIs keep the code's slashes as path segments (`/action/<slug>/EL/23/6/A`). References are restricted to ASCII letters, digits and `/`.
- Sub-actions publish as actions in their own right, with a new `part_of` relationship to a published parent. This adds a `structure` relationship family to the vocabulary.
- An annex row whose code names a different plan year (a legacy row) is excluded from that edition and logged.
- Before publishing, **reconcile** each edition's extracted actions against the Department of the Taoiseach's XLSX annexes. These are used as an independent reference list for checking only, not ingested. Each edition's `expected_action_count` is pinned.
- The web consumer (`publicinformation-web`) must accept a text `action_number` **before** `latest/` moves to 3.0.0. Today it turns non-numbers into `0` (`src/lib/publicBodyActions.ts:91`) and sorts by subtracting numbers (`:130`).

## Capabilities

### New Capabilities

- `public-body-actions-dataset`: the published contract of the actions dataset: identity, citability, URIs, sub-actions, assigning actions to an edition, reconciliation, existing editions left unchanged, and versioning. No spec covers this dataset today.

### Modified Capabilities

- `climate-action-plan-corpus`: adds the Annex of Actions documents to the corpus and makes them its action sources. This replaces "Plan documents are not action sources in this corpus".

## Impact

- `pipelines/document_pipeline/documents.yml`: three annex entries, with `expected_action_count` pinned once extraction stabilises.
- `pipelines/actions_pipeline/`: identity resolution (code recognition, edition-year check, text `action_number`), `part_of` relationships, and tests.
- `public/schemas/public-body-actions.schema.json`: `action_number` becomes a string, and the relationship enums gain `part_of` and `structure`.
- `public/vocabularies/` (if the relationship vocabulary is published there).
- `scripts/transform_public_body_actions.py`: URI and invariants, with the reference character set enforced.
- `public/v3.0.0/public-body-actions/`, the `latest/` mirror, `public/catalog/dataset-public-body-actions.ttl` (`owl:versionInfo` 3.0.0, `dct:modified`), and `public/CHANGELOG.md`.
- A reconciliation script and its evidence for the three editions.
- `../publicinformation-web`: accept text `action_number` and order by reference naturally. This must ship first.
- Unchanged: the transport editions' actions, observations and relationships (apart from `action_number` becoming text), progress-report entries, `fetch_pdfs` and `src/lib/pipeline_runner.py`.

## Decisions

**D-A (taken): `action_number` becomes text (MAJOR).** Alternatives rejected:
- Adding `action_code` next to a made-up integer gives two numbering schemes, and the permanent URI would use the made-up one.
- Numbering CAP actions sequentially breaks citability, since CAP actions are cited publicly as `EL/23/1`.
- Allowing integer *or* string is still a break for the web consumer, which coerces non-numbers to `0`.

See `design.md` for the URI, sub-action, edition-year and reconciliation decisions.

## Out of scope (→ `add-climate-action-status-observations`)

- Quarterly status observations, XLSX intake, repointing `reports_on` to the annexes, and colour-coded status.
- Attributing carried-over actions to their original plan (D-B), annexes and reports that span plans (D-C), and the Q1&Q2 2026 legacy report.
- CAP2019/CAP2021 editions. The 29 existing `to_plan_hint: CAP` relationships cite CAP21 numbers, and they stay unresolved.

## Dependencies

- `add-climate-action-plan-documents` is archived, so `climate-action-plan-corpus` is a main spec.
- The `publicinformation-web` change accepting a text `action_number` must land before `latest/` publishes 3.0.0.
