# Proposal

## Why

The National Transport Authority publishes its annual Active Travel Investment Grant allocations only as PDFs: five editions (2022–2026), roughly 1,000 project rows each, grouped by local authority. Together they are the five-year record of what each walking and cycling scheme was allocated, but that record is locked in paginated tables that cannot be sorted, filtered by authority, or compared year-on-year — and roughly 420 project codes recur across 2024–2026, so the comparison is there to be made.

The dataset is unusually well-suited to this project's fail-closed principle: every authority section closes with a declared total that the project rows should add up to, and the 2025/2026 editions carry a body-level summary table in the same document. Extraction can therefore be *verified against the source's own arithmetic* rather than trusted.

## What Changes

- New pipeline `pipelines/activetravel_pipeline/` that ingests a committed list of NTA publications (year → publication page → PDF, with each document's kind), extracts the per-authority project tables, classifies structural rows (title, recipient heading, column header, project row, subtotal, total, footnote), parses euro amounts, and attributes every project row to a recipient and funding stream.
- Fail-closed reconciliation as the core gate: per-authority project rows must sum to the document's declared totals, and extracted authority totals must agree with the document's body-level summary. Any disagreement is recorded as an error for human review, and the affected figures are not published as if reconciled.
- New published dataset of project-level allocations for 2022–2026: year, recipient, `public_body_id` (local authorities only), project code, a provisional-code flag, project name, allocation in euro, funding stream, and the source document and page.
- New `scripts/transform_active_travel_allocations.py` publishing the dataset, plus DCAT-AP catalogue entry, JSON Schema, CSVW metadata, dataset README, `public/CHANGELOG.md` entry, `DATA_SOURCES.md` attribution, and the `get-the-data` / `index` discovery links.
- A `status.py` for the pipeline and regenerated pipeline documentation, following the repository norms.

Explicitly out of scope:

- **Mid-year revisions.** No revision history is maintained; a reissued PDF simply replaces the figures on the next run.
- **TII greenway project lists.** The 2026 publication page points at TII for those; only what the NTA PDFs contain is ingested.
- **Recipients that are not local authorities** (the `Campuses, Hospitals, SRTS and Others` block, e.g. TUD, Naas General, OPW). These are published using the recipient name as printed, with no public-body linkage.
- **2020–2021.** The publication series starts in 2022; earlier allocations have no equivalent page.

## Capabilities

### New Capabilities

- `active-travel-allocations-dataset`: the published dataset contract — versioned and `latest` distributions, record identity, local-authority body linkage, JSON-LD and CSV serialisations, catalogue metadata and schema, closed funding-stream vocabulary, and discoverability from the site entry pages.
- `active-travel-allocation-extraction`: how the annual PDFs become verified records — the committed publication list, table extraction and structural gating, row classification, amount normalisation with logged repairs, recipient attribution, and the reconciliation gates that decide what may be published.

### Modified Capabilities

None. The existing `source-file-references` capability already covers holding public-body files by URL with uncommitted bytes; this change adds no requirement to it.

## Impact

- New code: `pipelines/activetravel_pipeline/` (pipeline.json, process.py, status.py, steps/*/process.py + README.md, tests, committed publication list) and `scripts/transform_active_travel_allocations.py`; likely additions to `src/lib/` for row classification and euro parsing.
- New outputs: `pipelines/activetravel_pipeline/steps/export_allocations/output.json` and the published dataset under `public/latest/` plus a versioned directory.
- Public-facing files: `public/catalog/dataset-active-travel-allocations.ttl`, `public/schemas/`, `public/get-the-data.html`, `public/index.html`, `public/CHANGELOG.md`, `DATA_SOURCES.md`.
- Documentation: regenerated pipeline tables via `scripts/generate_pipeline_docs.py`, `AGENTS.md` step sequence update, new pipeline `README.md`.
- Network and side effects: five PDF downloads per run into an uncommitted cache; no Apify, LLM or database use. Publishing only happens when the generated `public/` diff is reviewed and merged.
