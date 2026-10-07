# Prompt A/B — results (2026-10-07)

Probe: `prompt_ab.py` → `prompt_ab_report.py`. First 10 files of the frozen
`sample.json`, 6 models (5 candidates + gold `deepseek-v4-pro`), **default
effort**, two system prompts (`production` vs `exclude_procedural`). 120/120
records written to `prompt_ab.jsonl` (untracked, generated).

## Coverage / failures

Calls that failed were **client timeouts at the 180 s hard limit** in
`src/lib/llm_extract.py`, not protocol errors.

| prompt | model | ok | failed files |
|---|---|---:|---|
| production | gpt-6-luna | 10/10 | — |
| production | muse-spark-1.3 | 10/10 | — |
| production | deepseek-v4.1-flash | 10/10 | — |
| production | glm-5.3-flash | 9/10 | jul-plenary |
| production | qwen3.8-flash | 9/10 | 110319_01 |
| production | **gold deepseek-v4-pro** | **8/10** | 13-apr-2026, 110319_01 |
| exclude_procedural | gpt-6-luna | 10/10 | — |
| exclude_procedural | muse-spark-1.3 | 10/10 | — |
| exclude_procedural | deepseek-v4.1-flash | 9/10 | nov-2022 |
| exclude_procedural | glm-5.3-flash | **3/10** | 7 files |
| exclude_procedural | qwen3.8-flash | **3/10** | 7 files |
| exclude_procedural | **gold deepseek-v4-pro** | **9/10** | 110319_01 |

Gold timed out 3/20, so the paired table is over the **8 files with gold under
both prompts**, not 10.

## Mean motions per file (over-extraction signal)

| model | production | exclude_procedural |
|---|---:|---:|
| **gold deepseek-v4-pro** | **4.9** | **9.2** |
| gpt-6-luna | 15.2 | 9.9 |
| muse-spark-1.3 | 12.8 | 9.0 |
| deepseek-v4.1-flash | 15.3 | 13.0 |
| glm-5.3-flash | 12.9 | 20.7 (n=3) |
| qwen3.8-flash | 12.8 | 4.0 (n=3) |

Cheap models extract ~2–3× gold's count under the production prompt. The
exclusion clause narrows the gap for gpt-6-luna/muse-spark but not deepseek, and
gold's *own* count rises 4.9 → 9.2, so the clause changes the reference too.

## Paired delta (same 8 files, vs each prompt's own gold)

| model | prod F1 | mod F1 | ΔF1 | Δacc | Δcount-mae |
|---|---:|---:|---:|---:|---:|
| deepseek-v4.1-flash | 0.830 | 0.912 | **+0.082** | −0.124 | −1.50 |
| gpt-6-luna | 0.697 | 0.866 | **+0.169** | −0.208 | −0.75 |
| muse-spark-1.3 | 0.897 | 0.939 | **+0.043** | −0.111 | −0.63 |
| glm-5.3-flash | 0.563 | 0.372 | −0.190 | +0.032 | +0.63 |
| qwen3.8-flash | 0.758 | 0.468 | −0.290 | −0.444 | +1.00 |

Mean per-file cost ~\$0.0008–0.0018 for every candidate (gold ~\$0.006).

## Findings

1. **Over-extraction is the real gap**, and it is large: candidates emit 2–3×
   the motions gold does. Text-F1 against gold hides this; the count column
   makes it plain.
2. **The exclusion clause is not a clear win.** On the paired set, three models
   improve slightly and two drop sharply — but glm/qwen are dominated by
   timeouts, and gold's own output moves with the prompt, so the reference is
   not fixed. Treat ΔF1 as noise-level for the healthy models.
3. **Robustness**: default-effort (thinking) responses for `glm-5.3-flash` and
   `qwen3.8-flash` routinely exceed the 180 s client timeout — badly under the
   modified prompt (3/10 ok). They are not reliable production candidates at
   default effort on files of this size.
4. **Cost is a non-issue** at this scale for all candidates.

## Caveats

- n=8 paired (gold timeouts), 10-file sample, single run.
- Gold is a model reference, not human ground truth; token costs are char/4
  estimates.
