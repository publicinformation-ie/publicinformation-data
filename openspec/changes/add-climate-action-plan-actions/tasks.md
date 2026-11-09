# Tasks

## 0. Source verification (before code)

- [x] 0.1 Re-read the three Annex of Actions PDFs on the DCEE pages and record, for each edition: the direct PDF URL, title, publication date; how references are printed (confirm the year is embedded as in `EL/23/1`); whether sub-actions have parent rows with their own text (D3); and where legacy rows from earlier editions appear (D4). If the code format contradicts D2–D4, stop and revise the design.
- [x] 0.2 Download each edition's quarterly XLSX annexes to scratch, and confirm they list action codes and text in a readable column layout for reconciliation (D5).

## 1. Web consumer first (D6)

- [x] 1.1 In `publicinformation-web`, accept `action_number` as `number | string` (`src/lib/publicBodyActions.ts:11,32,91`), display it as printed, and replace the subtraction sort (`:130`) with a natural, segment-wise sort. Verify with tests for `"12"`, `"EL/23/1"` and `"EL/23/6/A"` ordering, and a 2.1.0 integer fixture still rendering unchanged.
- [ ] 1.2 Deploy that change while `latest/` is still 2.1.0, and confirm the live action pages are unchanged.

## 2. Identity and contract (actions_pipeline, schema, transform)

- [x] 2.1 Recognise CAP codes as references in identity resolution alongside leading ordinals, and publish `action_number` as text. Verify with fixtures for an ordinal row (`"12"`), a coded row, a sub-action row, and an unreadable row (excluded and logged, no number minted).
- [x] 2.1a Strip the recognised flags `*`, `**` and `(TF)` (any combination or order, with or without a preceding space) from identity. Publish `action_reference_printed` and `action_flags` (D2a). Verify with fixtures:
  - `TR/23/46(TF)` → `TR/23/46` with `[taskforce]`
  - `TR/24/4 (TF)` → `TR/24/4`
  - `RE/23/2*` → `[non_reportable]`
  - `TR/23/26**(TF)` → `[duplicate, taskforce]`
  - the same action printed with and without a flag → one action
  - `EL/23/4(X)` → excluded and logged
  - an ordinal row → printed == `action_number`, flags empty
  - a reference wrapped across lines in the text layer (`EN/23/` + `1*`, see source-notes) → read whole
- [x] 2.2 Enforce the reference character set (`[A-Za-z0-9]` segments joined by `/`). Verify that a fixture with a stray character is excluded and logged.
- [x] 2.3 Add the legacy check (D4): exclude rows whose code year is earlier than the edition year. Verify that a `/23/` row in a 2025 annex fixture is excluded, with the document, page and reference logged, and that a `/24/` row in a 2023 annex fixture is kept as a 2023 action.
- [x] 2.3a Emit `carried_forward_to` (`lineage`, `method: extracted`) from an earlier edition's action to a later edition's action with the same reference. Verify with a 2023 + 2025 fixture that both print `LU/25/1`.
- [x] 2.4 Emit `part_of` (`family: structure`, `method: extracted`) when a sub-action's parent is published in the same edition (D3). Verify both the parent-present and parent-absent cases.
- [ ] 2.5 (PREPARED, NOT APPLIED: see `public-contract.patch`; blocked by the no-commit-under-`public/` rule) Update `public/schemas/public-body-actions.schema.json`: `action_number` becomes a string matching the reference pattern, `action_reference_printed` (string, required) and `action_flags` (array of the closed set, required) are added, and the `relationship`/`family` enums gain `part_of`/`structure`. Update any published vocabulary to match.
- [x] 2.6 Confirm `transform_public_body_actions.py` builds slash-preserving URIs (D2). Verify that a coded action's URI ends `/action/<slug>/EL/23/6/A`.
- [x] 2.7 Confirm the 29 `to_plan_hint: CAP` relationships keep a null `to_action_id` after CAP editions are present. Add a test.
- [x] 2.8 Regenerate transport output and verify: CSVs identical to 2.1.0 apart from the added `action_reference_printed` and `action_flags` columns; JSON-LD differing only in `action_number` type and the added fields; every `action_id` and `@id` identical.

## 3. Corpus curation

- [x] 3.1 Add the three `climate-action-plan-<year>-annex-of-actions` entries (`role: plan`, `policy_role: action-plan`, `policy_id: climate-action-plan`, publisher DCEE, `public_body_id: 1198`), with titles from the PDFs and dates from the pages. Verify that `load_documents()` passes and the `documents.yml` diff contains only these entries.
- [ ] 3.2 (BLOCKED: headerless continuation tables, see report) Run each annex scoped (`--doc <slug> --force --stop-on-error`, bounded before any paid step), triage `errors.json` per step, and extend header aliases where an annex layout is new.
- [x] 3.3 Confirm Plan PDFs and progress reports still yield zero action rows.

## 4. Reconciliation (D5)

- [ ] 4.1 Write the reconciliation script (extracted actions vs XLSX codes and text, per edition). It reports missing references (blocking), text mismatches (fix or record a reason) and actions not in any XLSX (informational).
- [ ] 4.2 Run it for CAP23, CAP24 and CAP25. Resolve every blocking item and commit the report as evidence in this change's directory.
- [ ] 4.3 Pin `expected_action_count` on each annex entry from the reconciled extraction. Verify publication fails with a deliberately wrong pin.

## 5. Publication (3.0.0)

- [ ] 5.1 Gate: task 1.2 is done (the web consumer is live and accepts text).
- [ ] 5.2 Publish `public/v3.0.0/public-body-actions/` and the `latest/` mirror. Set `owl:versionInfo "3.0.0"` and `dct:modified` on `public/catalog/dataset-public-body-actions.ttl`. Add a `public/CHANGELOG.md` entry naming the `action_number` type change, the new `action_reference_printed`/`action_flags` fields, the new `part_of`/`structure` values and the CAP23–25 editions. State in the changelog and the dataset README that CAP24 and CAP25 annexes hold only new high-impact actions, not each plan's full roadmap.
- [ ] 5.3 Full verification matrix: `pipelines/document_pipeline` tests, `pipelines/actions_pipeline` tests, root `tests/`, and `uv run pyright`.
- [ ] 5.4 Review the full `public/**` diff before the publishing commit, and resolve orphans via `orphans.py` manifest → apply.

## Workflow follow-up

- Archive after publication. Then elaborate `add-climate-action-status-observations`, which depends on this change's identities and on the out-of-edition exclusions logged in 2.3.
