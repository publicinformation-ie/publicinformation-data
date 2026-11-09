# Motion model sweep: experiment report

Date: 2026-10-07
Branch: `experiment/motion-model-sweep`
Status: prompt A/B complete; full 220-call grid not yet run to completion; no
model adopted.

## Summary

The minutes pipeline asks an LLM to pull motions out of council meeting
minutes. Production currently uses `deepseek-v4-flash`. This experiment asked
whether a cheaper `opencode-go` model can do the job as well, and whether a
small change to the system prompt helps.

Four things came out of it:

1. The first full-grid attempt failed 220/220 because the gateway rejected the
   provider-prefixed model ids the client sent. Fixed.
2. The six-level effort dial does not exist on this gateway. Only a binary
   thinking on/off switch works.
3. Every cheap model extracts two to three times more motions than the gold
   model. That over-extraction is the main quality gap.
4. A clause telling the model to skip procedural items did not clearly help.

The prompt A/B (120 calls) ran to completion. The full 220-call grid still has
no usable results.

## 1. Goal

Choose the cheapest model and effort setting that matches gold-quality motion
extraction, so the per-file model used across the roughly 2,026 minutes files
can change without losing accuracy. Wiring a winner into production is a
separate follow-up.

## 2. Design

### Models and prices

| Model | In / Out $ per M |
|---|---|
| `opencode-go/gpt-6-luna` | 0.10 / 0.50 |
| `opencode-go/muse-spark-1.3-contributor` | 0.10 / 0.20 |
| `opencode-go/deepseek-v4.1-flash` | 0.15 / 0.60 |
| `opencode-go/glm-5.3-flash` | 0.15 / 0.50 |
| `opencode-go/qwen3.8-flash` | 0.15 / 0.47 |
| gold: `opencode-go/deepseek-v4-pro` | 0.66 / 1.98 |

### Effort axis

The plan called for five candidate models at two effort levels, ten combos in
all, plus a gold arm and a baseline arm built from the old production output.
The effort levels shrank to two once probing showed the gateway only offers a
binary switch (section 4).

### Sample

A seeded stratified draw (`sample.py`, seed 20261007) froze 20 minutes files
into `sample.json`, each with its text, extractor name, and the old production
motions. The grid uses all 20; the prompt A/B uses the first 10 in file order.

### Scoring

`compare.py` scores each combo against the gold arm offline. It normalises
motion text, matches pairs greedily at token-set IoU of 0.8 or higher, and
reports `text_f1`, `count_mae`, `field_acc` (proposer, seconder, status),
`failure_rate`, and `mean_cost`. `meeting_date` is out of scope, owned by the
`resolve_meeting_date` step. A failed extraction scores as a full miss and
counts toward the failure rate; the file is never dropped from the
denominator. Gold null for a file raises instead of shrinking the sample.

Costs come from a chars/4 token estimate, not metered usage, so absolute
dollars carry the estimator's bias. The cost ranking between models is exact up
to the completion term.

### Adoption rule

The human picks a winner from the Pareto table subject to two gates: text-F1
within a tolerance set at review time, and no regression against the baseline
arm. Any combo above a 10 percent failure rate is disqualified.

## 3. What broke, and the fixes

### The model-id prefix (220 of 220 calls failed)

The grid addresses models as `opencode-go/<id>`. On the first live run every
call returned HTTP 400 `Model is unavailable`. The `/zen/go/v1` gateway wants
bare model ids; the same prefixed ids had returned 200 earlier that day, so the
gateway changed behaviour mid-experiment. The fix strips the `opencode-go/`
prefix in `_call_opencode` before sending. Two wire tests pin it. The poisoned
`arms.json` is quarantined as `arms.json.poisoned-400s`.

### Responses-only models

`gpt-6-luna` and `muse-spark-1.3-contributor` reject `chat/completions` with
400 `ModelProtocolUnsupported`. They are routed to `{base}/responses` instead.
Thinking-off maps to `reasoning: {"effort": "none"}` there.

Two of the ten candidate combos fail closed by design and are known before the
grid runs:

- `muse-spark-1.3-contributor@none`: its lowest Responses effort is `minimal`,
  so it rejects `none` with a 400 rather than silently thinking.
- `glm-5.3-flash@none`: it rejects the `thinking` parameter outright.

Both return a recorded error, never a silent upgrade.

### The 180-second timeout

`_call_opencode` and `_call_opencode_responses` both set a 180-second client
timeout. Slow default-effort responses hit it and fail. This is what produces
most of the failures in section 5. The production value is unchanged; the
experiment measured against it as it stands.

## 4. Effort: gradient dead, toggle live

Nine live probe calls on `deepseek-v4.1-flash` settled the wire format.

The gradient is dead. A `model:low` suffix returns 400. A top-level `effort`
field, an `x-opencode-effort` header, and the documented `reasoning_effort`
field all return 200 with no measurable change in reasoning tokens. DeepSeek's
gateway forces max effort whenever it sees an agent profile (tools plus session
headers), and the Go proxy completes that profile even for minimal payloads.
Upstream also only accepts `low`, `high`, and `max`, so most of the six levels
collapse anyway.

The toggle is live. Sending top-level `thinking: {"type": "disabled"}` drops
reasoning tokens to 0 against a baseline of 82 and still returns a correct
answer. Only `"none"` is implementable, so the grid is a binary thinking
on/off axis. Any other effort value raises `ValueError` and fails closed rather
than sending an ignored level.

## 5. Prompt A/B

### Question and method

Cheap models over-extract partly because they count procedural items, such as
the confirmation of previous minutes. The A/B tests whether adding an exclusion
clause to the system prompt closes that gap.

Two system prompts run over the same 10 files:

- `production`: the shipping prompt, unchanged.
- `exclude_procedural`: the shipping prompt plus a clause telling the model to
  skip procedural and routine approvals.

Six models (five candidates plus gold) at default effort give 120 calls.
`prompt_ab.py` runs them six at a time and appends one flushed JSON line per
call, so the run resumes after a crash. Each candidate is scored against gold
**under the same prompt**, because gold's own output moves when the prompt
changes. `RESULTS-prompt-ab.md` holds the raw numbers.

### Coverage and failures

All failures are the 180-second timeout, not protocol errors.

| prompt | model | ok / 10 |
|---|---|---|
| production | gpt-6-luna | 10 |
| production | muse-spark-1.3 | 10 |
| production | deepseek-v4.1-flash | 10 |
| production | glm-5.3-flash | 9 |
| production | qwen3.8-flash | 9 |
| production | gold deepseek-v4-pro | 8 |
| exclude_procedural | gpt-6-luna | 10 |
| exclude_procedural | muse-spark-1.3 | 10 |
| exclude_procedural | deepseek-v4.1-flash | 9 |
| exclude_procedural | glm-5.3-flash | 3 |
| exclude_procedural | qwen3.8-flash | 3 |
| exclude_procedural | gold deepseek-v4-pro | 9 |

Gold timed out on 3 of 20 calls, so the paired comparison below uses the 8
files that have gold under both prompts, not 10.

### Over-extraction

Mean motions per file:

| model | production | exclude_procedural |
|---|---:|---:|
| gold deepseek-v4-pro | 4.9 | 9.2 |
| gpt-6-luna | 15.2 | 9.9 |
| muse-spark-1.3 | 12.8 | 9.0 |
| deepseek-v4.1-flash | 15.3 | 13.0 |
| glm-5.3-flash | 12.9 | 20.7 (n=3) |
| qwen3.8-flash | 12.8 | 4.0 (n=3) |

Under the production prompt the cheap models extract roughly twice to three
times what gold does. The clause narrows the gap for gpt-6-luna and
muse-spark, but not for deepseek-v4.1-flash. Gold's own count rises from 4.9 to
9.2, so the clause moves the reference as well as the candidates.

### Paired delta, same 8 files

| model | prod F1 | mod F1 | ΔF1 | Δacc | Δcount_mae |
|---|---:|---:|---:|---:|---:|
| deepseek-v4.1-flash | 0.830 | 0.912 | +0.082 | -0.124 | -1.50 |
| gpt-6-luna | 0.697 | 0.866 | +0.169 | -0.208 | -0.75 |
| muse-spark-1.3 | 0.897 | 0.939 | +0.043 | -0.111 | -0.63 |
| glm-5.3-flash | 0.563 | 0.372 | -0.190 | +0.032 | +0.63 |
| qwen3.8-flash | 0.758 | 0.468 | -0.290 | -0.444 | +1.00 |

The first report computed this delta across different file sets, which made it
look uniformly negative. Restricting both prompts to the same 8 files flips
three of the five signs. The earlier number was an artefact.

### What the A/B shows

The clause is not a clear win. Three models gain a little text-F1 and two lose
a lot, but the reference itself moves with the prompt, and the two large losses
come from models that mostly timed out. For the healthy models the change sits
near noise. The count column is the more useful signal: the clause visibly
narrows the over-extraction for two models.

Cost was never a factor. Every candidate costs roughly $0.001 per file, gold
about $0.006.

## 6. Outcomes and recommendations

- Treat over-extraction as the problem to solve, not text-F1. The answer is
  likely prompt or schema work, or a post-filter, not a model swap.
- Drop the effort-gradient axis. Only thinking on and thinking off are real.
- `gpt-6-luna` and `muse-spark-1.3-contributor` are the strongest cheap
  candidates from this run. `muse-spark-1.3` scored highest against
  production gold (F1 0.897) and never timed out.
- Do not use `glm-5.3-flash` or `qwen3.8-flash` at default effort on files this
  size. They hit the 180-second timeout often, badly so under the modified
  prompt (3 of 10). A thinking-off arm might fix this, but both are already
  known to fail closed on `"none"`, so they are unreliable either way.
- Before adopting anything, run the full 220-call grid, and raise the client
  timeout or lower the reasoning load first, or the failure rates will swamp
  the quality comparison.
- Consider a human ground-truth sample. Gold is a model, and a model reference
  that itself over- or under-extracts cannot settle whether the cheap output is
  actually worse.

## 7. Limitations

- The prompt A/B is one run over 10 files, with 8 used for the paired delta.
- Gold timed out on 3 of 20 calls, so the reference is incomplete.
- Gold is `deepseek-v4-pro`, not human annotation.
- Token and cost figures are chars/4 estimates.
- The full grid has no results, so no Pareto ranking or winner selection has
  happened.

## 8. Artifacts

| File | What it is |
|---|---|
| `README.md` | Original design and grid |
| `sample.py`, `sample.json` | Seeded 20-file freeze (`sample.json` is generated) |
| `extract.py` | Grid harness, per-arm checkpointing |
| `compare.py` | Offline scorer |
| `report.py` | Pareto table printer |
| `prompt_ab.py` | Parallel prompt A/B probe, per-call flush and resume |
| `prompt_ab_report.py` | Paired A/B scorer |
| `prompt_ab.jsonl` | Generated A/B records (untracked) |
| `RESULTS-prompt-ab.md` | Raw A/B numbers |
| `HANDOFF-prompt-ab.md` | How to re-run the A/B |

Reproduce the A/B from `pipelines/minutes_pipeline/`:

```bash
uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab.py
uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab_report.py
```

The probe makes live LLM calls. Re-running it skips completed work.
