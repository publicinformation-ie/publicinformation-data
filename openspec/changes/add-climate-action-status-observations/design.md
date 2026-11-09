# Design

> **Scaffold.** Records verified facts only and takes **no decisions**. D-B to D-F are stated in the proposal.

## Context

- **Observation joins.** `build_observations` looks up `mint_action_id(record["reports_on"], number)` and nothing else. `reports_on` is the live join key, and `documents.py:147-152` requires a report and its plan to share a `policy_id`. All CAP documents share `climate-action-plan` (archived documents change, D3), which is a precondition for cross-edition joins but not a mechanism for them.
- **Action sources.** After `add-climate-action-plan-actions`, the Annex of Actions PDFs are the CAP action sources, and progress reports still point at the Plan PDFs. Repointing `reports_on` to the annexes is therefore required before any CAP observation can join.
- **Step plumbing.** `fetch_pdfs` validates PDF content types and the `%PDF-` magic. `extract_pages:254-258` opens every fetched file with pymupdf, and `detect_structure`, `extract_figures`, `clean_text`, `assemble_sections` and `publish_bundles` follow it. `src/lib/pipeline_runner.py:99-105` resolves one input step per step. `actions_pipeline/pipeline.json` reaches into the document pipeline by absolute step path.
- **Prior art for spreadsheets.** `foi_pipeline`'s `transform_disclosure_files` → `extract_disclosures_detect_header_row` → normalize → canonicalize chain is a fail-closed Excel intake on `openpyxl` 3.1.5 / `xlrd` 2.0.1. Copy it, don't share it; extract it into `src/lib` only if a third domain needs it.
- **Status vocabulary.** `ActionStatusObservation.status` ∈ {Complete, OnSchedule, Delayed, Ongoing, Modified}. CAP annex statuses and the colour key must map into it or be excluded; widening it is a reviewed contract change.
- **Reference lists already read.** `add-climate-action-plan-actions` D5 reads the same XLSX files for reconciliation. Its scratch reader and the layouts it found are the starting point for D-D.

## Goals / Non-Goals

**Goals (indicative):**
- Quarterly CAP status observations publish against the CAP actions, dated from their report.
- Carried-over actions are attributed to the edition that declared them.
- All parsing fails closed.

**Non-Goals (indicative):**
- No change to action identity (owned by `public-body-actions-dataset`).
- No shared spreadsheet engine extracted from `foi_pipeline`.
- No CAP2019/2021 retro-ingestion.

## Risks / Trade-offs

- **Layout drift between quarterly workbooks.** Pinned `expected_status_counts` turn silent shrinkage into a loud failure, but only at publish time.
- **Record growth.** One observation per action per report makes a large publish diff, so triage `errors.json` per step before publishing.
- **Two pipelines touching Excel.** Accepted duplication, to be revisited if a third domain needs it.
