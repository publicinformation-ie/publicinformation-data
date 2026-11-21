# Proposal

## Why

datacatalogue.gov.ie lists Irish public-sector organisations at `https://datacatalogue.gov.ie/organization/`, and each organisation has its own page. This is a separate catalogue from data.gov.ie: the existing `data-gov-ie-links` dataset covers data.gov.ie and does not cover it. Linking each canonical public body to its datacatalogue.gov.ie organisation page gives users one more reference from a public body to the data it holds. The pipeline shape is already proven by `wdw_pipeline` and `datagovie_pipeline`.

## What Changes

- New pipeline `pipelines/datacatalogue_pipeline/` with three steps, following the "Who Does What" and data.gov.ie pattern:
  1. `fetch_datacatalogue_orgs`: fetch the full organisation list from datacatalogue.gov.ie, with each organisation's slug, display name, page URL and, where the source exposes them, its dataset count and description.
  2. `match_public_bodies`: fuzzy-match each organisation name against the canonical public-body list with the shared `src/lib/body_matching.py`, at the same threshold as the other link pipelines.
  3. `apply_overrides`: apply manual `public_body_id` corrections keyed by organisation slug from a committed `override.json`, then drop organisations that are still unmatched. Most catalogue organisations may not be canonical public bodies, so partial resolution is expected.
- New published dataset `datacatalogue-gov-ie-links` (v1.0.0), in JSON-LD and CSV under `public/v1.0.0/` and `public/latest/`. Each record links one public body to one datacatalogue.gov.ie organisation page.
- New `scripts/transform_datacatalogue_links.py`, plus a DCAT-AP catalogue entry, a JSON Schema, CSVW metadata, a dataset README, a `public/CHANGELOG.md` entry, a `DATA_SOURCES.md` attribution, and discovery links in `README.md` and `public/get-the-data.html`.
- Regenerated pipeline documentation (`AGENTS.md` step sequences) and a `README.md` entry for the new pipeline.

Out of scope:

- **Changing `data-gov-ie-links` or `datagovie_pipeline`.** The two catalogues stay separate datasets. Cross-linking or merging them is a later decision.
- **Dataset-level records.** Only the organisation link is published, not the datasets or data assets each organisation lists.
- **Adding datacatalogue links to the `public-bodies` dataset.** The new dataset references public bodies by URI. `public-bodies` itself does not change.
- **Paid steps.** No LLM or Apify calls. Matching is deterministic fuzzy matching plus manual overrides.

## Capabilities

### New Capabilities

- `datacatalogue-links-dataset`: how datacatalogue.gov.ie organisations become a published link dataset. It covers the complete fetch with fail-closed guards, deterministic name matching, the override rules, dropping unmatched organisations, record identity, JSON-LD and CSV serialisations, catalogue metadata and schema, and content-only `dct:modified` stamping.

### Modified Capabilities

None. No existing spec covers the link datasets (`who-does-what`, `data-gov-ie-links`, `lobbying-ie-links`), and this change does not alter `source-file-references` or `public-body-actions-dataset`.

## Impact

- New code: `pipelines/datacatalogue_pipeline/` (`pipeline.json`, `process.py`, `steps/*/process.py` and `README.md`, `steps/apply_overrides/override.json`, `tests/`) and `scripts/transform_datacatalogue_links.py`. It reuses `src/lib/body_matching.py`, `src/lib/body_refs.py`, `src/lib/dataset_publish.py` and `src/lib/http_utils.py` without changing them.
- New tests: pipeline step tests under `pipelines/datacatalogue_pipeline/tests/`, and root tests `tests/test_transform_datacatalogue_links.py` and `tests/test_datacatalogue_gov_ie_links_schema.py`. The `tests/test_readme_dataset_counts.py` mapping gets a new entry.
- Public files: `public/catalog/dataset-datacatalogue-gov-ie-links.ttl`, `public/schemas/datacatalogue-gov-ie-links.schema.json`, `public/v1.0.0/datacatalogue-gov-ie-links/` and `public/latest/datacatalogue-gov-ie-links/`, `public/get-the-data.html`, `public/CHANGELOG.md`.
- Environment: the fetch step needs network access to `datacatalogue.gov.ie`. The current cloud environment blocks that host, so it must be allowed before the first live run.
- Upstream dependency: `match_public_bodies` reads `pipelines/cso_pipeline/steps/resolve_website_urls/output.json`, the same input `datagovie_pipeline` reads.
