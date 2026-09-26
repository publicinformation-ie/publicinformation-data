# CSO website resolution experiment (2026-09-26)

Spec: `docs/superpowers/specs/2026-09-26-cso-website-resolution-design.md` §7.

Question: which search cascade (seed_only / haiku / apify / haiku_then_apify) and which
judge (ollama gemma4 / qwen3.8 / haiku) resolves CSO body websites best on the gold set,
per dollar?

## Run
    uv run python pipelines/cso_pipeline/website_eval/sample_gold.py --n-unresolved 24 --n-resolved 6   # 30-row gold set; then hand-label the CSV
    uv run python pipelines/cso_pipeline/experiments/2026-09-26-website-resolution/run_experiment.py --approach seed_only --no-fallback
    uv run python .../run_experiment.py --approach haiku --limit 10   # pilot: check spend
    uv run python .../run_experiment.py --approach all
    uv run python .../run_experiment.py --approach all --judge ollama:deepseek-r1:8b   # cached search, judge only
    uv run python .../run_experiment.py --approach all --judge haiku --no-fallback
    uv run python .../report.py

## Results

Gold set: 30 bodies (24 unresolved + 6 resolved; 23 own_site, 7 no_own_site).
The haiku_then_apify row is the 10-body pilot only — the full-run Haiku tier is
pending (needs ANTHROPIC_API_KEY); seed_only and apify rows are full 30-body runs.

| approach | judge | n | own cov | own prec | no-own P | no-own R | false not_found | $ |
|---|---|---|---|---|---|---|---|---|
| seed_only | ollama:gemma4:latest | 30 | 0.43 | 0.83 | — | 0.00 | 0.52 | 0.00 |
| apify | ollama:gemma4:latest | 30 | 0.48 | 0.48 | — | 0.00 | 0.13 | 0.21 |
| apify | ollama:deepseek-r1:8b | 30 | 0.48 | 0.44 | — | 0.00 | 0.04 | 0.00 |
| haiku_then_apify | ollama:gemma4:latest | 10 | 0.43 | 0.43 | — | 0.00 | 0.00 | 0.06 |

## Decision
- Cascade: **apify** over seed_only — cuts false-not-found from 0.52 to 0.13 at ~$0.007/body.
  seed_only alone is unusable (half of own_site bodies are missed).
- Judge: **deepseek-r1:8b** over gemma4 on the apify cascade (false_not_found 0.04 vs 0.13,
  +2 own sites) at ~30s/call; gemma4 remains a viable cheaper primary. qwen3.8:27b-mlx
  rejected (this machine can't run it at reasonable speed).
- Unlisted directory domains seen (add to DIRECTORY_DOMAINS): publicinformation.ie,
  constructiondirectory.ie (added).
- Implications for Plan 2: pending Haiku-tier result before finalising cascade order.
  The verify/decide/judge stack in `lib/` is validated end-to-end on live data.
