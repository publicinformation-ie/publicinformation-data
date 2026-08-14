# Steps Directory — Agent Instructions

For the top-level pipeline overview, see the parent [AGENTS.md](../AGENTS.md).

## Data-handling principle

When a step transforms or canonicalizes record data: **if a value cannot be reasonably and deterministically reconstructed, write an error to the step's `errors.json` and let a human reviewer handle it.** Do not reconstruct with fragile heuristics, and never silently null or rewrite a field to make it fit — a false positive or a silent loss of information is worse than an explicit, reviewable error. See the [Core Data-Handling Principle](../../../AGENTS.md#core-data-handling-principle) in the top-level AGENTS.md.

## Quick Start: Running Steps

**To run all steps via the process script:**
```bash
cd ..
uv run python process.py --force --stop-on-error
```

**To run from a specific step:**
```bash
cd ..
uv run python process.py --from <step_name> --force --stop-on-error
```

**To run a single step directly:**
```bash
PYTHONPATH=.. python <step_name>/process.py \
  --input ../<previous_step>/output.json \
  --output <step_name>/output.json \
  --force
```

> **Note:** Use the process script for normal operation. Direct step execution is for testing/debugging only.

## Keeping documentation in sync

**When you add, remove, or rename a pipeline step, you must update the following files:**

1. **`../pipeline.json`** — the authoritative step order. Add, remove, or reorder the step name in the `"steps"` array.
2. **`README.md`** (this directory) — update the step sequence table to match `pipeline.json` exactly. Each row should have the correct step number, a link to the step subdirectory, and a one-sentence description.
3. **`<step>/README.md`** — create a README in the new step's directory following the same format as the existing step READMEs (what it does, input, output, notable files).
4. **Run `uv run python scripts/generate_pipeline_docs.py` from the repository root** to refresh generated pipeline summaries in the top-level `AGENTS.md`.

**When you change what a step does** (its inputs, outputs, key behaviour, or notable files), update that step's `README.md` to reflect the change.

**When you add or remove a merger in `export_status/process.py`**, update the `export_status/README.md` table and the parent `AGENTS.md` merger table accordingly.

## Checklist for adding a new step

- [ ] Create `steps/<new_step>/` directory with `__init__.py` and `process.py`
- [ ] Add the step name to `../pipeline.json` in the correct position
- [ ] Write `steps/<new_step>/README.md`
- [ ] Update the sequence table in `steps/README.md`
- [ ] If the step contributes to the export status, add a merger to `export_status/process.py` and update `export_status/README.md`
