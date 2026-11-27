# Proposal

## Why

SPC decision IDs are ordinal within a meeting (`<meeting_id>/d<NN>`), so any re-extraction that adds, drops or reorders a decision silently points a published URI at a different decision. The step 5 re-extraction under prompt `spc-items-v2` showed this: removing the `d01` drop override renumbered the published 2025-11-20 decisions, and re-extraction also changed quote boundaries. The prompt fixes for P1.2 and prompt injection cannot be adopted until published decision identity no longer depends on extraction order.

## What Changes

- Add a committed, append-only decision ID registry. Each published decision is registered once, by meeting, agenda item and normalised quote, and keeps its `d<NN>` for good.
- Assign IDs from the registry. A decision whose item and quote match a registered entry reuses its ID. A decision with no registry match and no overlap with an unmatched registered entry gets the next unused number for that meeting.
- Fail closed on drift. A new quote that overlaps an unmatched registered quote in the same item, or a registered decision that is no longer extracted, is logged as an error and is not published or renumbered until a human maps or retires it.
- Retire instead of delete. A retired ID is kept in the registry with a reason, is never published and is never reused. The `d01` entry for 2025-11-20 becomes a retired entry, replacing the positional `drop_decisions` override.
- Seed the registry from the 17 decisions now published, so no live URI changes.
- Document ID stability in the dataset README and `public/CHANGELOG.md`.
- No schema, field, CSV or JSON-LD shape change, and no `owl:versionInfo` bump: no published ID changes.

## Capabilities

### New Capabilities

### Modified Capabilities
- `spc-decisions`: the requirement "Decision identity is stable" now defines how IDs are allocated and kept, in place of "numbered in order of appearance".

## Impact

- `pipelines/spc_pipeline/steps/extract_spc_items/`: ID assignment in `extraction.py`, the new `decision_ids.json`, replacement of `drop_decisions`, tests and README.
- `pipelines/spc_pipeline/steps/export_spc_meetings` and `scripts/transform_spc_meetings.py`: read decision IDs as before; the dataset README gains an ID-stability statement.
- Unblocks adopting prompt `spc-items-v2` (parked in `.scratch/spc-prompt-v2.patch`), and the removal of the `d01` override.
- Follow-up reference: `openspec/changes/archive/2026-11-26-add-spc-minutes-pipeline/followups-2026-11-26.md` §7.
