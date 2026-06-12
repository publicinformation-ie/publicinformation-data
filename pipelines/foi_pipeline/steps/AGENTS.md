# Steps Directory — Agent Instructions

For the top-level pipeline overview, see the parent [AGENTS.md](../AGENTS.md).

## Quick Start: Running Steps

**To run all steps via the process script:**
```bash
cd ..
python process.py --force
```

**To run from a specific step:**
```bash
cd ..
python process.py --from <step_name> --force
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

**When you change what a step does** (its inputs, outputs, key behaviour, or notable files), update that step's `README.md` to reflect the change.

**When you add or remove a merger in `export_status/process.py`**, update the `export_status/README.md` table and the parent `AGENTS.md` merger table accordingly.

## Checklist for adding a new step

- [ ] Create `steps/<new_step>/` directory with `__init__.py` and `process.py`
- [ ] Add the step name to `../pipeline.json` in the correct position
- [ ] Write `steps/<new_step>/README.md`
- [ ] Update the sequence table in `steps/README.md`
- [ ] If the step contributes to the export status, add a merger to `export_status/process.py` and update `export_status/README.md`
