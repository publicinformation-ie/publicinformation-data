# Proposal

## Why

Git LFS stores a full new copy of a file on every change, so each FOI rescan costs 38–62 MB of LFS quota per output file even though only a few hundred rows actually change. FOI outputs used about 60% of the 563 MB of LFS quota spent in the last 30 days. Stored as ordinary git, the same changes cost 0.3–2.7 MB because git keeps only the differences.

## What Changes

- The FOI disclosures dataset is committed as one NDJSON file per public body under `public/latest/foi-disclosures/bodies/`, one row per line. Each file is serialised canonically, so a body whose rows didn't change produces a byte-identical file. These files are kept in ordinary git, not LFS, and diff and merge as text.
- **BREAKING (repo layout only):** the combined `public/foi-disclosures.json`, the derived `public/latest/foi-disclosures/foi-disclosures.{csv,jsonld,xlsx}` and the per-body index `bodies/manifest.json` are no longer committed. They are built from the per-body files by the export step (so a local checkout stays current), when the site is deployed, and when a release tag is pushed. Their public URLs on `data.publicinformation.ie` stay the same.
- The manifest is an index for people and agents: for each body it gives the name, `public_body_id`, file path and URL, row count, `date_received` range and sha256.
- Versioned releases are published to bunny.net storage, served from a project-owned hostname (`releases.publicinformation.ie`), when a `foi-disclosures-v<schema>+<build>` tag is pushed (e.g. `foi-disclosures-v1.0.0+20261113`). The schema version stays the stable `DATASET_VERSION` contract through many builds; the build identifier, the UTC release date, tells builds apart. This extends the existing `foi-disclosures-v1.0.0` tag convention. Each release folder is written once and never changed. There is no `latest/` copy on bunny; Pages remains the single "latest". Publishing is a script that doesn't depend on GitHub, so the git host can change without changing where releases live.
- `foi-disclosures.xlsx` gets a builder. It has been stale since 2026-10-04 because nothing writes it.
- `public/disclosure-files.json` (0.6 MB) and `pipelines/foi_pipeline/steps/transform_disclosure_files/output.json` move from LFS to ordinary git. The step output drops its `completed_at` timestamp, which changed on every run even when the data didn't.
- Files downloaded from public bodies are referenced by URL and checksum instead of committed. The ten Climate Action Plan annex `.xlsx` files in `fetch_status_annexes/annexes/` move to a download cache that isn't committed.

## Capabilities

### New Capabilities

- `foi-disclosures-dataset`: how the FOI disclosures dataset is stored in the repo (per-body NDJSON files, canonical serialisation), how its built forms (combined JSON, CSV, JSON-LD, XLSX, manifest) are produced and served, and how versioned releases are published.
- `source-file-references`: how files that come from public bodies are held, as a source URL plus a committed checksum, fetched into a cache that isn't committed and verified before use.

### Modified Capabilities

(none; `climate-action-plan-corpus` keeps its requirements, and only where the annex files are stored changes)

## Impact

- **Code**:
  - `pipelines/foi_pipeline/steps/export_status/process.py` (writers at :252–265)
  - `scripts/transform_foi_disclosures.py:15–22`
  - a new builder for the combined files, the XLSX and the manifest
  - `pipelines/document_pipeline/steps/fetch_status_annexes/process.py`
  - `pipelines/document_pipeline/steps/extract_annex_status/process.py:414,514`
  - `pipelines/document_pipeline/documents.yml` (annex checksums)
- **Repo config**: `.gitattributes` (FOI text paths leave LFS), `.gitignore` (built files, annex cache).
- **CI**: `.github/workflows/deploy-pages.yml` installs the pinned build dependency and builds the combined files before uploading the site. A new release workflow, triggered by a `foi-disclosures-v*` tag push, calls `scripts/publish_artifacts.py` to upload them to bunny.net.
- **New dependency**: a bunny.net Storage Zone and Pull Zone, a `releases.publicinformation.ie` CNAME to the Pull Zone, and CI secrets (`BUNNY_STORAGE_ZONE`, `BUNNY_STORAGE_KEY`).
- **Tests**:
  - `tests/test_transform_foi_disclosures.py`
  - `pipelines/foi_pipeline/tests/test_export_status.py`
  - `tests/test_readme_dataset_counts.py`
  - the annex step tests
- **Docs**:
  - `README.md`
  - `public/README.md`, `GET_THE_DATA.md`, `QUICKSTART.md`, `quickstart.html`, `get-the-data.html`, `DATA_QUALITY.md`
  - `public/latest/foi-disclosures/README.md`
  - `public/catalog/dataset-foi-disclosures.ttl`
- **Downstream**: `publicinformation-web` `scripts/seed/fetch.ts` reads `https://data.publicinformation.ie/latest/foi-disclosures/foi-disclosures.csv`. That URL keeps working, so no web change is needed. Local-path seeding against a repo checkout works once the export step or the build script has run.
- **Consumers who clone the repo** now need Python and openpyxl to get the combined files. The docs lead with the site URLs so most consumers never need to.
- **Not recovered**: LFS quota already spent stays in history.
- **Out of scope**: `public/documents/**/bundle.tar.gz`, which cost about 147 MB in the last 30 days, is a separate follow-up. The other datasets' `public/vX.Y.Z/` snapshots are unchanged.
