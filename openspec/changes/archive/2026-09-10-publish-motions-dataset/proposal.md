## Why

`minutes_pipeline` now extracts and canonicalises motions moved at local-authority meetings, but its output exists only as raw, unversioned `public/motions/<slug>.json` files. They carry no JSON Schema, no DCAT-AP catalogue entry, no controlled vocabulary, no versioned/`latest` distribution, and are not listed on either entry page — so they are not yet usable as open data the way every other published dataset is.

## What Changes

- Add `scripts/transform_motions.py`, reading `minutes_pipeline/steps/export_motions/output.json` and publishing JSON-LD + CSV + CSVW metadata to `public/v1.0.0/motions/` and `public/latest/motions/`.
- Add `public/schemas/motions.schema.json` (JSON Schema 2020-12) for the motion record.
- Add `public/catalog/dataset-motions.ttl` (DCAT-AP 3.0), related to the Public Bodies dataset via `dct:relation`.
- Add `public/vocabularies/motion-status.csv` (+ CSVW metadata) for the closed status set (`carried`, `carried_as_amended`, `not_carried`, `withdrawn`, `deferred`, `not_recorded`); `meeting_type` stays a schema enum.
- Add a hand-authored `README.md` in both the versioned and `latest` directories documenting the data model, provenance, and limitations.
- List the dataset on `public/get-the-data.html` (CSV download + plain-English description) and on the `public/index.html` `#reference` list, satisfying the existing discovery guard test.
- Add a `public/CHANGELOG.md` entry and tests (`tests/test_transform_motions.py`, `tests/test_motions_schema.py`).
- Update the dataset-inventory prose in `README.md` (and `scripts/README.md`/`scripts/AGENTS.md` pointers) to include the new transform.

## Capabilities

### New Capabilities

- `motions-dataset`: the observable contract of the published motions dataset — its files, record shape, `@id`/`public_body` URIs, status vocabulary, DCAT-AP metadata, and versioning.

### Modified Capabilities

(none — the existing generic `open-data-discovery` requirement already covers every `latest/` dataset, so adding motions changes no discovery requirement; the guard test enforces it automatically)

## Impact

- **Code**: new `scripts/transform_motions.py`; tests under `tests/`.
- **Published data**: new `public/v1.0.0/motions/`, `public/latest/motions/`, `public/schemas/motions.schema.json`, `public/catalog/dataset-motions.ttl`, `public/vocabularies/motion-status.csv` (+ metadata); edits to `public/get-the-data.html`, `public/index.html`, `public/CHANGELOG.md`.
- **Docs**: `README.md` dataset inventory; `scripts/README.md` and `scripts/AGENTS.md` script table.
- **No pipeline changes, no new dependencies, no database changes.** `export_motions` already produces the source records; the raw `public/motions/<slug>.json` files remain as-is.
