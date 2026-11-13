# Spec Delta

## Purpose

Defines how the FOI disclosures dataset is stored in the repository and how its built and released forms are produced, so that a rescan's storage cost tracks the rows that changed rather than the size of the dataset.

## ADDED Requirements

### Requirement: Disclosures are stored one file per public body

The committed FOI disclosures dataset SHALL consist of one NDJSON file per public body at `public/latest/foi-disclosures/bodies/<public_body_id>.ndjson`, holding that body's disclosure rows, one row per line. A body with no rows SHALL have no file.

#### Scenario: Rows land in their body's file

- **WHEN** the export step writes the disclosures dataset
- **THEN** every row appears on exactly one line of exactly one file, the file named for its `public_body_id`, and no file holds rows of another body

#### Scenario: Body loses all rows

- **WHEN** a rescan leaves a body with no disclosure rows
- **THEN** that body's file is removed

#### Scenario: Row without a body

- **WHEN** the export step is given a row with no `public_body_id`
- **THEN** it fails naming the row and writes no files

### Requirement: Per-body files are canonical

Each per-body file SHALL hold one compact JSON object per line, with keys in a fixed field order, non-ASCII characters written as UTF-8 except U+2028 and U+2029 which are escaped, rows ordered by `row_id`, LF line endings, a trailing newline, and no run-specific values such as timestamps. Identical rows SHALL produce a byte-identical file.

#### Scenario: Unchanged body is untouched by a rescan

- **WHEN** the export runs twice on the same input rows
- **THEN** every per-body file is byte-identical between the two runs

#### Scenario: Rescan touches a subset of bodies

- **WHEN** a rescan changes rows for some bodies only
- **THEN** only those bodies' files differ from the previous commit

#### Scenario: Verification

- **WHEN** verification runs over the per-body folder
- **THEN** it passes only if every line parses, every row's `public_body_id` matches its filename, rows are in `row_id` order, no `row_id` appears in two files, and each file equals its canonical re-serialisation

### Requirement: Dataset text files are stored as text in ordinary git

The per-body files, `public/disclosure-files.json` and the `transform_disclosure_files` step output SHALL be committed as ordinary git files, not LFS pointers, and SHALL diff and merge as text. No committed FOI file SHALL exceed 45 MB.

#### Scenario: Attributes exclude the dataset from LFS

- **WHEN** `git check-attr filter diff merge` is run on any of these paths
- **THEN** `filter` does not report `lfs`, and none of `filter`, `diff` or `merge` is reported as `unset` or `lfs`

#### Scenario: Size guard

- **WHEN** a committed FOI text file grows past 45 MB
- **THEN** a test fails naming the file

### Requirement: Step output carries no volatile timestamp

The committed `transform_disclosure_files` output SHALL NOT contain a value that changes on every run independent of the data, such as a completion timestamp.

#### Scenario: Rerun on unchanged inputs

- **WHEN** the step reruns with unchanged inputs and caches
- **THEN** its committed output is byte-identical to the previous one

### Requirement: Built forms are built, not committed

The combined `foi-disclosures.json`, the CSV, JSON-LD and XLSX forms, and `bodies/manifest.json` SHALL be built from the per-body files and SHALL NOT be committed. The built rows SHALL equal the union of the per-body rows. The export step SHALL run the build after writing the per-body files.

#### Scenario: Building from the stored dataset

- **WHEN** the build is run on a checkout
- **THEN** it writes the combined JSON, CSV, JSON-LD and XLSX, each holding exactly the per-body files' total row count, and the manifest

#### Scenario: Export leaves built files current

- **WHEN** the export step finishes
- **THEN** the local built files reflect the per-body files it just wrote

#### Scenario: Built files are ignored by git

- **WHEN** the build has run locally, including on a fresh checkout with no built files present
- **THEN** `git status` shows no new or modified files from it, including the catalog `.ttl`

### Requirement: Content date follows the stored data

The catalog's `dct:modified` for the FOI disclosures dataset SHALL be updated by the export step only when it changes, adds or removes a per-body file. Building the combined forms SHALL NOT change it.

#### Scenario: Export with changed rows

- **WHEN** the export step writes per-body files that differ from those on disk
- **THEN** `dct:modified` in `public/catalog/dataset-foi-disclosures.ttl` is set to the run date

#### Scenario: Export with unchanged rows

- **WHEN** the export step writes per-body files identical to those on disk
- **THEN** the `.ttl` is unchanged

#### Scenario: Deploy build

- **WHEN** CI builds the combined forms from a fresh checkout
- **THEN** the served `dct:modified` is the committed value, not the deploy date

### Requirement: Manifest indexes the dataset

The built `bodies/manifest.json` SHALL list every per-body file with its `public_body_id`, body `name`, relative `path`, absolute `url` on `data.publicinformation.ie`, `row_count`, `date_received_min`, `date_received_max` and `sha256`, together with the dataset's total row and body counts, `schema_version`, `build` (null outside a release) and the source commit. It SHALL be deterministic for the same per-body files.

#### Scenario: Finding a body by name

- **WHEN** a consumer or agent reads the manifest
- **THEN** it can find a body's file URL and row count by body name without opening any per-body file

#### Scenario: Manifest agrees with files

- **WHEN** the manifest is built
- **THEN** every listed sha256 and row count matches its file, and every per-body file is listed

### Requirement: Published URLs are unchanged

The deployed site SHALL serve the built combined files at the URLs they had before this change, including `/foi-disclosures.json` and `/latest/foi-disclosures/foi-disclosures.{csv,jsonld,xlsx}`, and SHALL also serve the per-body files and manifest under `/latest/foi-disclosures/bodies/`.

#### Scenario: Downstream seed fetch

- **WHEN** a consumer fetches `https://data.publicinformation.ie/latest/foi-disclosures/foi-disclosures.csv` after a deploy
- **THEN** it receives the CSV built from the deployed commit's per-body files

### Requirement: Versioned releases are immutable

Pushing a `foi-disclosures-v<schema>+<build>` tag SHALL publish `foi-disclosures/v<schema>/<build>/` to release storage (a bunny.net Storage Zone), holding the combined JSON, CSV, JSON-LD and XLSX built from the tagged commit, the built `manifest.json` and `SHA256SUMS`. An existing build's folder SHALL never be overwritten.

#### Scenario: First publish of a build

- **WHEN** tag `foi-disclosures-v1.0.0+20261113` is pushed, `DATASET_VERSION` is `1.0.0`, and no `foi-disclosures/v1.0.0/20261113/` exists
- **THEN** the folder is created with the six files, each matching its `SHA256SUMS` entry, with row counts equal to the manifest's, and the manifest records schema `1.0.0` and build `20261113`

#### Scenario: Republishing an existing build

- **WHEN** publishing runs for a build whose folder already exists
- **THEN** it fails without modifying any file in that folder

### Requirement: Release identity is schema version plus build

A release SHALL be identified by the schema version and a build identifier. The schema version SHALL equal the dataset's `DATASET_VERSION` (`owl:versionInfo`) and stay stable across builds. The build SHALL be the UTC release date `YYYYMMDD`, optionally followed by `.<n>`. Both SHALL be recorded in the release manifest. Tags that don't start with `foi-disclosures-v` SHALL NOT publish FOI data.

#### Scenario: Schema mismatch

- **WHEN** tag `foi-disclosures-v1.1.0+20261113` is pushed but `DATASET_VERSION` at that commit is `1.0.0`
- **THEN** publishing fails before uploading anything

#### Scenario: Tag without a build

- **WHEN** a tag such as `foi-disclosures-v1.0.0` with no build part is pushed
- **THEN** publishing fails before uploading anything

#### Scenario: Unrelated tag

- **WHEN** a repo-wide `v3.3.0` or `public-bodies-v1.1.0` tag is pushed
- **THEN** no FOI release is published

### Requirement: Release URLs use a project-owned hostname

Release files SHALL be served and documented at `https://releases.publicinformation.ie/foi-disclosures/v<schema>/<build>/`. Docs and the catalog SHALL NOT cite the CDN provider's own hostname. Release storage SHALL hold no `latest/` copy; the site's `/latest/` is the only latest.

#### Scenario: Fetching a release

- **WHEN** a consumer fetches `https://releases.publicinformation.ie/foi-disclosures/v1.0.0/20261113/SHA256SUMS`
- **THEN** it receives that release's checksums

### Requirement: Publishing is independent of the git host

Publishing SHALL be one command whose credentials come from environment variables. It SHALL support a local-directory target that produces the same layout as release storage.

#### Scenario: Dry run without CI

- **WHEN** the publish command runs on a checkout with the local-directory target and no CI environment
- **THEN** it writes the same tree of files that the release storage would receive

### Requirement: XLSX reflects current data

The XLSX form SHALL hold the same rows and columns as the CSV form built from the same commit.

#### Scenario: XLSX and CSV agree

- **WHEN** both are built from one commit
- **THEN** their header rows match and their data rows are equal as values
