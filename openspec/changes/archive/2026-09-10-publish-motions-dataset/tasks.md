## 1. Transform and payloads

- [x] 1.1 Add `scripts/transform_motions.py`: read `pipelines/minutes_pipeline/steps/export_motions/output.json` and `pipelines/foi_pipeline/steps/find_public_bodies/output.json`; build records with `@id` = `{BASE_URI}/motion/{motion_id}`, `@type` `mot:Motion`, `public_body` via `body_uri(slug)`; raise on an unresolvable `public_body_id`
- [x] 1.2 Publish JSON-LD (`motions.jsonld`), CSV (`motions.csv`), and CSVW metadata (`motions.csv-metadata.json`) into `public/v1.0.0/motions/`, using `render_jsonld`/`render_csv`; copy the directory to `public/latest/motions/` only when content changes via `stamp_if_changed`
- [x] 1.3 Run the transform once and confirm both distributions are written and identical

## 2. Schema, vocabulary, and catalogue metadata

- [x] 2.1 Add `public/vocabularies/motion-status.csv` (+ `motion-status.csv-metadata.json`) with the six terms: `carried`, `carried_as_amended`, `not_carried`, `withdrawn`, `deferred`, `not_recorded`
- [x] 2.2 Add `public/schemas/motions.schema.json` (JSON Schema 2020-12) with the motion properties, required core fields, `status` enum matching the vocabulary, and `meeting_type` enum (`council`, `municipal_district`)
- [x] 2.3 Add `public/catalog/dataset-motions.ttl` (DCAT-AP 3.0): dataset URI, JSON-LD + CSV + CSVW distributions, `dct:relation` to public-bodies, `dct:conformsTo` the schema, `owl:versionInfo "1.0.0"`, and the `prov:wasGeneratedBy` block
- [x] 2.4 Add the hand-authored `public/v1.0.0/motions/README.md` documenting the data model, body-linkage join, status vocabulary, provenance, and known limitations

## 3. Discovery and documentation

- [x] 3.1 Add a motions section to `public/get-the-data.html` (CSV download link + plain-English description) and a `latest/motions/README.md` link to the `#reference` list in `public/index.html`
- [x] 3.2 Add a `public/CHANGELOG.md` entry for `motions 1.0.0`
- [x] 3.3 Update the dataset inventory in `README.md` and add the `transform_motions.py` pointer to `scripts/README.md` and `scripts/AGENTS.md`

## 4. Tests

- [x] 4.1 Add `tests/test_transform_motions.py` (record shape, slug resolution + unknown-id failure, JSON-LD wrapping, CSV flattening, `publish` changed/no-op)
- [x] 4.2 Add `tests/test_motions_schema.py` (valid schema, required fields, every published record validates, schema `status` enum matches the vocabulary)
- [x] 4.3 Run `uv run pytest tests/ -q` and `uv run pyright`, then review the `public/` diff
