# Proposal

## Why

The SPC dataset already classifies agenda items with COFOG 1999, and the site publishes a flat CSV of the codes. But the classification is not usable as a framework: there is no machine-readable hierarchy, the term URIs (`https://data.publicinformation.ie/ns/cofog#04.5.1`) return 404, and the only description of a class is "COFOG 1999 class (CS)". The UN is revising COFOG, with the update expected by 2028, so the 1999 scheme needs a stable, versioned, publishable form now. This is a small, self-contained publication change — not a new classification exercise.

## What Changes

- Publish the COFOG 1999 vocabulary as a first-class open vocabulary:
  - a canonical JSON file at `public/vocabularies/cofog-1999.json` with scheme metadata, nested divisions → groups → classes, a flat concept index, parent and level, and the source's CS/IS service type;
  - a SKOS Turtle file at `public/vocabularies/cofog-1999.ttl`;
  - the existing CSV and CSVW metadata retained as a distribution, in the same four-column shape.
- Make the term URIs dereferenceable with a resolver page at `public/ns/cofog/index.html`; keep `https://data.publicinformation.ie/ns/cofog#<code>` as the COFOG 1999 namespace.
- Add one build script, `scripts/build_cofog_vocabulary.py`, that reads the pinned `pipelines/spc_pipeline/reference/cofog_1999.json`, validates the hierarchy, writes all three formats, and supports `--check`.
- Remove COFOG CSV generation from `pipelines/spc_pipeline/scripts/build_vocabularies.py` so there is a single writer; the SPC schema enum and every published SPC record are unchanged.
- Add a vocabulary README, a DCAT catalogue record, a `public/README.md` and `DATA_SOURCES.md` link, and a `public/CHANGELOG.md` entry.
- Add tests covering hierarchy integrity, JSON/CSV/Turtle agreement, the 188 terms, the resolver links, and the existing SPC schema enum.

Explicitly out of scope:

- **Definitions / explanatory notes.** The JSON and Turtle carry labels and hierarchy only. The UNSD explanatory notes are not reproduced in this change.
- **Linking records to terms.** SPC items keep their bare codes; no JSON-LD context, `@id` or `dct:subject` change.
- **Classifying other datasets.** COFOG is not applied to public bodies, motions, FOI disclosures or public body actions here.
- **The 2028 revision.** Only COFOG 1999 is published; a future revision gets a new namespace and a new vocabulary.
- **Moving the source.** The pinned reference stays in `pipelines/spc_pipeline/reference/` for now.

## Capabilities

### New Capabilities

- `cofog-vocabulary`: the published COFOG 1999 vocabulary — source pinning and provenance, the division/group/class hierarchy and service type, the JSON/CSV/Turtle distributions, the `/ns/cofog` URI space and resolver, catalogue metadata and documentation, and the single-writer generation contract.

### Modified Capabilities

None. `spc-meetings-dataset` already requires COFOG codes to be published under `public/vocabularies/`; this change adds formats and a resolver but does not change that requirement, the SPC schema, or any published SPC record.

## Impact

- New code: `scripts/build_cofog_vocabulary.py`, `tests/test_cofog_vocabulary.py`.
- New outputs: `public/vocabularies/cofog-1999.json`, `.ttl`, `.csv`, `.csv-metadata.json`; `public/ns/cofog/index.html`; `public/vocabularies/cofog-1999.md`; `public/catalog/dataset-cofog-1999.ttl`.
- Changed: `pipelines/spc_pipeline/scripts/build_vocabularies.py` (drop COFOG rows), `public/README.md`, `DATA_SOURCES.md`, `public/CHANGELOG.md`, and the SPC README's vocabulary line.
- Unchanged: SPC pipeline outputs, `public/schemas/spc-meetings.schema.json`, and every published SPC record.
- No network, LLM, Apify or database use. Publishing happens only when the generated `public/` diff is reviewed and merged.
- Dependencies: none new; `rdflib` is already available for the Turtle test.
