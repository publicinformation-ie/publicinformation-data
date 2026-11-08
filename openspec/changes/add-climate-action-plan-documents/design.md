# Design

## Context

The document pipeline is a single hand-authored-input machine: `documents.yml` (validated by `documents.py`) keys every downstream step on `doc_slug`, and `policy_id` must resolve against the transport policy inventory parsed from `input_plans_transport.md` by `policies.py`. Both validators are process-fatal by design. That inventory is the only thing standing between the pipeline and the CAP corpus: nothing else about publishing a PDF bundle is transport-specific.

Two existing behaviours do the heavy lifting here, and both were verified rather than assumed:

- `extract_actions/process.py:380-390` treats a document as an action source **only** when `policy_role: action-plan`. A plan document declared `primary` is skipped with "not an action plan". This is what lets the CAP corpus be published as documents without touching the actions path.
- `extract_action_status/process.py:415` processes only `role: report` documents, and emits `UnknownReportFormat` (`:327`) for a report whose annex layout it does not recognise. Nine CAP reports would mean nine such errors every run.

Full motivation, and the evidence behind the deferred half, are in the proposal; behavioural contracts are in the two spec deltas.

## Goals / Non-Goals

**Goals:**
- CAP23–CAP25 plans and progress reports publish as document bundles through the existing step machinery, with no new step and no runner change.
- A climate `policy_id` resolves for validation without altering the transport inventory or the published Transport Policies dataset.
- Zero action or status records are produced for the CAP corpus in this change — by existing mechanism, not by suppression.

**Non-Goals:**
- No action extraction, no spreadsheet intake, no `actions_pipeline` or `public-body-actions` change, no `fetch_pdfs` payload relaxation. See the proposal's *Deferred scope*.
- No run-time scraping of the gov.ie listing pages: they are enumerated once per document during curation, and `documents.yml` stays the single curated source.
- No CAP2019/2021 retro-ingestion, and no CAP2026 (no plan has been published; the 2026 progress report covers legacy actions only).

## Decisions

### D1. Second inventory file; loader merges per-domain files
`policies.py` discovers every `input_plans_<domain>.md` (glob) and merges the parsed policies into one validation namespace, recording `domain` on each record. `policy_id` collision across files is process-fatal, naming both files. Domain-specific row rules (transport's `CODE_OF_PRACTICE_NUMBERS`) are evaluated within each file's parse context. `number` stays what it is today — row order **within its file** — so it is no longer unique across the merged set; nothing may key on it alone.
**Alternatives rejected:** appending climate rows to the transport table (pollutes a domain-pure file, and the transport `CODE_OF_PRACTICE` cross-check would need exceptions); generalising the transport file's prose while its name still says "transport".

### D2. Inventory-derived datasets filter to their own domain
`scripts/transform_transport_policies.py:83` publishes `build_rows(load_policies(), …)` straight into `public/v1.0.0/transport-policies/transport-policies.csv`, and `tests/test_transport_policies_dataset.py:57` asserts the published rows equal `load_policies()` row-for-row. A merged loader therefore publishes climate rows into the Transport Policies dataset unless the transform filters on `domain`. The regression test is that the published CSV is **byte-identical** after the change.
Whether climate policies get a dataset of their own is a separate publish-product decision, deliberately not taken here.

### D3. Annual plans are editions of one policy, not three policies
The climate inventory holds **one** policy, `climate-action-plan`, and each annual Plan PDF is a `policy_role: primary` document under it. This follows the NSMP precedent already in the inventory (one standing policy, several dated documents), and matches how DECC describes CAP23 — "the second annual update to Ireland's Climate Action Plan 2019", not a new policy each year.

It also keeps the follow-up change possible. `documents.py:147-152` requires a report and the plan it reports on to share a `policy_id`; with one policy per year, a report observing a carried-over CAP23 action could never point at the plan that declared it. One policy keeps every CAP document in one `policy_id` namespace, while per-year identity stays where the code already puts it — `resolve_action_identity` namespaces actions by the plan document's `doc_slug`, not by `policy_id`.
**Consequence to note:** one policy will have three `primary` documents. Nothing in the pipeline constrains the number of primaries per policy (checked), but it is novel for this inventory.

### D4. Annex of Actions PDFs are deferred, not mislabelled
Each plan year also has a separate *Annex of Actions* PDF, published by DECC after the plan itself (CAP23's on 7 March 2023), and it — not the Plan PDF — carries the implementation detail. It is excluded from this change because declaring it truthfully as `policy_role: action-plan` is exactly what makes `extract_actions` treat it as an action source, which feeds `actions_pipeline` ~290 unresolvable CAP23 rows and drowns the NSMP corpus's real errors.

The cost is that the follow-up change must repoint each report's `reports_on` from the Plan PDF to the Annex PDF once the annex becomes the action source. That is a nine-line curated edit, not a slug change, and that change has to decide which document is the action source anyway. `climate-action-plan-<year>-annex-of-actions` is reserved for those slugs.
**Alternatives rejected:** declaring the annexes `primary` now and flipping the role later (`policy_role` is published in `index.json`, so that publishes a wrong value in the meantime); adding a suppression field to `documents.yml` whose only purpose is to be removed by the next change.

### D5. `status_source: annex` as an explicit declaration
Report entries whose status detail is published in a companion spreadsheet gain `status_source: annex`; `extract_action_status` skips them **by declaration** — no record emitted, no `UnknownReportFormat`, no retry churn. The field states where the data lives, which is true today and stays true after the follow-up gives it operational meaning (fetch and parse that annex), so it will not need renaming. A report *without* the marker whose layout is unrecognised still errors exactly as it does today.
**Alternative rejected:** teaching `extract_action_status` the CAP PDF report layouts — the spreadsheet annex is the authoritative machine-readable record, so reverse-engineering the PDFs adds failure surface for data we will get properly later.

### D6. Content addition, no version bump
No field name, type or vocabulary changes, so no `owl:versionInfo` bump: `dataset-documents.ttl` gets a `dct:modified` stamp (by hand — no script stamps it; `tests/test_documents_dataset.py:31` only asserts a stampable line exists), the Transport Policies dataset must not change at all, and `public-body-actions` is untouched. A `public/CHANGELOG.md` entry records the corpus addition.

## Risks / Trade-offs

- **Curation volume** — 12 entries nearly doubles `documents.yml` (25 today). Titles come off the PDFs and dates off the listing pages; neither is guessed from a filename.
- **`index.json` and `documents.yml` must land together** — `tests/test_documents_dataset.py:40` asserts `published ∪ failed == curated`, so adding entries without a publishing run is a red root suite. Not a risk to data, but it forbids splitting curation and publication across commits.
- **Bundle size in Git LFS** — the CAP plans are large documents and all bundles are LFS-tracked (`test_bundles_and_index_are_lfs_tracked`). Review the artifact sizes in the publish diff.
- **Structure detection on unseen layouts** — the CAP PDFs have not been through `detect_structure` before; a poor TOC parse degrades a bundle's sections without failing. `errors.json` triage per document before publishing is the control, and `--doc` scoping keeps it per-document.
- **Merged inventory widens `load_policies()`' blast radius** — three callers (`documents.py`, `transform_transport_policies.py`, `pdf_candidates.py`). D2 covers the one that publishes; the other two are validated by tests.

## Migration Plan

1. Land code first, zero data movement: D1 loader merge (+ cross-domain uniqueness tests), D2 domain filter (+ byte-identical transport CSV check), D5 marker in `documents.py` and `extract_action_status` (+ fixture tests). Transport pipeline outputs verified unchanged.
2. Add `input_plans_climate.md` with the single `climate-action-plan` policy.
3. Curate the 12 entries, reading titles off the PDFs and dates off the listing pages, with verified body ids (DCEE 1198 for the plans, Department of the Taoiseach 1212 for the progress reports).
4. Run scoped per document: `cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error --doc <slug>`; triage `errors.json` at every step.
5. Publish: bundles via `publish_bundles`, regenerated `index.json` committed with the entries, `dct:modified` stamp, `public/CHANGELOG.md` entry, `public/**` diff review before the commit that publishes.

Rollback: revert the `documents.yml` entries (they drop from the next publish) and decline deploy; leftover published artifacts are removed with `orphans.py`'s manifest→apply two-stage deletion.

## Open Questions

- Whether climate policies get their own catalog dataset (`dataset-climate-policies.ttl`) or stay covered by `dataset-documents`. D2 forces the domain filter either way, so this is a publish-product decision that can trail the corpus.
- Whether the CAP23 plan's March 2023 digital re-issue (typographical corrections) is the edition to curate, or the December 2022 launch PDF. Resolved by reading the DECC page at curation time; it affects `published_date`, not identity.
