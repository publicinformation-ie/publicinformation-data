# Tasks

## 1. Milestone splitter

- [x] 1.1 Create `pipelines/actions_pipeline/milestones.py` (`Milestone`, `split_milestones`, `MilestoneRoundTripFailed`) with `tests/test_milestones.py` covering action 4, `YYYY:`, `IMMAC 2025-2030`, mid-sentence marker (action 15), prose date, lead-in text, undated, `interim target`, bare-year-dash (actions 54, 71, 91), CAP date-only lists, `Q 4 2024` canonicalisation, empty/nbsp input, ordinals, partition and determinism; verify with `pytest pipelines/actions_pipeline/tests/test_milestones.py -v`

## 2. `extract_milestones` step

- [x] 2.1 Create `steps/extract_milestones/process.py` (`build_milestones`, `main`) with `tests/test_extract_milestones.py` (ids, empty cells, round-trip fallback logged, input order, referential integrity); verify with `pytest pipelines/actions_pipeline/tests/test_extract_milestones.py -v`
- [x] 2.2 Register the step in `pipelines/actions_pipeline/pipeline.json` with `input_steps` pointing at `resolve_action_identity`; add the step README and update `pipelines/actions_pipeline/README.md`; verify by running `--from extract_milestones --to extract_milestones` and getting `output.json`

## 3. Blast-radius audit

- [x] 3.1 Run over all 206 rows; verify zero `MilestoneRoundTripFailed`, exact per-plan record counts, and actions 4→2, 1→4, 15→3, 74→3, 3→1 undated, 54→1 dated, 75→0; record counts and suspect splits in `docs/analysis/2026-11-11-action-milestones-audit.md`
- [x] 3.2 Fix any defect with a failing regression test first; verify tasks 1.1 and 2.1 tests still pass

## 4. Publish the table

- [ ] 4.1 Extend `scripts/transform_public_body_actions.py` (`MILESTONE_FIELDS`, `build_milestone_rows`, invariants, CSV, JSON-LD `milestones`, keyword-only `milestones=None`) with tests in `tests/test_transform_public_body_actions.py` and the end-to-end test; verify with `pytest tests/test_transform_public_body_actions.py tests/test_public_body_actions_end_to_end.py -v`
- [ ] 4.2 Add the CSVW table and foreign key, JSON Schema `ActionMilestone`, DCAT distribution and version, and dataset README columns for the new release; update `tests/test_public_body_actions_schema.py` (tablegroup covers four tables; rename the version test to the new version); verify with `pytest tests/test_public_body_actions_schema.py -v`
- [ ] 4.3 Run the transform; verify with `diff -r` against the previous release that only the new CSV, CSVW, README and JSON-LD differ

## 5. Documentation and integration

- [ ] 5.1 Update `public/CHANGELOG.md` (additive minor; `original_deadline_milestones` unchanged) and the `AGENTS.md` pipeline table; verify the documented step name and table match the code
- [ ] 5.2 Run `pytest pipelines/actions_pipeline/tests tests -q` and the repo's pyright invocation; verify all pass and `git status` shows only files named in this change

## Workflow follow-up

- Merge the climate status-observations work before starting; branch from the resulting `main`.
- Archive the change after review and verify the archived result.
