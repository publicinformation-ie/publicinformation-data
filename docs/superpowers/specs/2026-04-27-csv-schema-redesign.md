# CSV Schema Redesign

**Date:** 2026-04-27  
**Status:** Approved

## Context

This project stores data about Irish public bodies and their FOI (Freedom of Information) obligations across a set of CSV files. The files serve three downstream uses:

1. **Codeberg RSS** — each file committed to git generates an RSS feed; row-level `last_modified` provides clean change signal
2. **SQLite import** — files are imported into a relational database; `public_body_id` is the foreign key
3. **Pipeline input** — files represent sequential pipeline stages: public bodies → FOI pages → FOI details → disclosure files

## Design Decisions

### Intentional denormalisation
`public_body_name` is repeated in all child files. This is a conscious choice so each file is self-contained and human-readable when downloaded independently or viewed in an RSS entry. SQLite consumers join on `public_body_id`; the name column does not cause correctness problems.

### Tracking columns on every row
Every file carries `last_checked` and `last_modified` on each row:
- `last_checked` — updated every pipeline run, whether or not data changed
- `last_modified` — updated only when the row's data changes; this is the signal for RSS

### Merged FOI details
`public_body_foi_contact.csv` and `public_body_foi_disclosure_page_urls.csv` are merged into one file. Both are outputs of scraping the FOI page; their columns are nullable independently because the page may omit one or both values.

### Provenance in disclosure files
`source_page_url` in `public_body_foi_disclosure_files.csv` is intentional denormalisation — it records where each document link was found, for auditability and re-scraping purposes. `date_added` is immutable and distinct from `last_modified`.

## File Structure

| Old filename | New filename | Reason |
|---|---|---|
| `public_bodies_ireland.csv` | `public_bodies.csv` | Drop country suffix — single country, easy to add suffix later if needed |
| `public_body_foi_page_urls.csv` | `public_body_foi_pages.csv` | Drop redundant `_urls` |
| `public_body_foi_contact.csv` + `public_body_foi_disclosure_page_urls.csv` | `public_body_foi_details.csv` | Merge two closely related files |
| `public_body_foi_disclosure_file_urls.csv` | `public_body_foi_disclosure_files.csv` | Drop redundant `_urls` |

## Column Schemas

### `public_bodies.csv`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `public_body_id` | integer | no | Primary key |
| `public_body_name` | string | no | |
| `public_body_short_name` | string | yes | |
| `public_body_url` | string | yes | Main website URL |
| `public_body_category` | string | yes | |
| `last_checked` | date | no | |
| `last_modified` | date | no | |

### `public_body_foi_pages.csv`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `public_body_id` | integer | no | FK → `public_bodies.public_body_id` |
| `public_body_name` | string | no | Denormalised for portability |
| `foi_page_url` | string | no | |
| `is_reachable` | boolean | no | |
| `last_checked` | date | no | |
| `last_modified` | date | no | |

### `public_body_foi_details.csv`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `public_body_id` | integer | no | FK → `public_bodies.public_body_id` |
| `public_body_name` | string | no | Denormalised for portability |
| `foi_contact_email` | string | yes | May not be listed on FOI page |
| `foi_disclosure_page_url` | string | yes | May not be linked on FOI page |
| `last_checked` | date | no | |
| `last_modified` | date | no | |

### `public_body_foi_disclosure_files.csv`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `public_body_id` | integer | no | FK → `public_bodies.public_body_id` |
| `public_body_name` | string | no | Denormalised for portability |
| `source_page_url` | string | no | Provenance — page where document was found |
| `document_url` | string | no | |
| `date_added` | date | no | Immutable — when first discovered by pipeline |
| `last_checked` | date | no | |
| `last_modified` | date | no | |

## Naming Decisions

| Old name | New name | Reason |
|---|---|---|
| `foi_email` | `foi_contact_email` | Consistent with `data_structure.yml` |
| `foi_disclosure_url` | `foi_disclosure_page_url` | Consistent with contact file; explicit it's a page not a file |
| `Date Added` | `date_added` | snake_case |
| `Public Entity Name` | `public_body_name` | snake_case; consistent with all other files |
| `Source Page` | `source_page_url` | snake_case; explicit `_url` suffix |
| `Document Link` | `document_url` | snake_case; explicit `_url` suffix |
| `last_checked_date` | `last_checked` | Drop redundant `_date` suffix |

## Out of Scope

- `data_structure.yml` should be updated to reflect this schema but that is a separate task
- No changes to pipeline logic, only to the data contracts (column names and file names)
