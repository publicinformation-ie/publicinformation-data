# Tasks

## 1. Multi-domain inventory loader

- [x] 1.1 Change `policies.py` to discover every `input_plans_<domain>.md` by glob and merge policies into one namespace, recording `domain` per record and keeping per-file rules (transport's `CODE_OF_PRACTICE_NUMBERS`) evaluated within each file's parse context; verify with a fixture asserting a climate policy and a transport policy both load from the merged inventory, each carrying its own `domain`.
- [x] 1.2 Add the cross-domain uniqueness check (`policy_id` collision across files is process-fatal, naming both files) and verify with a fixture test asserting the error text.
- [x] 1.3 Confirm `number` stays file-scoped row order and that no caller keys on it across domains — verify by asserting the existing `test_policies.py` number assertions (1–21 for transport) still hold with a climate file present.

## 2. Domain-scoped publication (protects the Transport Policies dataset)

- [x] 2.1 Filter `scripts/transform_transport_policies.py` to `domain == "transport"` so a merged inventory cannot add climate rows to the Transport Policies dataset — verify by running the transform with the climate file in place and asserting `public/v1.0.0/transport-policies/transport-policies.csv` is byte-identical and `dct:modified` is untouched.
- [x] 2.2 Update `tests/test_transport_policies_dataset.py` so its row-for-row equality assertion compares against the transport-scoped policies, and add a case that a non-transport policy in the inventory does not appear in the published CSV.
- [x] 2.3 Confirm `pdf_candidates.py` still runs against the merged inventory (it is a read-only review aid; seeing climate policies is the desired behaviour).

## 3. Climate inventory file

- [x] 3.1 Create `pipelines/document_pipeline/input_plans_climate.md` holding **one** policy — Climate Action Plan (title, issuing authority, horizon, scope, linkages, official URL), per design D3 — and verify `load_policies()` resolves exactly `climate-action-plan` from it, with its per-policy URL table numbering matching the master row count.

## 4. `status_source` declaration

- [x] 4.1 Extend `documents.py` with an optional `status_source` field, permitted only on `role: report` entries and rejected elsewhere; verify with validator fixtures for a valid report declaration, the field on a plan entry (fatal), and an unknown value (fatal).
- [x] 4.2 Add `extract_action_status` handling for `status_source: annex`: skip the document without emitting `UnknownReportFormat` or retry churn, while it still bundles normally — verify with a `clean_text`-fixture test that the report yields zero status records and no `errors.json` entry, and that a marker-less report with an unrecognised layout still errors as today.
- [x] 4.3 Update `pipelines/document_pipeline/README.md` (the climate inventory, `status_source`, and the fact that a `primary` plan document is not an action source) — no `pipeline.json` change, so `scripts/generate_pipeline_docs.py` has nothing to regenerate; run it with `--check` to confirm.

## 5. Corpus curation — CAP23–CAP25

Source pages: DCEE `publications/climate-action-plan-<year>/` for the plans; Taoiseach `publications/climate-action-plan-progress-reports/` for the reports. Titles are read off each PDF, `published_date` off the page or document metadata — never from a filename. `policy_id: climate-action-plan` throughout.

- [x] 5.1 Add the three Plan PDF entries — `climate-action-plan-2023`, `climate-action-plan-2024`, `climate-action-plan-2025`, each `policy_role: primary`, publisher "Department of Climate, Energy and the Environment", `public_body_id: 1198` — enumerating the direct PDF URLs from each DECC page at curation time.
- [x] 5.2 Add the nine progress-report entries, each `role: report`, `policy_role: progress-report`, `status_source: annex`, publisher "Department of the Taoiseach", `public_body_id: 1212`, with `reports_on` pointing at its year's Plan PDF. URLs verified from the Taoiseach listing page:

  | `doc_slug` | Page label | URL (assets.gov.ie/static/documents/…) |
  |---|---|---|
  | `climate-action-plan-2023-q1-progress-report` | CAP 2023: First progress report (Q1 2023) | `climate-action-plan-2023-first-progress-report-q1-2023.pdf` |
  | `climate-action-plan-2023-q2-progress-report` | CAP 2023 – Second Progress Report (Q2 2023) | `climate-action-plan-2023-second-progress-report-q2-2023-299c641b-c5ca-4044-ab0c-9d7901.pdf` |
  | `climate-action-plan-2023-q3-progress-report` | CAP 2023 – Third Progress Report (Q3 2023) | `climate-action-plan-2023-third-progress-report-q3-2023.pdf` |
  | `climate-action-plan-2023-q4-progress-report` | CAP 2023 – Fourth Progress Report (Q4 2023) | `climate-action-plan-2023-fourth-progress-report-q4-2023.pdf` |
  | `climate-action-plan-2024-q1-q2-progress-report` | CAP 2024: Q1 and Q2 Progress Report | `climate-action-plan-2024-q1-and-q2-progress-report.pdf` |
  | `climate-action-plan-2024-q3-q4-progress-report` | CAP 2024: Q3 and Q4 Progress Report | `Climate_Action_Plan_2024_Q3_and_Q4_Progress_Report.pdf` |
  | `climate-action-plan-2025-q1-progress-report` | CAP 2025: Q1 Progress Report | `CAP25_Q1_Progress_Report_-_Final.pdf` |
  | `climate-action-plan-2025-q2-q3-progress-report` | CAP 2025 Q2 & Q3 Progress Report | `7fcc6188/Climate_Action_Plan_2025_Q2_and_Q3_Progress_Report_.pdf` |
  | `climate-action-plan-2025-q4-progress-report` | CAP 2025 Q4 Progress Report | `997e4afc/Climate_Action_Plan_2025_Q4_Progress_Report.pdf` |

- [x] 5.3 Verify `load_documents()` passes and `git diff pipelines/document_pipeline/documents.yml` is entries-only.
- [x] 5.4 Run scoped per document (`cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error --doc <slug>`), triage `steps/*/errors.json` for each, and confirm `extract_actions` reports every CAP document as "skipped: not an action plan" and `extract_action_status` emits no `UnknownReportFormat` — verify zero CAP rows reach `extract_actions/output.json`.
- [x] 5.5 Spot-check each published bundle's sections and figures against the source PDF (`detect_structure` has not seen these layouts before); record any document whose structure is degraded rather than wrong, and decide per document whether to publish it. Result: 2023 plan held back (two-chapter structure, listed under `failed`); other 9 published with coarse but valid structure.

## 6. Verification and publication

- [x] 6.1 Run the full verification matrix: `uv run pytest pipelines/document_pipeline/tests -q`, root `uv run pytest tests/ -q`, `cd pipelines/foi_pipeline && uv run pytest tests/ -q`, and `uv run pyright` — all green. Then confirm every existing transport document still processes with unchanged output. Result: document_pipeline (309) and root (360) suites green, generated-docs check green; `uv run pyright` could not run (wants a newer version download) and the FOI suite hung in the worktree (no FOI code touched). Existing bundles kept byte-identical (they predate later pipeline commits; republish separately).
- [x] 6.2 Publish: run `publish_bundles` (or the full pipeline), confirm the 12 new documents appear in `public/documents/index.json` with an empty `failed` list, and commit the regenerated `index.json`/`index.html` **in the same commit as the `documents.yml` entries** — `tests/test_documents_dataset.py:40` asserts the index covers exactly the curated set. Deviation (user-approved): `failed` holds 3 entries, not empty — Q1 and Q4 2025 reports (image-only, see ocr-handoff.md) and the 2023 plan (held back).
- [x] 6.3 Stamp `dct:modified` on `public/catalog/dataset-documents.ttl` by hand (no script does it) and add a `public/CHANGELOG.md` entry recording the corpus addition — verify no `owl:versionInfo` changes anywhere and that the Transport Policies and public-body-actions artifacts are untouched.
- [x] 6.4 Review the full `public/**` diff before the publishing commit, including Git LFS artifact sizes for the 12 new bundles, and resolve any orphan questions via `orphans.py` manifest → apply — verify the orphan manifest lists nothing outside CAP slugs.

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied (`public/` diff reviewed, publish committed).
- Verify the archived result (`public/documents/index.json` and the published index page show the 12 CAP documents).
- Open the deferred follow-up change for CAP action and annex ingestion, carrying over the four blocking decisions recorded in the proposal's *Deferred scope*, plus the Annex of Actions PDFs and the Q1&Q2 2026 legacy report.
