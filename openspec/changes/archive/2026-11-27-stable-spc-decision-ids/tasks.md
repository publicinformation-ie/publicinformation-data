# Tasks

## 1. Registry and ID assignment

- [x] 1.1 Define `extract_spc_items/decision_ids.json` and its JSON Schema; add a loader that rejects duplicate numbers within a meeting, a malformed `id`, an unknown status and a retired entry without a reason.
- [x] 1.2 Add `assign_decision_ids` in `extraction.py`: exact match reuses the ID; token-sequence overlap with an unmatched active entry raises `DecisionIdAmbiguous`; otherwise allocate `max(all numbers incl. retired) + 1`; an unmatched active entry raises `RegisteredDecisionMissing`; a retired match is suppressed and counted.
- [x] 1.3 Make the step append entries for brand-new decisions only, never editing or removing an existing entry, and write nothing when there is nothing new.
- [x] 1.4 Replace the positional `decision_id` numbering and remove `drop_decisions` and its stale-target check; document the new error types in the step README.

## 2. Tests

- [x] 2.1 Tests for each scenario in the spec delta: first-run ordinal numbering, ID kept when an earlier decision is added or dropped, next-number allocation, retired number never reused, boundary drift error, missing registered decision.
- [x] 2.2 A test that every decision in `public/latest/spc-meetings/decisions.jsonld` is active in the registry with the same normalised quote and meeting.

## 3. Seed and verify

- [x] 3.1 Seed the registry from the current `output.json` (17 decisions) and add 2025-11-20 `d01` as retired with its reason; remove `drop_decisions` from `override.json`.
- [x] 3.2 Run `uv run python pipelines/spc_pipeline/process.py pipelines/spc_pipeline --force --stop-on-error --from extract_spc_items` (cache hits only; no paid call) and confirm `scripts/transform_spc_meetings.py` reports no content change and `git diff public` is empty.
- [x] 3.3 Add the ID-stability statement to the generated dataset README and the Documentation entry in `public/CHANGELOG.md`; regenerate; run the SPC, root, `pyright` and docs checks.

## 4. Follow-on review gate (no code until reviewed)

- [x] 4.1 With the registry in place, apply `.scratch/spc-prompt-v2.patch` locally against the cached v2 responses and list every error and content difference against the live data.
- [x] 4.2 Present the list to the user for a decision: adopt v2, adopt v2 with registry edits, or stay on v1. Record the outcome in the follow-ups doc §7. (Outcome: adopted v4 after trials v2, v3, v4.)
