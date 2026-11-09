# Tasks

> **Scaffold.** Work packages only. Elaborate into verifiable tasks once §0 is decided and `add-climate-action-plan-actions` is archived. Do not implement against this list as it stands.

## 0. Decisions (blocking, elaborate first)

- [ ] 0.1 **D-B**: how an observation of a carried-over action is matched to the edition that declared it, given that joins currently go only through `reports_on`.
- [ ] 0.2 **D-C**: how an annex or report spanning plan years is expressed, including the Q1&Q2 2026 legacy report, which has no 2026 plan.
- [ ] 0.3 **D-D**: spreadsheet plumbing. How a non-PDF document is acquired, how the PDF-only middle steps skip it, and whether the second action source arrives via the shared `pipeline_runner` or the sibling-path convention.
- [ ] 0.4 **D-E**: colour-coded status. Is fill-only status an error or a reviewed source, and if reviewed, how is the mapping recorded and tested?
- [ ] 0.5 **D-F**: dating observations from the legacy-exercise workbook, which has no matching report.
- [ ] 0.6 Re-read the sources. Counts and layouts in the proposal were read on 2026-11-07, and the listing pages are updated quarterly.

## 1. Corpus

- [ ] 1.1 Repoint each progress report's `reports_on` to its year's Annex of Actions.
- [ ] 1.2 Curate the XLSX annexes and the Q1&Q2 2026 legacy report per the 0.2/0.3 decisions.

## 2. Spreadsheet annex ingestion

- [ ] 2.1 Implement the acquisition and step-skipping decision from 0.3.
- [ ] 2.2 Implement fail-closed annex parsing with a reviewed per-layout header and status mapping, adapted from `foi_pipeline`. Include fixture workbooks for a recognised layout, an unrecognised header, a merged/multi-row header, and unmappable status and date cells.
- [ ] 2.3 Give `status_source: annex` its operational meaning.

## 3. Attribution

- [ ] 3.1 Implement the 0.1 decision. Unattributable observations are excluded and logged, never assigned to the observing report's own plan.

## 4. Verification and publication

- [ ] 4.1 Pin `expected_status_counts` per report once extraction stabilises.
- [ ] 4.2 Full verification matrix, plus confirmation that transport observations are unchanged.
- [ ] 4.3 Version bump on `public-body-actions` (MINOR if no field changes), with a `CHANGELOG` entry. Review the `public/**` diff and resolve orphans.
