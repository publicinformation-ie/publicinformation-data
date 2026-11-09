# Tasks

> **Scaffold.** Work packages only, at the granularity the open decisions allow. Elaborate into verifiable tasks after the decisions in §0 are taken and after `add-climate-action-plan-documents` is archived. Do not implement against this list as it stands.

## 0. Decisions (blocking — elaborate first)

- [ ] 0.1 **D-A** Action identity for alphanumeric CAP codes: widen `action_number` (MAJOR), add `action_code` alongside a synthetic integer (MINOR), or mint sequential integers (breaks citability) — and how sub-actions (`EL/23/6/A`) are represented. Decide the dataset version bump and the action URI shape in the same breath.
- [ ] 0.2 **D-B** How a carried-over action's observation is matched to the plan edition that declared it, given `build_observations` joins solely through `reports_on`.
- [ ] 0.3 **D-C** How an annex or report spanning plan years is expressed, given `documents.yml` allows one `reports_on` per report sharing its `policy_id`; includes the Q1&Q2 2026 legacy report, which has no 2026 plan.
- [ ] 0.4 **D-D** Spreadsheet plumbing: how a non-PDF document is acquired, how the PDF-only middle steps skip it, and whether a second action source arrives via a change to the shared `pipeline_runner` or an extension of the existing sibling-path convention.
- [ ] 0.5 Colour-coded status: whether fill-only status is an error or a reviewed source, and if reviewed, how the mapping is recorded and tested.
- [ ] 0.6 Re-read the sources before committing to any of the above — published counts and layouts in this proposal were read on 2026-11-07 and the listing pages are updated quarterly.

## 1. Annex of Actions PDFs become the plans' action sources

- [ ] 1.1 Curate the three Annex of Actions PDFs (slugs reserved: `climate-action-plan-<year>-annex-of-actions`), with titles read off the PDFs and dates off the DECC pages.
- [ ] 1.2 Repoint each of the nine progress reports' `reports_on` from its Plan PDF to its year's annex, and confirm the role flip is intentional per `extract_actions`' own curation note.
- [ ] 1.3 Supersede the documents-change requirement that CAP plan documents are not action sources.

## 2. Action extraction and identity

- [ ] 2.1 Extract declared actions from the annex PDFs, carrying each action's published reference.
- [ ] 2.2 Implement the identity decision from 0.1 end to end, including the schema, the transform, the action URI and the `CHANGELOG` entry.
- [ ] 2.3 Implement the attribution decision from 0.2, with unattributable observations excluded and logged.

## 3. Spreadsheet annex ingestion

- [ ] 3.1 Implement the acquisition and step-skipping decision from 0.4.
- [ ] 3.2 Implement fail-closed annex parsing with a reviewed per-layout header and status mapping, adapted (copied, not shared) from `foi_pipeline`'s disclosure-header chain, with fixture workbooks for recognised layout, unrecognised header, merged/multi-row header, and unmappable status and date cells.
- [ ] 3.3 Give `status_source: annex` its operational meaning: the declared annex supplies the report's observations.

## 4. Curation and verification

- [ ] 4.1 Curate the eleven XLSX annexes and the Q1&Q2 2026 legacy report listed in the proposal, scoped per document, triaging `errors.json` at every step.
- [ ] 4.2 Pin `expected_action_count` / `expected_status_counts` per entry once extraction stabilises, and decide whether publish-time enforcement is early enough.
- [ ] 4.3 Full verification matrix (three suites + `pyright`), plus confirmation that the transport corpus's actions and observations are unchanged.

## 5. Publication

- [ ] 5.1 Apply the dataset version bump decided in 0.1 to `public/catalog/dataset-public-body-actions.ttl` with a `public/CHANGELOG.md` entry.
- [ ] 5.2 Review the full `public/**` diff before the publishing commit; resolve orphans via `orphans.py` manifest → apply.

## Workflow follow-up

- Archive after the `public/` diff is reviewed and the publish is committed; verify the published dataset shows CAP actions and observations.
