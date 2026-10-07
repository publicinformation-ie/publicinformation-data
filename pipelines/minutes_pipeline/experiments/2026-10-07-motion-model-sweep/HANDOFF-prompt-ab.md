# Prompt A/B handoff (motion-model-sweep)

Date: 2026-10-07. Branch: `experiment/motion-model-sweep`.

## What this is

A focused A/B of the motion-extraction **system prompt**, independent of the
full 220-call grid:

- **Prompts**: `production` (verbatim `steps/extract_motions/process.py`
  `_SYSTEM_PROMPT`) and `exclude_procedural` (production + an explicit clause
  excluding procedural items such as confirmation/adoption of previous
  minutes). The production prompt is **not** modified — the variant is
  script-local.
- **Models**: the 5 candidates + gold `opencode-go/deepseek-v4-pro`.
- **Sample**: first **10** files of the frozen `sample.json` order.
- **Effort**: default only (thinking enabled).
- **Total**: 6 models × 2 prompts × 10 files = **120 live calls**.

## Prerequisites

- Run from this worktree: `…/.worktrees/motion-model-sweep`, branch
  `experiment/motion-model-sweep` (contains the prefix fix, Responses routing,
  and this probe).
- `experiments/2026-10-07-motion-model-sweep/sample.json` must be present
  (it is, untracked; reproducible via `sample.py`).
- opencode-go credentials in `~/.local/share/opencode/auth.json`.
- Network access; **live LLM spend**.

## Commands

```bash
cd /Volumes/ext/dev/publicinformation/publicinformation-data/.worktrees/motion-model-sweep/pipelines/minutes_pipeline

# 1) Run the A/B (120 calls, ~10–20 min, 6 parallel workers)
uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab.py

# 2) Score + report (offline)
uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab_report.py
```

## Durability / resume

Each completed call is appended to
`experiments/2026-10-07-motion-model-sweep/prompt_ab.jsonl` and flushed+fsynced
immediately. If the run dies, **just re-run the same command** — completed
`(prompt, model, file)` keys are skipped. To start clean, delete
`prompt_ab.jsonl`. Do **not** commit `prompt_ab.jsonl` (generated data).

## Reading the result

`prompt_ab_report.py` prints, per prompt, each candidate's `text-F1`,
`field_acc`, `count_mae`, `failure_rate`, and estimated `mean_cost`, scored
against gold **under the same prompt**, plus a
`modified − production` delta column. `n` is the files scored for that cell.

## Known behaviour

- `gpt-6-luna` and `muse-spark-1.3-contributor` are Responses-only and are
  routed automatically; both work at default effort.
- Failures fail closed (motions `null`, error recorded) and show as `FAIL`;
  they do not crash the run.
- Costs are char/4 **estimates**, not metered usage — fine for ranking.
- Gold is a model reference, not human ground truth; a delta near zero on 10
  files is directional only.
