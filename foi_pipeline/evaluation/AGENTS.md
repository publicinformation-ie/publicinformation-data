# Evaluation Framework - Agent Documentation

`evaluate.py` runs quality evaluation for pipeline steps that have `steps/<name>/eval/evaluate.py`, recomputing only stale evaluations (same mtime contract as `process.py`).

## Usage

```bash
# Run all step evaluations (only stale ones)
uv run python evaluate.py

# Force specific steps
uv run python evaluate.py --steps find_disclosure_files canonicalize

# Force all evaluations
uv run python evaluate.py --force

# Verbose per-item detail
uv run python evaluate.py --verbose

# Print north-star metric (valid records, bodies, funnel)
uv run python evaluate.py --headline

# Exit non-zero on regression vs baseline.json
uv run python evaluate.py --check

# Record current scores as new baseline
uv run python evaluate.py --update-baseline
```

## Command-Line Flags

| Flag | Description |
|------|-------------|
| `--steps <names>` | Force just these step evaluations |
| `--force` | Recompute all evaluations |
| `--verbose` | Per-item detail output |
| `--headline` | Print the north-star metric |
| `--check` | Exit non-zero on regression vs baseline |
| `--update-baseline` | Record current scores as new baseline |

## LLM-Judged Steps

Steps `find_disclosure_files` and `extract_disclosures_canonicalize` (header mapping) use LLM-based quality judgment. Human-verified judgments are cached in `steps/<name>/eval/judgments.json`.

New items are proposed by the LLM with `verified='auto'` and must be human-verified (yes/no) to count toward the headline metric. A skipped evaluation makes zero API calls.

## Judge Backend Configuration

The judge backend is provider-agnostic. Configure via environment variables:

```bash
EVAL_JUDGE_PROVIDER=anthropic  # or openai (default: anthropic)
EVAL_JUDGE_MODEL=<model-id>    # provider default if not specified
EVAL_JUDGE_BASE_URL=<url>     # OpenAI-compatible URL for LOCAL models
```

### Local Model Example

```bash
EVAL_JUDGE_PROVIDER=openai \
  EVAL_JUDGE_BASE_URL=http://localhost:11434/v1 \
  EVAL_JUDGE_MODEL=qwen2.5:7b \
  uv run python evaluate.py --steps find_disclosure_files
```

> **Note:** Switching provider/model changes the recorded `judge_model` id (`<provider>:<model>`). This is your cue to re-verify cached judgments before trusting the metric.

## Baseline Comparison

Evaluations are compared against `baseline.json` (input-hash gated) to detect regressions. Use `--check` to fail on regression, `--update-baseline` to save current scores.

## Uniqueness Pass Interaction

The `find_foi_pages` step runs a post-process uniqueness check that removes records sharing a `foi_page_url`. Override records participate in this pass. If an override record shares a `foi_page_url` with an automated result, the automated result is dropped — manual truth wins.
