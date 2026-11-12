# Proposal

## Why

`original_deadline_milestones` publishes a plan's interim milestones as one flat string. For SMP 2026–2030 action 4 that is `Q1 2029 – Convene working group… Q3 2030 – Secure Ministerial sign-off…`: complete and correct, but a consumer cannot ask "which milestones fall due in 2029?" without parsing prose themselves. 150 of the 206 published actions carry milestone text, and 50+ of those hold several milestones.

## What Changes

- New deterministic pipeline step `extract_milestones` (`actions_pipeline`) splits each action's `original_deadline_milestones` into one record per milestone, with a parsed due date where the plan states one. No model call; no upstream file is rewritten.
- New published table `action-milestones.csv` (also in the JSON-LD, CSVW, JSON Schema and DCAT catalogue) keyed to `actions.csv` by `action_id`.
- `actions.csv` and its `original_deadline_milestones` column are unchanged. The three existing tables are byte-identical in content.
- Scope: SMP 2026–2030 and SMP 2022–2025. Climate Action Plan date-only lists (5 rows) emit dated rows with empty text.
- Additive minor release after 3.1.0 (folded into 3.1.0 if that release is still unpublished when this lands).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `public-body-actions-dataset`: adds requirements for the milestone table — one record per milestone, dates only where the plan states them, lossless relationship to the raw prose, and referential integrity with actions.

## Impact

- Code: `pipelines/actions_pipeline` (new `milestones.py`, new step, `pipeline.json`), `scripts/transform_public_body_actions.py`.
- Published: new `action-milestones.csv`; updated CSVW, `public/schemas/public-body-actions.schema.json`, `public/catalog/dataset-public-body-actions.ttl`, JSON-LD, dataset README, `public/CHANGELOG.md`, `AGENTS.md`.
- Tests: new `test_milestones.py`, `test_extract_milestones.py`; extended transform and schema tests.
- Precondition: the climate status-observations work (v3.1.0, currently uncommitted) is merged first.
- Detailed task plan: `docs/superpowers/plans/2026-11-11-action-milestones.md`.
