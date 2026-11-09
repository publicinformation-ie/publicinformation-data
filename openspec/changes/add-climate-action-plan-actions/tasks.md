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
- [x] 2.5 Prepare the contract update (schema: `action_number` string matching the reference pattern; `action_reference_printed` and `action_flags` required; `relationship`/`family` enums gain `part_of`/`structure`; CSVW columns) as `public-contract.patch`. It is applied in 5.2a, because it edits `public/`.
- [x] 2.6 Confirm `transform_public_body_actions.py` builds slash-preserving URIs (D2). Verify that a coded action's URI ends `/action/<slug>/EL/23/6/A`.
- [x] 2.7 Confirm the 29 `to_plan_hint: CAP` relationships keep a null `to_action_id` after CAP editions are present. Add a test.
- [x] 2.8 Regenerate transport output and verify against 2.1.0:
  - every `action_id`, `@id`, `action_number` value, observation key and relationship row is identical;
  - the only new fields are `action_reference_printed` and `action_flags`;
  - every **text** difference (`action_text`, `output`, `progress_text`, …) is a PDF-extraction repair from the table ligature fix (PR #11), shown by re-running the pre-ligature-fix extraction or by a classified diff listing each changed row.
  Identity was verified on 2026-11-09: 37 action rows and 54 observation rows differ in text only, for example "batet ry-electric" → "battery-electric". The ligature attribution is still to be shown.

## 3. Corpus curation

- [x] 3.1 Add the three `climate-action-plan-<year>-annex-of-actions` entries (`role: plan`, `policy_role: action-plan`, `policy_id: climate-action-plan`, publisher DCEE, `public_body_id: 1198`), with titles from the PDFs and dates from the pages. Verify that `load_documents()` passes and the `documents.yml` diff contains only these entries.
- [x] 3.2a Add an opt-in `action_table_layout` field to `documents.yml`, validated in `documents.py`, permitted only on `policy_role: action-plan` entries, with a closed set of flags (D7): `skip_subtitle_header` (a lone-cell row such as "Actions" is never chosen as the header; **superseded by 3.2f**) and `carry_header` (a headerless table continuing the previous page's table inherits its header). Implement both in `extract_actions` behind the field only. Verify with fixtures for each flag, an unknown flag (fatal), the field on a non-action-plan entry (fatal), and a table without the field read exactly as today.
- [x] 3.2b Blast radius: rerun `extract_actions` and the actions pipeline over **every** curated action plan. Verify that the SMP 2022–2025 and 2026–2030 outputs are byte-identical to the run before 3.2a.
- [x] 3.2f Replace `skip_subtitle_header` with `action_number_header` (D7, revised): the header is the first row with a cell that normalises to "action number", and every row above it is skipped. Verify with fixtures:
  - a lone "Actions" subtitle row above the header;
  - a multi-cell theme/KPI row plus a `Measure:` row plus "Actions" above the header;
  - a table without an "Action Number" row, which is a `carry_header` candidate;
  - `skip_subtitle_header` now rejected as unknown (fatal).
  Re-run the 3.2b byte-identical check for the SMP plans.
- [x] 3.2g Log each reference-bearing row in a table that is not read as an action table (for example `UnreadActionTable`, with document, page and the first reference seen), so the `carry_header` limit is visible rather than silent.
- [x] 3.2h `carry_header` ignores header-table columns that are empty in every row when comparing widths (D7, revised again). Verify with a fixture that has an 8-column header with an empty spacer column and a 7-column continuation (BE/23/34/B-D recovered), and a fixture where a non-empty column differs (still not carried). Re-run the 3.2b SMP check.
- [x] 3.2i Add `reference_corrections` (D8), validated in `documents.py`, allowed only on action-plan entries. Apply it to CAP23 p.57 `BE/23/36` → `BE/23/38` with evidence from the XLSX. Verify:
  - the corrected identity is used, and `action_reference_printed` keeps the misprint;
  - a correction whose printed reference isn't on its page is fatal;
  - the DuplicateActionReference on p.57 is gone.
- [x] 3.2j A "-" action cell inherits the parent row's text (D9), and a "-" row with no parent is excluded and logged. Verify with fixtures. Re-check the 61 "-" rows in reconciliation, and the 4 recorded mismatches (AD/23/8/A, AD/23/8/B, PS/23/12/A, PS/23/12/C) stay recorded with a reason.
- [x] 3.2c Set `action_table_layout` on the three annex entries, run each annex scoped (`--doc <slug> --force --stop-on-error`), and triage `errors.json` per step. Target per edition: `UnresolvedActionNumber` limited to rows whose reference is genuinely unreadable, each listed. Indicative row counts from source-notes: about 410 for CAP23, 126 for CAP24, 146 for CAP25 (82 after legacy exclusion).
- [x] 3.2d Annex document bundles: confirm whether `extract_actions` still runs on a `hold`-declared document. If it does, hold the 2023 and 2025 annex bundles (InvalidStructure), as the 2023 Plan is held. If it doesn't, stop and report.
- [x] 3.2e Edition year comes from the slug pattern `climate-action-plan-<year>-annex-of-actions`. A coded action-plan document whose slug doesn't match is a fatal error. Add a test.
- [x] 3.3 Confirm Plan PDFs and progress reports still yield zero action rows.

- [ ] 3.2k Match corrections by `text_starts` as well as `printed` (D8), replacing the last-occurrence rule. Verify: the CAP23 BE/23/38 correction still applies; a fixture where only the genuine BE/23/36 row remains is fatal and renames nothing; a fixture with two matching rows is fatal. Re-run the reconciliation: counts unchanged (445/126/82).

## 4. Reconciliation (D5)

- [x] 4.1 Write the reconciliation script (extracted actions vs XLSX codes and text, per edition). It reports missing references (blocking), text mismatches (fix or record a reason) and actions not in any XLSX (informational).
- [x] 4.2 Run it for CAP23, CAP24 and CAP25. Resolve every blocking item and commit the report as evidence in this change's directory.
- [x] 4.3 Pin `expected_action_count` on each annex entry from the reconciled extraction. Verify publication fails with a deliberately wrong pin.

## 5. Publication (3.0.0)

- [ ] 5.1 Gate: task 1.2 is done (the web consumer is live and accepts text).
- [ ] 5.2a Apply `public-contract.patch` (`patch -p1`, since the files are LFS-filtered) and add `part_of` to `relationships.VOCABULARY`, so the schema/vocabulary coupling tests pass. Commit the `documents.yml` annex entries in the same commit as the regenerated `public/documents/index.*`.
- [ ] 5.2 Publish `public/v3.0.0/public-body-actions/` and the `latest/` mirror. Set `owl:versionInfo "3.0.0"` and `dct:modified` on `public/catalog/dataset-public-body-actions.ttl`. Add a `public/CHANGELOG.md` entry naming the `action_number` type change, the new `action_reference_printed`/`action_flags` fields, the new `part_of`/`structure` values and the CAP23–25 editions. Note that transport text fields carry the table ligature repairs (see 2.8). State in the changelog and the dataset README that CAP24 and CAP25 annexes hold only new high-impact actions, not each plan's full roadmap.
- [ ] 5.3 Full verification matrix: `pipelines/document_pipeline` tests, `pipelines/actions_pipeline` tests, root `tests/`, and `uv run pyright`.
- [ ] 5.4 Review the full `public/**` diff before the publishing commit, and resolve orphans via `orphans.py` manifest → apply.

## Workflow follow-up

- Archive after publication. Then elaborate `add-climate-action-status-observations`, which depends on this change's identities and on the out-of-edition exclusions logged in 2.3.
