## Why

The shared pipeline runner (`src/lib/pipeline_runner.py`) can resume a run from a named step with `--from`, but cannot stop early. Testing or debugging a bounded slice of a 27-step pipeline (for example, only the extraction steps) still requires either running the tail steps unnecessarily or invoking steps individually, which bypasses dependency resolution and staleness handling.

## What Changes

- Add a `--to STEP` flag to the shared pipeline runner that stops the run after the named step completes (inclusive), mirroring `--from`.
- Support `--from` and `--to` together to run a bounded window of steps (e.g. `--from find_foi_pages --to get_foi_emails`).
- Fail fast with a clear error when `--to` (or `--from`) names a step that is not in the pipeline's `pipeline.json` step list, or when `--to` appears before `--from` in the sequence.
- Document `--to` in the runner usage docs (`AGENTS.md`, `README.md`, and the FOI pipeline docs where `--from` is currently described).
- Add runner tests covering: stop-after behaviour, `--from`+`--to` windowing, input-chain preservation at the window start, `--to` on the last step, unknown-step error, inverted-range error, and composition with `--force`, `--stop-on-error`, absolute-path upstream steps, and `always_run` steps.

## Capabilities

### New Capabilities

- `pipeline-runner`: the shared CLI runner that executes a pipeline's steps in order, resolving input/output paths, staleness, and step-range flags (`--from`, `--to`).

### Modified Capabilities

(none — no specs exist yet)

## Impact

- **Code**: `src/lib/pipeline_runner.py` only (adds argument parsing, range validation, and a stop condition in the step loop). No changes to `pipeline.json` files or individual steps.
- **Tests**: new cases in `pipelines/foi_pipeline/tests/test_pipeline_runner.py` (the existing home for runner tests). Run with `cd pipelines/foi_pipeline && uv run pytest tests/ -q`.
- **Docs**: `AGENTS.md` (Common Commands / runner flags), `README.md`, and `pipelines/foi_pipeline/AGENTS.md` gain a `--to` example.
- **No new dependencies, no database, network, or publishing side effects.**
