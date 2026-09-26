# CSO website resolution experiment (2026-09-26)

Spec: `docs/superpowers/specs/2026-09-26-cso-website-resolution-design.md` §7.

Question: which search cascade (seed_only / haiku / apify / haiku_then_apify) and which
judge (ollama gemma4 / qwen3.8 / haiku) resolves CSO body websites best on the gold set,
per dollar?

## Run
    uv run python pipelines/cso_pipeline/website_eval/sample_gold.py          # once; then hand-label the CSV
    uv run python pipelines/cso_pipeline/experiments/2026-09-26-website-resolution/run_experiment.py --approach seed_only
    uv run python .../run_experiment.py --approach haiku --limit 10   # pilot: check spend
    uv run python .../run_experiment.py --approach all
    uv run python .../run_experiment.py --approach all --judge ollama:qwen3.8:27b-mlx   # cached search, judge only
    uv run python .../run_experiment.py --approach all --judge haiku --no-fallback
    uv run python .../report.py

## Results
(pasted report.py table)

## Decision
- Cascade:
- Judge:
- Unlisted directory domains seen (add to DIRECTORY_DOMAINS):
- Implications for Plan 2:
