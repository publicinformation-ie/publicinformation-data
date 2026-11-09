# Tasks

## 0. Source verification (before code)

- [ ] 0.1 Re-read the three Annex of Actions PDFs on the DCEE pages and record, for each edition: the direct PDF URL, title, publication date; how references are printed (confirm the year is embedded as in `EL/23/1`); whether sub-actions have parent rows with their own text (D3); and where legacy rows from earlier editions appear (D4). If the code format contradicts D2–D4, stop and revise the design.
- [ ] 0.2 Download each edition's quarterly XLSX annexes to scratch, and confirm they list action codes and text in a readable column layout for reconciliation (D5).

## 1. Web consumer first (D6)

- [ ] 1.1 In `publicinformation-web`, accept `action_number` as `number | string` (`src/lib/publicBodyActions.ts:11,32,91`), display it as printed, and replace the subtraction sort (`:130`) with a natural, segment-wise sort. Verify with tests for `"12"`, `"EL/23/1"` and `"EL/23/6/A"` ordering, and a 2.1.0 integer fixture still rendering unchanged.
- [ ] 1.2 Deploy that change while `latest/` is still 2.1.0, and confirm the live action pages are unchanged.

## 2. Identity and contract (actions_pipeline, schema, transform)

- [ ] 2.1 Recognise CAP codes as references in identity resolution alongside leading ordinals, and publish `action_number` as text. Verify with fixtures for an ordinal row (`"12"`), a coded row, a sub-action row, and an unreadable row (excluded and logged, no number minted).
- [ ] 2.2 Enforce the reference character set (`[A-Za-z0-9]` segments joined by `/`). Verify that a fixture with a stray character is excluded and logged.
- [ ] 2.3 Add the edition-year check (D4). Verify that a 2023-coded row in a 2025 annex fixture is excluded with the document, page and reference logged.
- [ ] 2.4 Emit `part_of` (`family: structure`, `method: extracted`) when a sub-action's parent is published in the same edition (D3). Verify both the parent-present and parent-absent cases.
- [ ] 2.5 Update `public/schemas/public-body-actions.schema.json`: `action_number` becomes a string matching the reference pattern, and the `relationship`/`family` enums gain `part_of`/`structure`. Update any published vocabulary to match.
- [ ] 2.6 Confirm `transform_public_body_actions.py` builds slash-preserving URIs (D2). Verify that a coded action's URI ends `/action/<slug>/EL/23/6/A`.
- [ ] 2.7 Confirm the 29 `to_plan_hint: CAP` relationships keep a null `to_action_id` after CAP editions are present. Add a test.
- [ ] 2.8 Regenerate transport output and verify: CSVs byte-identical to 2.1.0; JSON-LD differing only in `action_number` type; every `action_id` and `@id` identical.

## 3. Corpus curation

- [ ] 3.1 Add the three `climate-action-plan-<year>-annex-of-actions` entries (`role: plan`, `policy_role: action-plan`, `policy_id: climate-action-plan`, publisher DCEE, `public_body_id: 1198`), with titles from the PDFs and dates from the pages. Verify that `load_documents()` passes and the `documents.yml` diff contains only these entries.
- [ ] 3.2 Run each annex scoped (`--doc <slug> --force --stop-on-error`, bounded before any paid step), triage `errors.json` per step, and extend header aliases where an annex layout is new.
- [ ] 3.3 Confirm Plan PDFs and progress reports still yield zero action rows.

## 4. Reconciliation (D5)

- [ ] 4.1 Write the reconciliation script (extracted actions vs XLSX codes and text, per edition). It reports missing references (blocking), text mismatches (fix or record a reason) and actions not in any XLSX (informational).
- [ ] 4.2 Run it for CAP23, CAP24 and CAP25. Resolve every blocking item and commit the report as evidence in this change's directory.
- [ ] 4.3 Pin `expected_action_count` on each annex entry from the reconciled extraction. Verify publication fails with a deliberately wrong pin.

## 5. Publication (3.0.0)

- [ ] 5.1 Gate: task 1.2 is done (the web consumer is live and accepts text).
- [ ] 5.2 Publish `public/v3.0.0/public-body-actions/` and the `latest/` mirror. Set `owl:versionInfo "3.0.0"` and `dct:modified` on `public/catalog/dataset-public-body-actions.ttl`. Add a `public/CHANGELOG.md` entry naming the `action_number` type change, the new `part_of`/`structure` values and the CAP23–25 editions.
- [ ] 5.3 Full verification matrix: `pipelines/document_pipeline` tests, `pipelines/actions_pipeline` tests, root `tests/`, and `uv run pyright`.
- [ ] 5.4 Review the full `public/**` diff before the publishing commit, and resolve orphans via `orphans.py` manifest → apply.

## Workflow follow-up

- Archive after publication. Then elaborate `add-climate-action-status-observations`, which depends on this change's identities and on the out-of-edition exclusions logged in 2.3.
