## Context

See proposal.md — Why. The relevant current state:

- `minutes_pipeline` step `export_motions` already writes a flat, canonical `output.json` (`{metadata, results}`) and, as a side effect, raw per-authority `public/motions/<slug>.json` files. Each canonical record already has `motion_id` (`<slug>/<meeting_date>/m<NNN>`), `public_body_id`, `public_body_slug`, `public_body_name`, `municipal_district`, `meeting_date`, `meeting_type`, `source_file_url`, `motion_text`, `proposer`, `seconder`, and `status`.
- Every curated dataset in the catalogue is produced by a `scripts/transform_*.py` that reads pipeline step output and writes JSON-LD + CSV + CSVW into `public/vX.Y.Z/<dataset>/` and `public/latest/<dataset>/`, using `src/lib/dataset_publish.py` (`render_jsonld`, `render_csv`, `stamp_if_changed`) and, where a body URI is needed, `src/lib/body_refs.py` (`build_body_slug_lookup`, `body_uri`).
- `public/catalog/` holds one DCAT-AP `.ttl` per dataset, `public/schemas/` one JSON Schema, and `public/vocabularies/` CSV controlled vocabularies (with `-metadata.json`) where a field is a closed set.
- `tests/test_dataset_discovery.py` derives the dataset set from `public/latest/*/` and asserts each dataset's CSVs are linked from `get-the-data.html` and its README from `index.html`'s `#reference` list. So once a `latest/motions/` distribution exists, those page edits become mandatory for the suite to pass.
- The status field is a closed set of six terms, already enforced by `canonicalize_motions` (`CANONICAL_STATUSES`). `meeting_type` is one of two derived values (`council`, `municipal_district`).

## Goals / Non-Goals

**Goals:**

- Publish motions as a first-class catalogued dataset, byte-compatible with the established JSON-LD/CSV/CSVW shape so the existing shared helpers and tests apply unchanged.
- Guarantee the `public_body` URI on every record is the same `@id` published in the Public Bodies dataset, or fail publication.
- Make the dataset discoverable on both entry pages, enforced by the existing guard test.

**Non-Goals:**

- No changes to `minutes_pipeline` or `export_motions`; the raw `public/motions/<slug>.json` files stay as they are.
- No new database tables, API, or web-repo consumer work (the sibling `publicinformation-web` repo is out of scope).
- No rendering or embedding of motion text beyond the dataset payloads; no full-text search.
- No removal or renaming of the existing `public/motions/` path.

## Decisions

### D1: A new `scripts/transform_motions.py`, following the `transform_who_does_what.py` pattern

The transform reads `pipelines/minutes_pipeline/steps/export_motions/output.json` and `pipelines/foi_pipeline/steps/find_public_bodies/output.json`, builds records, and publishes via the shared `dataset_publish` helpers. This is the established shape for a curated dataset and gives versioning, `dct:modified` stamping, CSVW, and schema/vocabulary consistency for free.

**Alternative considered:** catalog the raw `public/motions/<slug>.json` files in place. Rejected — that path has no JSON-LD/CSV/CSVW, no versioning, and no `latest/` distribution, so it would be the only dataset not following the contract and would not satisfy the discovery guard.

### D2: Source is the canonical flat step output, not the per-authority files

`export_motions/output.json` is the single deterministic source of all canonical records; re-reading the per-authority files would add a grouping step for no benefit. The per-authority `public/motions/<slug>.json` files remain as unversioned raw output alongside `public/foi-disclosures.json` and similar.

### D3: Record shape and URI scheme

Each motion becomes one JSON-LD node:

- `@id`: `https://data.publicinformation.ie/motion/{motion_id}` — stable, derived from the canonical id.
- `@type`: `mot:Motion` (namespace `mot:` = `https://data.publicinformation.ie/ns/motions#`).
- `public_body`: `body_uri(slug)` from `body_refs.py`, matching the public-bodies `@id`.
- `public_body_id`: retained for joins, matching the `public-body-actions` precedent for record datasets (link datasets keep only the URI).
- Retained verbatim: `motion_id`, `municipal_district`, `meeting_date`, `meeting_type`, `source_file_url`, `motion_text`, `proposer`, `seconder`, `status`.

CSV flattens `@id` to `id` (as `who-does-what` does) and carries the same fields.

**Body slug resolution:** the transform resolves `public_body_id` through `build_body_slug_lookup()` against the authoritative Public Bodies data and raises on an unknown id — never falling back to the motion's own `public_body_slug`. This guarantees the published URI matches public-bodies even if the minutes pipeline's slug drifts.

### D4: `status` gets a controlled vocabulary; `meeting_type` does not

`public/vocabularies/motion-status.csv` (+ `-metadata.json`) lists the six closed terms; the JSON Schema's `status` enum lists exactly the same terms (a test asserts the two agree). `meeting_type` (`council` | `municipal_district`) is a two-value derived flag, not a semantic controlled list, so it stays a schema enum without a vocabulary file.

### D5: Versioned distribution with a content-stamped `dct:modified`

Version 1.0.0. `scripts/transform_motions.py` writes `public/v1.0.0/motions/{motions.jsonld,motions.csv,motions.csv-metadata.json}`, stamps `public/catalog/dataset-motions.ttl` only when content changes (via `stamp_if_changed`), and on change copies the versioned directory to `public/latest/motions/`. The hand-authored `README.md` lives in the versioned directory and is carried to `latest/` by that copy.

### D6: DCAT-AP metadata modeled on the Who Does What dataset

`public/catalog/dataset-motions.ttl` declares the dataset at `.../dataset/motions`, with `dct:relation` to `.../dataset/public-bodies`, JSON-LD and CSV distributions (access/download URLs into `v1.0.0/` and `latest/`), `dct:conformsTo` the schema and CSVW, and the standard `prov:wasGeneratedBy` block. `owl:versionInfo` starts at `1.0.0`.

### D7: Discovery via the existing generic requirement

Add a motions section to `get-the-data.html` and a README link to the `index.html` `#reference` list. No new discovery capability or requirement is introduced — the existing guard test covers the new dataset automatically once `latest/motions/` exists.

### D8: Tests mirror the Who Does What tests

`tests/test_transform_motions.py` covers record building, slug resolution/failure, JSON-LD wrapping, CSV flattening, and the `publish`/`stamp_if_changed` no-op and changed cases. `tests/test_motions_schema.py` asserts the schema is valid, requires the core fields, and validates every published record; it also asserts the schema `status` enum matches `public/vocabularies/motion-status.csv`.

## Risks / Trade-offs

- [Slug drift between the minutes pipeline and public-bodies] → resolve through `build_body_slug_lookup()` against the authoritative source and raise on unknown id; never trust the motion's own `public_body_slug`.
- [The status closed set grows, invalidating the schema/vocabulary] → a new term is an additive change and gets a MINOR `owl:versionInfo` bump plus a CHANGELOG entry, per the dataset-versioning policy; the transform itself never invents a term.
- [Dataset grows large as more authorities are ingested] → JSON-LD + CSV remain single files; size is comparable to `foi-disclosures`, which already publishes a single large CSV, so no new mechanism is needed.
- [Page prose counts drift] → the guard test checks links, not prose; the count is updated in this change and future datasets are caught by the link check.

## Migration Plan

Purely additive. Land the transform, payloads, schema, vocabulary, catalogue TTL, README, tests, and page edits together; the raw `public/motions/` path is untouched. Rollback = revert the commit; no data migration and no consumers depend on the new paths yet.

## Open Questions

- Whether the raw per-authority `public/motions/<slug>.json` path should eventually be retired in favour of the `latest/motions/` distribution is deferrable and does not affect this change's specs, approach, or tasks.
