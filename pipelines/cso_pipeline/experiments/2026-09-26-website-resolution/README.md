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

Gold set: 30 bodies (24 unresolved + 6 resolved; 23 own_site, 7 no_own_site). With 23
own_site bodies, a 0.04 difference in own cov / false not_found is one body — read the
table as direction, not significance.

| approach | judge | n | own cov | own prec | no-own P | no-own R | false not_found | $ |
|---|---|---|---|---|---|---|---|---|
| apify | haiku-cc | 30 | 0.48 | 0.58 | 0.25 | 0.14 | 0.13 | 0.39 |
| apify | ollama:deepseek-r1:8b | 30 | 0.48 | 0.44 | — | 0.00 | 0.04 | 0.00 |
| apify | ollama:gemma4:latest | 30 | 0.48 | 0.48 | — | 0.00 | 0.13 | 0.00 |
| haiku_cc | haiku-cc | 30 | 0.52 | 0.92 | 0.17 | 0.14 | 0.22 | 0.39 |
| haiku_cc | ollama:deepseek-r1:8b | 30 | 0.57 | 0.93 | 0.25 | 0.14 | 0.26 | 0.39 |
| haiku_cc | ollama:gemma4:latest | 30 | 0.61 | 0.88 | 0.00 | 0.00 | 0.22 | 0.39 |
| haiku_cc_then_apify | haiku-cc | 30 | 0.61 | 0.78 | 0.17 | 0.14 | 0.09 | 0.39 |
| haiku_cc_then_apify | ollama:deepseek-r1:8b | 30 | 0.57 | 0.72 | 0.25 | 0.14 | 0.17 | 0.39 |
| haiku_cc_then_apify | ollama:gemma4:latest | 30 | 0.65 | 0.79 | 0.00 | 0.00 | 0.17 | 0.39 |
| haiku_then_apify ¹ | ollama:gemma4:latest | 10 | 0.43 | 0.43 | — | 0.00 | 0.00 | 0.06 |
| seed_only | haiku-cc | 30 | 0.35 | 0.89 | — | 0.00 | 0.61 | 0.39 |
| seed_only | ollama:gemma4:latest | 30 | 0.43 | 0.83 | — | 0.00 | 0.52 | 0.00 |

¹ 10-body pilot from the first run. The Haiku tier failed there (no ANTHROPIC_API_KEY), so
this row is effectively seed+apify, not a Haiku result. Superseded by the `haiku_cc*` rows.

`$` column: for `haiku_cc*` rows it is only the search-fee estimate (39 searches × $0.01);
Haiku tokens ran on the Claude Code plan and are not counted. Rows from `--approach all`
runs (every `haiku-cc` judge row) carry the cumulative spend of the whole run, which is why
`seed_only | haiku-cc` and `apify | haiku-cc` show $0.39. Apify was fully cached for every
new row (`apify_paid_queries: 0`).

### Haiku via Claude Code subagents

The Haiku search and judge tiers ran as `haiku-oracle` subagents (Read/Write/WebSearch only)
answering exported prompt files, which `haiku_cc_bridge.py` then ingested into the same
caches the API path uses (`--haiku-source cc`, `--judge haiku-cc`). Search: 30 bodies, 39
searches in total, 0 missing / invalid / over_budget. Judge: 203 prompts, and the
completeness rerun recorded 0 new ones. Fidelity caveats:

1. Claude Code's `WebSearch` is not the API's `web_search_20250305` tool. It has no
   `user_location: IE` and no hard `max_uses: 3`; the limit was enforced by instruction only.
2. `interpret_haiku`'s citation guard only checks `own_site` against the subagent's
   **self-reported** result list, so the guard is weaker. The live probe and the judge still
   catch fabricated URLs downstream.
3. There is no token accounting, so `$` is the search-fee estimate only (see above).
4. Subagents run at default temperature under the Claude Code system prompt. The API judge
   uses `temperature=0`.
5. So the question answered is directional: does a Haiku-search tier add coverage over apify,
   and does a Haiku judge beat deepseek-r1:8b?

Haiku's result URLs included deep links (e.g. a PDF brochure), which exposed a probe bug:
non-HTML bodies were parsed as HTML and crashed the run. Fixed in `lib/website_probe.py`
(non-HTML Content-Type → `dead`, `error="non_html: <type>"`).

## Decision
- Cascade: **apify** over seed_only — cuts false-not-found from 0.52 to 0.13 at ~$0.007/body.
  seed_only alone is unusable (half of own_site bodies are missed).
- Judge: **deepseek-r1:8b** over gemma4 on the apify cascade (false_not_found 0.04 vs 0.13,
  +2 own sites) at ~30s/call; gemma4 remains a viable cheaper primary. qwen3.8:27b-mlx
  rejected (this machine can't run it at reasonable speed).
- Unlisted directory domains seen (add to DIRECTORY_DOMAINS): publicinformation.ie,
  constructiondirectory.ie (added).
- Implications for Plan 2 (Haiku tier, via Claude Code subagents — directional, see caveats):
  - **Put a Haiku-search tier before apify.** Against the current `apify | deepseek` decision
    (own cov 0.48, own prec 0.44, false not_found 0.04), `haiku_cc_then_apify | deepseek`
    reaches 0.57 / 0.72 / 0.17. The large gain is precision: over half of apify's own_site
    claims are wrong, while Haiku alone is at 0.92–0.93. The cost is false not_found:
    because Haiku settles a body first, apify never sees the ones Haiku got wrong. Plan 2 should
    send Haiku `no_own_site` / not_found residue on to apify, not treat it as final.
  - **Haiku judge: a better choice than deepseek-r1:8b on the Haiku-first cascade, not on apify alone.** On
    `haiku_cc_then_apify` the haiku-cc judge wins on every metric (0.61 / 0.78 / 0.09 vs
    0.57 / 0.72 / 0.17), and it is the best row overall. On `apify` alone it is more precise
    (0.58 vs 0.44) but has more false not_found (0.13 vs 0.04). It also removes the ~30s/call
    local-model wait.
  - no_own_site recall stays ≤ 0.14 for every approach (1 of 7). No cascade identifies
    "has no website" reliably; Plan 2 must not rely on it for that.
  The verify/decide/judge stack in `lib/` is validated end-to-end on live data.

### Final decision (2026-09-27) — supersedes the apify | deepseek decision above
- **No Anthropic API, ever.** Haiku runs only as Claude Code `haiku-oracle` subagents through
  the exchange-file bridge. The subagent path is therefore the production path, not a proxy,
  so no real-API spot check is needed; caveats 1, 2 and 4 describe the production system itself.
- **Cascade: `haiku_then_apify`.** Seed → Haiku search (subagents) → Apify on the residue.
  Haiku `no_own_site` / not_found residue goes on to Apify.
- **Judge: `deepseek-r1:8b` first, `haiku-cc` only on `unsure`.** deepseek runs locally and
  unattended, and routing only its `unsure` verdicts to subagents keeps plan-quota use to a
  small share of all judge prompts. The all-haiku-cc judge row (0.61 / 0.78 / 0.09) is the reference
  this hybrid is compared against on the gold set.
- **Targets reset to the measured baseline.** No cascade meets spec §9 (≥ 90% coverage /
  ≥ 97% precision). Plan 2's gold-set acceptance is "no regression against the best measured
  row", plus the spec's structural criteria. Improving precision is a follow-up.
