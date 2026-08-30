## 1. Data repo — discoverability on data.publicinformation.ie

- [x] 1.1 Add a public-body-actions section to `public/get-the-data.html`: download links for `actions.csv`, `action-status-observations.csv`, `action-relationships.csv` with plain-English descriptions; update the intro prose count ("Five downloadable spreadsheet files")
- [x] 1.2 Move the `latest/public-body-actions/README.md` link on `public/index.html` into the `#reference` list and remove the nested duplicate under "Strategies and Plans"
- [x] 1.3 Add a guard test in `tests/` deriving the dataset set from `public/latest/*/` and asserting every dataset's CSVs are linked from `get-the-data.html` and its README from the `index.html#reference` list
- [x] 1.4 Run `uv run pytest tests/ -q` and review the `public/` diff

## 2. Web repo (publicinformation-web) — dataset consumer

- [x] 2.1 Add `src/lib/publicBodyActions.ts`: fetch `latest/public-body-actions/public-body-actions.jsonld` via `fetchDatasetJson`, split `@graph` by `@type`, validate required fields (fail the build on missing/malformed), join observations to actions by `action_id` (latest `as_of` wins) and actions to bodies by `public_body_id`, expose freshness
- [x] 2.2 Add `src/lib/datasets/publicBodyActions.ts` manifest (`id: 'public-body-actions'`, `perBody: true`, `rss: false`) and register it in `src/lib/datasets/registry.ts`
- [x] 2.3 Make `src/pages/bodies/[slug]/[dataset]/index.astro` and `[page].astro` record-type-aware: dispatch on `datasetId`, render actions with a new action-list component (action text, plan title, original deadline, latest reported status), keep the FOI branch unchanged
- [x] 2.4 Add tests mirroring the `whoDoesWhat.test.ts` / `dataGovIeLinks.test.ts` patterns (fetch/parse, manifest behaviour, registry inclusion)
- [x] 2.5 Build against local data (`DATA_BASE_URL=../publicinformation-data/public`) and verify `/data/public-body-actions/`, `/bodies/<slug>/public-body-actions/`, and `/api/data/public-body-actions.json|.csv`; confirm `/bodies/<slug>/foi/` output is unchanged

## 3. Publish and verify

- [ ] 3.1 Review the generated `public/` diff, then let the post-commit hook (or `scripts/publish_pages.sh`) rebuild the `pages` branch
- [ ] 3.2 Spot-check the live pages: dataset listed on data.publicinformation.ie (`get-the-data.html`, `index.html`) and actions visible on publicinformation.ie body pages
