## Why

`actions_pipeline` now extracts plan actions, status observations, and relationships from strategy documents, and the `public-body-actions` dataset (v1.0.0) is already published under `public/`. But it is effectively invisible: it is absent from `get-the-data.html`, linked on `index.html` only as a nested sub-item of "Strategies and Plans", and the sibling repo `publicinformation-web` does not consume it at all. For the data to count as open data, it must be discoverable on data.publicinformation.ie and actually reused on publicinformation.ie.

## What Changes

- **Data repo — discoverability**:
  - List public-body-actions on `public/get-the-data.html` with download links and plain-English descriptions for all three CSV tables (actions, action-status-observations, action-relationships).
  - Promote the Public Body Actions README link on `public/index.html` into the main `#reference` list (removing the nested duplicate under "Strategies and Plans").
  - Add a guard test that every catalogued dataset with a `latest/` distribution is listed on both pages.
- **Web repo (`publicinformation-web`) — reuse**:
  - Fetch `latest/public-body-actions/public-body-actions.jsonld` at build time and register a `DatasetManifest` for it.
  - Render per-body actions pages (`/bodies/<slug>/public-body-actions/`) showing each action's text, plan, original deadline, and most recent reported status; the generic `/data/public-body-actions/` catalogue page and `/api/data/public-body-actions.json|.csv` mirrors come from the existing registry.
- No changes to the published dataset contract: v1.0.0 schema, payloads, vocabularies, and TTL stay as-is; no `owl:versionInfo` bump.

## Capabilities

### New Capabilities

- `open-data-discovery`: every dataset published to data.publicinformation.ie is discoverable from the site's landing and "Get the Data" pages.
- `actions-dataset-reuse`: publicinformation.ie (the web site, built from the sibling repo) consumes the public-body-actions dataset and surfaces per-body actions with their reported status.

### Modified Capabilities

(none — no specs exist yet)

## Impact

- **Data repo**: `public/get-the-data.html`, `public/index.html`, new guard test under `tests/`. No pipeline/transform changes, no dataset version bump.
- **Web repo** (`../publicinformation-web`): new fetcher + `DatasetManifest` module, registry entry, record-type-aware rendering on the per-body dataset page, tests. Build-time dependency on `https://data.publicinformation.ie/latest/public-body-actions/public-body-actions.jsonld` (honouring the existing `DATA_BASE_URL` override for offline dev).
- **No new dependencies, no database changes.** The dataset payloads are already committed and live, so the web consumer can land independently once the data repo pages are updated.
