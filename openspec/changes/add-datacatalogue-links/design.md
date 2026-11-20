# Design

## Context

Three link pipelines already share one shape: `wdw_pipeline`, `datagovie_pipeline` and `lobbying_pipeline` each run fetch/parse → `match_public_bodies` → `apply_overrides`, and a `scripts/transform_*_links.py` publishes the result. `datagovie_pipeline` is the closest template. It reads a CKAN `organization_list` endpoint, fuzzy-matches with `src/lib/body_matching.py` against `cso_pipeline/steps/resolve_website_urls/output.json`, applies a slug-keyed `override.json`, drops unmatched records, and publishes through `src/lib/dataset_publish.py` (`render_jsonld`, `render_csv`, `stamp_if_changed`) using `src/lib/body_refs.py` for body URIs.

The source's structure has not been verified. The `/organization/` path suggests CKAN, but this session's network blocks `datacatalogue.gov.ie`, so the page and any `/api/3/action/...` endpoint have not been inspected.

## Goals / Non-Goals

**Goals:**
- Mirror `datagovie_pipeline` closely enough that a reviewer can diff the two and see only source-specific changes.
- Reuse the shared matching, slug and publishing helpers unchanged.

**Non-Goals:**
- No shared base class or factory for the link pipelines. Folding the four copies into one is a separate refactor.
- No scheduling or CI job to refresh the dataset. It is run by hand, like the other link pipelines.

## Decisions

### D1. Fetch source: CKAN API if present, HTML listing otherwise

The first implementation task is a short source check: does `https://datacatalogue.gov.ie/api/3/action/organization_list?all_fields=true` respond?

- **If CKAN responds:** use the API, like `fetch_datagovie_orgs`, keeping the `type == "organization"` and `state == "active"` filter and using `display_name` rather than `title`. Check whether the instance pages `organization_list` (newer CKAN caps `all_fields` results, often at 25 or 1000). If it does, page with `limit`/`offset` until a short page comes back.
- **If CKAN does not respond:** parse the paginated HTML listing (`/organization/?page=N`) with BeautifulSoup, already a dependency through `parse_wdw_bodies`, until a page yields no organisations. Take slugs from the `/organization/<slug>` hrefs.

*Alternative considered:* always scrape HTML. Rejected because the API is more stable, carries state and package counts, and matches the existing template. Either path meets the same spec, so the choice is an implementation detail.

### D2. Naming

| Thing | Name |
|---|---|
| Pipeline dir | `pipelines/datacatalogue_pipeline/` |
| Steps | `fetch_datacatalogue_orgs`, `match_public_bodies`, `apply_overrides` |
| Record fields | `datacatalogue_slug`, `datacatalogue_name`, `datacatalogue_url`, `datacatalogue_package_count` (optional), `datacatalogue_description` (optional) |
| Dataset id / dir | `datacatalogue-gov-ie-links` |
| JSON-LD type / ns | `dcl:DataCatalogueLink`, `dcl` → `https://data.publicinformation.ie/ns/dcl#` |
| Transform | `scripts/transform_datacatalogue_links.py` |

The dataset id follows `data-gov-ie-links` (host name plus `-links`), so the two catalogues sit side by side and can be told apart in listings.

### D3. Matching and overrides are copied, not shared

The step processes start as copies of the `datagovie_pipeline` steps, with field names swapped. `IncrementalWriter` stays keyed on the slug so interrupted runs can resume. `apply_overrides` keeps the datagovie semantics: an explicit null suppresses a match, and unresolved records are dropped and counted, not fatal. This differs from WDW's fatal-on-gap behaviour because many catalogue organisations will not be canonical public bodies.

*Alternative considered:* parametrise the datagovie steps to serve both catalogues. Rejected for now because it couples two datasets' release cycles and widens the change.

### D4. Seeding overrides from data-gov-ie-links

Where an organisation's datacatalogue.gov.ie slug equals its data.gov.ie slug, the existing `datagovie_pipeline` override is a useful hint. It is not copied automatically. A reviewer checks the unmatched list in `match_log.json` and adds overrides by hand, each marked in the commit message, following the override-system rules in `AGENTS.md`.

### D5. No paid steps, no status.py

`pipeline.json` lists no `paid_steps`. `scripts/pipeline_status.py` covers the pipeline automatically, so no per-item `status.py` is added, matching the other link pipelines.

## Risks / Trade-offs

- [The source is not CKAN, or its HTML changes] → The fetch fails closed on zero organisations, and the parser tests use a committed HTML fixture so a markup change shows up as a test failure, not as silently thin output.
- [Fuzzy false positives, e.g. "Department of X" against a renamed department] → The shared threshold is kept, and `match_log.json` is reviewed before the first publish. Suppressions go into `override.json` as explicit nulls.
- [The two catalogues overlap heavily and look redundant] → They are published as separate datasets on purpose, per the user's direction. The dataset README states how the two catalogues differ once the source has been checked.
- [Network blocked in cloud sessions] → `datacatalogue.gov.ie` has to be added to the environment's allowed hosts before task 1. Tests use fixtures and need no network.

## Migration Plan

This is an additive change. Publishing happens when the `public/` diff is merged to `main` after review. To roll back, revert the commit. No existing dataset changes.

## Open Questions

- What exactly datacatalogue.gov.ie catalogues (open datasets, or the Data Sharing and Governance Act data-asset inventory) only affects the wording of the dataset README and the `.ttl` description. Task 1 answers it.
