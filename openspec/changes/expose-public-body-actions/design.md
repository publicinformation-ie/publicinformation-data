## Context

The `public-body-actions` dataset (v1.0.0) is already fully published: transform script (`scripts/transform_public_body_actions.py`), payloads (`public/v1.0.0/public-body-actions/` + `public/latest/public-body-actions/`: three CSVs, CSVW metadata, JSON-LD, README), catalogue TTL, JSON Schema, vocabularies, and tests. What is missing is purely exposure — see proposal.md for motivation.

Constraints shaping the approach:

- The web repo (publicinformation-web) has two established consumption patterns: (A) build-time JSON-LD fetch via `src/lib/dataSource.ts` + `DatasetManifest` registration (used by who-does-what, data-gov-ie-links), and (B) CSV seed into `data.db` (used by FOI datasets).
- The actions dataset is small: 198 actions, 279 status observations, 50 relationships.
- The web repo's generic dataset pages (`/data/[dataset]/`, `/bodies/[slug]/[dataset]/`, `/api/data/...`) iterate the manifest registry, but the per-body page currently renders every record set through `FoiDisclosureList` with FOI quarterly stats.
- The JSON-LD graph already carries `public_body_id` on every action node, so body joins need no slug resolution.
- `get-the-data.html` is hand-authored plain-English prose that currently says "Five downloadable spreadsheet files"; `index.html` nests the actions README under "Strategies and Plans" instead of the `#reference` list.

## Goals / Non-Goals

**Goals:**

- public-body-actions discoverable from both entry pages on data.publicinformation.ie, guarded against regression.
- publicinformation-web consumes the dataset through the cheapest established pattern and renders per-body actions with their latest reported status.
- Zero changes to the published dataset contract (no version bump, no payload regeneration).

**Non-Goals:**

- No changes to `actions_pipeline`, the transform script, schemas, or vocabularies.
- No rendering of action *relationships* in the web UI (they remain available via the API mirrors; UI is future work).
- No DB-backed seeding of actions, no new libSQL tables, no edge-function changes.
- No changes to the `documents` library publishing.

## Decisions

### D1: Web consumption uses Pattern A (build-time JSON-LD manifest), not DB seeding

The dataset is small and relational joining is trivial in memory (observations → actions by `action_id`, relationships → actions by `from_action_id`, actions → bodies by `public_body_id`). Pattern A is proven by two existing datasets, gives the `/data/` catalogue page, per-body pages, and API mirrors from the generic registry, and needs no schema.sql/load.ts/validate.ts changes.

**Alternative considered:** Pattern B (CSV seed into `data.db`) — rejected: three new tables plus mapping/validation/load code for ~500 records; only justified if actions grow to a scale needing SQL queries. Re-evaluate if the corpus grows an order of magnitude.

### D2: Fetch the single JSON-LD file, not the three CSVs

`public-body-actions.jsonld` contains all three tables as typed `@graph` nodes (`act:Action`, `act:ActionStatusObservation`, `act:ActionRelationship`) in one fetch, matching the who-does-what/data-gov-ie-links precedent. Fetching and joining three CSVs would duplicate the transform's assembly logic on the consumer side.

### D3: Per-body pages become record-type-aware by dispatching on dataset id

`bodies/[slug]/[dataset]/index.astro` (and its `[page].astro` pagination twin) currently hard-code `FoiDisclosureList` and FOI quarterly stats. The change adds a dispatch on `datasetId`: `foi` keeps today's rendering byte-identical; `public-body-actions` renders a new action-list component showing action text, plan title, original deadline, and the latest observation status (most recent `as_of` wins). The generic page shell (header, download links, pagination) is reused unchanged.

**Alternative considered:** a fully generic record renderer — rejected as over-engineering for two record types.

### D4: Manifest shape

`DatasetManifest` with `id: 'public-body-actions'`, `perBody: true`, `rss: false`, `siteWideSlices: []`. `bodyRecords(bodyId)` returns that body's actions with observations folded in (latest status precomputed). Freshness comes from `dataSource.ts`'s existing last-modified capture.

### D5: Guard test derives the dataset set from `public/latest/` subdirectories

Listing `public/latest/*/` is simpler and more authoritative than parsing catalogue TTLs, and naturally excludes `documents` (which has a catalogue TTL but no `latest/` distribution). The test asserts each dataset's CSV(s) are linked from `get-the-data.html` and its README from the `index.html#reference` list.

### D6: get-the-data.html gains one section for a three-table dataset

The page's contract is plain-English, spreadsheet-ready downloads. The new section links all three CSVs with a one-line description each, and the intro prose is updated from "Five downloadable spreadsheet files" to reflect the actual count. Prose stays hand-authored; only links are machine-guarded (D5).

### D7: index.html reference list is the single home for dataset README links

The actions README link moves from the nested "Strategies and Plans" sublist into `#reference`; the nested duplicate is removed to avoid two links to the same README.

## Risks / Trade-offs

- [Per-body page changes could regress FOI rendering] → dispatch keeps the FOI branch untouched; existing web tests plus a build diff of `/bodies/<slug>/foi/` output verify no change.
- [Web build gains a hard dependency on the actions dataset URL] → fail-closed with an explicit error (consistent with existing build-time datasets); `DATA_BASE_URL` file mode keeps CI/offline builds working against the local data repo.
- [JSON-LD shape drift breaks the consumer] → the web parser validates required fields (`@type`, `action_id`, `public_body_id`) and fails the build; the data repo's schema tests already pin the shape.
- [Hand-authored prose counts ("Five files") drift again] → the guard test checks links, not prose; the count is fixed in this change and future datasets get caught by the link check.

## Migration Plan

Purely additive. Data-repo page edits and the guard test land first (or independently); the web consumer can land any time after, since the `latest/` payloads are already published. Rollback = revert; no data migration, no cache invalidation concerns.

## Open Questions

- Should the actions dataset appear in `quickstart.html`'s worked example eventually? Deferrable; the quickstart is a single narrative example, not a listing, and the guard test deliberately does not cover it.
