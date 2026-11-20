# Tasks

## 1. Source check

- [x] 1.1 Get `datacatalogue.gov.ie` allowed in the session's network settings. Verify that `curl -sI https://datacatalogue.gov.ie/organization/` returns 200.
- [x] 1.2 Probe `https://datacatalogue.gov.ie/api/3/action/organization_list?all_fields=true` and record the fetch path chosen under design D1 (CKAN or HTML), the total organisation count, the pagination behaviour and the fields available. Verify by writing those findings into the step README drafted in 2.2.
- [x] 1.3 Save a small, trimmed fixture of the real response (JSON or listing HTML, 3 to 5 organisations, including one non-active entry if the source has any) under `pipelines/datacatalogue_pipeline/tests/fixtures/`. Verify that the fixture loads in a Python shell.

## 2. Fetch step

- [x] 2.1 Scaffold `pipelines/datacatalogue_pipeline/` (`pipeline.json` with the three steps and no `paid_steps`, a `process.py` copied from `datagovie_pipeline`, `tests/conftest.py`). Verify that `uv run python pipelines/datacatalogue_pipeline/process.py pipelines/datacatalogue_pipeline --help` runs.
- [x] 2.2 Implement `steps/fetch_datacatalogue_orgs/process.py` and its `README.md`: full pagination, active-only filtering, the record fields from design D2, and fail-closed exits on request, HTTP, parse and zero-result errors. Verify with `tests/test_fetch_datacatalogue_orgs.py` against the fixture: pagination is followed, duplicate slugs are rejected, inactive entries are dropped, the URL format is correct, and each failure path exits non-zero without writing output.

## 3. Matching and overrides

- [x] 3.1 Implement `steps/match_public_bodies/process.py` and its `README.md` (copied from datagovie, keyed on `datacatalogue_slug`, writing `match_log.json`). Verify that `tests/test_match_public_bodies.py` covers a match above the threshold, a match below it, and resuming via `IncrementalWriter`.
- [x] 3.2 Implement `steps/apply_overrides/process.py`, its `README.md` and an empty `override.json` (`{}`). Verify that `tests/test_apply_overrides.py` covers a non-null override, an explicit-null suppression, unmatched records being dropped, and the matched/override/dropped summary line.
- [x] 3.3 Run the pipeline live through `apply_overrides`: `uv run python pipelines/datacatalogue_pipeline/process.py pipelines/datacatalogue_pipeline --force --stop-on-error`. Review `match_log.json`, then add reviewed overrides (corrections and null suppressions) to `override.json`, checking each candidate against the `data-gov-ie-links` overrides per design D4. Verify that a re-run prints the expected matched/dropped counts and that `uv run pytest pipelines/datacatalogue_pipeline/tests -q` passes.

## 4. Published dataset

- [x] 4.1 Write `public/schemas/datacatalogue-gov-ie-links.schema.json` and `public/catalog/dataset-datacatalogue-gov-ie-links.ttl` (v1.0.0, relation to `public-bodies`, both distributions), modelled on the `data-gov-ie-links` files. Verify that the `.ttl` parses (`uv run python -c "import rdflib; rdflib.Graph().parse('public/catalog/dataset-datacatalogue-gov-ie-links.ttl')"`, or the repo's existing catalog test).
- [x] 4.2 Implement `scripts/transform_datacatalogue_links.py` (JSON-LD and CSV, CSVW metadata, fail on an unknown `public_body_id`, `stamp_if_changed`, copy to `latest/`). Verify with `tests/test_transform_datacatalogue_links.py`, which covers record building, the unknown-id error, CSV rows, and `dct:modified` staying put on unchanged content.
- [x] 4.3 Run the transform and add `tests/test_datacatalogue_gov_ie_links_schema.py`. Verify that `uv run pytest tests/test_datacatalogue_gov_ie_links_schema.py -q` passes against the generated JSON-LD.
- [x] 4.4 Write `public/v1.0.0/datacatalogue-gov-ie-links/README.md` (data model, provenance, how this catalogue differs from data.gov.ie, matching caveats) and copy it to `latest/`. Verify by checking that the README's field list matches the CSV header.

## 5. Discovery and documentation

- [ ] 5.1 Add the dataset to the `README.md` dataset table (with its count) and pipeline table, to the repository-structure tree, and to the `tests/test_readme_dataset_counts.py` mapping. Verify that `uv run pytest tests/test_readme_dataset_counts.py -q` passes.
- [ ] 5.2 Add the dataset to `public/get-the-data.html` (a download block and the reference-pages sentence), and add a `DATA_SOURCES.md` attribution with the source's licence as stated on the site. Verify that the links resolve to existing files under `public/latest/`.
- [ ] 5.3 Add a `public/CHANGELOG.md` entry for datacatalogue-gov-ie-links v1.0.0, and add the pipeline to the `AGENTS.md` repository-structure list. Run `uv run python scripts/generate_pipeline_docs.py`. Verify that `git diff AGENTS.md` shows the new step-sequence table and that the generated-docs consistency check passes.

## 6. Integration check

- [ ] 6.1 Run `uv run pytest tests -q`, `uv run pytest pipelines/datacatalogue_pipeline/tests -q`, `uv run pyright` and `uv run python scripts/pipeline_status.py --pipeline datacatalogue_pipeline`. Verify that everything passes and that the status tool reports the pipeline with no paid steps.
- [ ] 6.2 Review the `public/` diff (record count, a sample of links opened in a browser, no unexpected changes to other datasets). Verify that the record count matches the `apply_overrides` summary line.

## Workflow follow-up

- Merge to `main` only after the `public/` diff has been reviewed. Merging is what publishes.
- Archive the change with `/opsx:archive` once it is merged.
