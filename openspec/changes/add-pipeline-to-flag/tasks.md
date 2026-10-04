## 1. Runner implementation

- [x] 1.1 Add `--to STEP` to the argument parser in `src/lib/pipeline_runner.py` with help text mirroring `--from`
- [x] 1.2 Resolve `--from`/`--to` to start/end indices over the ordered `steps` list; exit non-zero naming the value when a step is unknown or when `--to` precedes `--from`
- [x] 1.3 Iterate from step 0 through the inclusive end index: steps before the start index follow the existing `--from` skip path (message + `prev_out`), break after processing the end step, and keep the absolute-path, staleness, `always_run`, and subprocess branches unchanged

## 2. Tests

- [x] 2.1 Add a test that `--to <step>` runs only up to and including that step (no later step runs)
- [x] 2.2 Add a test that `--from <a> --to <b>` runs only the inclusive window, plus a single-step `--from X --to X` case
- [x] 2.3 Add tests that unknown `--to` and unknown `--from` exit non-zero with the offending name in the error
- [x] 2.4 Add a test that an inverted range (`--to` before `--from`) exits non-zero
- [x] 2.5 Add a test that `--to` on the last step behaves like a full run
- [x] 2.6 Add a test that the first windowed step receives the prior step's output as its `--input` and staleness baseline
- [x] 2.7 Add a test that `--to` with `--stop-on-error` halts within the window on a failing step
- [x] 2.8 Add a test that `--to` with `--force` runs every step in the window regardless of staleness
- [x] 2.9 Add a test that an absolute-path upstream step inside the window validates upstream output and runs no subprocess
- [x] 2.10 Add a test that an `always_run` step inside the window runs even when not stale
- [x] 2.11 Run `cd pipelines/foi_pipeline && uv run pytest tests/test_pipeline_runner.py -q` and confirm existing runner tests still pass

## 3. Documentation and verification

- [x] 3.1 Document `--to` (and `--from`+`--to` windowing) in `AGENTS.md` Common Commands / runner flags
- [x] 3.2 Document `--to` in `README.md` and `pipelines/foi_pipeline/AGENTS.md` alongside the existing `--from` examples
- [x] 3.3 Run the FOI pipeline test suite (`cd pipelines/foi_pipeline && uv run pytest tests/ -q`) and `uv run pyright`
