## Purpose

Ensures every dataset published to data.publicinformation.ie is discoverable by humans from the site's landing and download pages, so that published data is actually findable as open data rather than sitting in unlinked directories.

## ADDED Requirements

### Requirement: Every latest-published dataset is listed on the Get the Data page

`get-the-data.html` SHALL list every dataset that publishes a `latest/<dataset>/` distribution. For each dataset the page SHALL provide a direct download link for every CSV table and a plain-English description of what the dataset contains.

#### Scenario: Single-table dataset is listed

- **WHEN** a dataset publishes exactly one CSV at `latest/<dataset>/<dataset>.csv`
- **THEN** `get-the-data.html` contains a section whose heading links to that CSV and whose description explains the dataset in plain English

#### Scenario: Multi-table dataset is listed

- **WHEN** a dataset publishes multiple CSVs under `latest/<dataset>/` (as public-body-actions does: `actions.csv`, `action-status-observations.csv`, `action-relationships.csv`)
- **THEN** `get-the-data.html` links to every CSV table and describes what each table contains in plain English

#### Scenario: public-body-actions is downloadable without technical knowledge

- **WHEN** a user opens `get-the-data.html`
- **THEN** they can reach all three public-body-actions CSV files and understand what actions, status observations, and relationships are without needing the technical README

### Requirement: Every latest-published dataset README is linked from the site reference list

`index.html` SHALL link the README (`latest/<dataset>/README.md`) of every dataset that publishes a `latest/<dataset>/` distribution in the `#reference` list.

#### Scenario: public-body-actions README is in the reference list

- **WHEN** a user opens `index.html`
- **THEN** the `#reference` list contains a link to `latest/public-body-actions/README.md`

#### Scenario: Reference list is complete

- **WHEN** the site publishes N datasets with `latest/` distributions
- **THEN** the `#reference` list contains N dataset README links

### Requirement: Dataset listing completeness is guarded by an automated test

An automated test SHALL derive the set of datasets that publish `latest/` distributions and assert that both `get-the-data.html` and the `index.html` reference list include every one of them. Datasets that publish only outside `latest/` (such as `documents`, served from `public/documents/`) SHALL be excluded from this check.

#### Scenario: Unlisted dataset fails the test suite

- **WHEN** a dataset with a `latest/` distribution is missing from `get-the-data.html` or from the `index.html` reference list
- **THEN** the test suite fails

#### Scenario: Documents library is not falsely required

- **WHEN** the guard test runs against the current catalogue
- **THEN** the `documents` dataset (no `latest/` distribution) does not cause a failure
