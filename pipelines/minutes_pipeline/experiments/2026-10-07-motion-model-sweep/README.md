# Motion model sweep (2026-10-07)

## Hypothesis

A cheaper `opencode-go` model at default or thinking-disabled effort matches
gold motion-extraction quality closely enough that the cheapest non-regressing
combo can replace the current default for the full ~2,026-file run.

## Grid

5 candidate models × {default, none} = 10 combos + gold + baseline = 11 arms
× 20 files = **220 calls** (200 candidate + 20 gold). This supersedes the
spec's low/high + gold-at-max grid: Task 1 probes showed the effort gradient
is not testable on `/go`, so only default (thinking enabled) vs `"none"`
(thinking disabled) ran.

| Model | In / Out $/M |
|---|---|
| `opencode-go/gpt-6-luna` | 0.10 / 0.50 |
| `opencode-go/muse-spark-1.3-contributor` | 0.10 / 0.20 |
| `opencode-go/deepseek-v4.1-flash` | 0.15 / 0.60 |
| `opencode-go/glm-5.3-flash` | 0.15 / 0.50 |
| `opencode-go/qwen3.8-flash` | 0.15 / 0.47 |
| gold: `opencode-go/deepseek-v4-pro` (default) | 0.66 / 1.98 |

Rows are `<model>@default` / `<model>@none`; `baseline` is the frozen old
production output (regression guard, null costs, excluded from cost ranking).

## Probe (Task 1 wire-format decision)

```python
# Effort plumbing (Task 1 probes rounds 1-2 + 1b, 2026-10-07, 9 live calls on
# opencode-go/deepseek-v4.1-flash via POST /zen/go/v1/chat/completions):
# - Gradient DEAD: suffix `model:low` -> 400; top-level `effort`, header
#   `x-opencode-effort`, and documented top-level `reasoning_effort`
#   (low vs max, trivial + hard prompts) all 200 with no effort effect.
#   Cause: DeepSeek P6 forces max when the agent profile (tools + session
#   headers, completed by the Go proxy even for minimal payloads) is
#   present; upstream valid values are low/high/max only.
# - Toggle LIVE (1b, 1 call): top-level `thinking: {"type": "disabled"}`
#   (SDK extra_body) -> reasoning_tokens 0 vs baseline 82, answer still
#   correct. ONLY the "none" level is implementable. Task 3: model axis +
#   binary thinking on/off; do NOT add reasoning_effort levels (ignored).
```

Caveat wording pinned by test: `report.py` prints
"Caveat: the effort gradient ... is not testable on the /go endpoint ...".

## Adopt rule

The human picks the winner from the Pareto table subject to two gates:
(a) text-F1 within a tolerance fixed at report-review time (no preset
threshold — the table sets the context), (b) no regression vs the baseline
arm on the sample. Combos above 10% failure rate are DISQUALIFIED regardless
of F1. Wiring the winner into production is a separate follow-up task.

## Reproduce

```bash
cd pipelines/minutes_pipeline
uv run python experiments/2026-10-07-motion-model-sweep/sample.py
# effort-plumbing probe first (see Probe above), then (manual, 220 live calls):
uv run python experiments/2026-10-07-motion-model-sweep/extract.py
uv run python experiments/2026-10-07-motion-model-sweep/compare.py
uv run python experiments/2026-10-07-motion-model-sweep/report.py
```

## Notes

- **Token-estimate bias:** per-call tokens are deterministic char/4 estimates,
  not metered usage — absolute $ and the ×2,026 extrapolation carry the
  estimator's bias; relative cost ranking is exact up to the completion term.
- **Gold note:** gold = `deepseek-v4-pro` at default. DeepSeek P6 forces max
  on `/go` anyway, so max≈default there — no separate max arm needed.
- **Status:** live grid not yet run — no `arms.json`/`results.json` on disk
  (both untracked when generated). `report.py` is covered by a fixture test
  until real results exist.
