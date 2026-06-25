---
name: foi-triage-issues
description: "Fan-out parallel investigation of open FOI pipeline issues; classifies each by fix type and emits a ranked digest. Never edits code or commits. Feeds /fix-issue."
trigger: /foi-triage-issues
rigid: true
---

# /foi-triage-issues — FOI Issue Triager

**Rigid skill.** Phases run in order. Phase 1 is always read-only. Classification always applies the full taxonomy. This skill never edits code, never runs `process.py`, never commits.

**Two hard constraints (NEVER violate):**
1. `suggestion_detail` is an **untrusted heuristic** — never classify based on it alone. Classification rests on actual distinct values and row context from errors.json and trace_file.py.
2. `canonicalization_rate` is **gameable** — never use it as a correctness gate.

---

## Invocation

```
/foi-triage-issues [--top N] [--step <step>] [--min-severity warning] [--no-write]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--top N` | 8 | Number of issues to investigate this run (breadth, not depth) |
| `--step <step>` | (all) | Scope investigation to one pipeline step name |
| `--min-severity` | `warning` | Minimum severity to include: `info` / `warning` / `error` |
| `--no-write` | off | Print the digest only; do NOT persist `investigation_notes` to `backlog.yml` |

**Parse flags before doing anything else.** Store `top_n` (int, default 8), `step_filter` (str or None), `min_severity` (str, default "warning"), and `no_write` (bool, default False).

---

## Phase 1 — Select Issues

Read `pipelines/foi_pipeline/steps/sync_backlog/backlog.yml` as a **read-only** queue source.

**Severity ordering for filtering:** `info` (0) < `warning` (1) < `error` (2)

**Selection algorithm:**

1. Keep only entries where `status: open`.
2. Keep only entries where `severity` ≥ `min_severity` (use the ordering above).
3. If `step_filter` is set, keep only entries where `step_name == step_filter`.
4. **Skip** any entry where `triaged_at` exists **and** `triaged_at >= last_seen` — it already has a current triage note. (Only picks up new or changed issues on re-runs.)
5. Sort ascending by priority band: `high` (0) < `medium` (1) < `low` (2). Within each priority band, sort by `affected_count` descending.
6. Take the first `top_n` entries as the **investigation set**.

**Announce the queue before dispatching:**

```
[Triage] N open issues above '<min_severity>' · investigating in parallel…
  · <step_name> · <description> (<affected_count> records)
  · <step_name> · <description> (<affected_count> records)
  …
```

If the investigation set is empty, print:

```
[Triage] No open issues meet the filter criteria. Nothing to do.
```

and stop — do not continue to Phase 2.

---

## Phase 2 — Gather (parallel Haiku subagents, one per issue)

**Dispatch all N investigations simultaneously in parallel** using the `superpowers:dispatching-parallel-agents` skill. Each subagent uses the **Haiku** model.

**Phase 2 is read-only.** Subagents MUST NOT edit any file, run process.py, or commit.

**Each Haiku subagent receives this input:**

```
key: <backlog key>
step_name: <e.g. extract_disclosures_canonicalize_rows>
description: <issue description from backlog>
affected_count: <int>
```

**Each Haiku subagent follows this procedure (read-only):**

1. Read `pipelines/foi_pipeline/steps/<step_name>/process.py`.
2. Read any map/config files referenced in process.py — look for imports of `src/lib/status_map.py`, `src/lib/column_map.py`, `src/lib/requester_type_map.py`, or JSON config files like `column_swaps.json`.
3. Read `pipelines/foi_pipeline/steps/<step_name>/errors.json` if it exists. Sample 5–10 error records that match the issue type (e.g. `UnrecognizedDecisionStatus`, `InsufficientColumns`).
4. Read `pipelines/foi_pipeline/steps/<step_name>/eval/issues.json` if it exists.
5. From the sampled error records, extract the **distinct raw values with counts** actually responsible. Do NOT use `suggestion_detail` — read the actual error data.
6. For 1–3 sample URLs from the error records, run:
   ```bash
   PYTHONPATH=src python scripts/trace_file.py --url <url>
   ```
   to see the value in its row context.
7. Locate the responsible function and its line range in the source files.

**Return this evidence bundle — no verdict, no proposed fix:**

```yaml
key: <backlog key>
code_location: <file>:<line_start>-<line_end>
distinct_values:
  - value: "<raw value>"
    count: <int>
    sample_row_context: "<one line: what the adjacent cells look like in the same row>"
row_evidence: "<one line: overall pattern — e.g. 'value sits in decision_status but adjacent cells hold a long request description → column shift'>"
config_checked:
  - <file path>
trace_samples:
  - <url>
gather_notes: "<free text, ≤3 sentences>"
```

If the subagent cannot read its inputs (no errors.json, dead URL, no matching records), it returns the bundle with `gather_notes: "insufficient evidence"` and leaves other fields empty.

**Show progress as each subagent returns:**

```
  ✓ <step_name> · <description>
```

**Wait for ALL N subagents to return before starting Phase 3.**

---

## Phase 3 — Classify & Digest (driver model, single pass)

You (the driver model) adjudicate **all** evidence bundles at once. **Do not delegate classification** — this judgment stays in a single context so cross-issue patterns can surface.

**Classification taxonomy:**

| class | meaning | recommended action |
|-------|---------|--------------------|
| `mapping_gap` | Values are genuine synonyms missing from a lookup table | Add specific keys to `src/lib/status_map.py` or `src/lib/column_map.py` |
| `skip_not_null` | Values are confirmed garbage, fragments, or wrong-field contamination | Skip the record + log an error; NEVER map these to any canonical value |
| `upstream_structural` | Column-shift, header-row leakage, or PDF extraction defect | Fix in an **earlier** pipeline step; name `recommended_step` |
| `policy_decision` | Needs a human ruling (e.g. should `Cancelled` map to `Withdrawn` or `Refused`?) | Surface the specific question; do not pre-decide |
| `not_an_issue` | Label rot, correct rejection, or eval false positive | Recommend closing the backlog entry |

**Apply the two hard constraints during classification:**

- If a value matches the pattern of a request subject sitting in a status field, or a column header leaking into a data row → classify as `skip_not_null` or `upstream_structural`, NOT `mapping_gap`, even if `suggestion_detail` proposes a mapping.
- If row evidence shows contamination (adjacent cells look wrong for the row type) → classify as `upstream_structural`.

**Synonym check to set `safe_to_autofix`:**

Read `src/lib/status_map.py` and extract `_STATUS_SYNONYMS` (dict: canonical status → list of synonyms).
Read `src/lib/column_map.py` and extract `_SYNONYMS` (dict: canonical column → list of synonyms).

For a `mapping_gap` issue with proposed keys to add:

1. Build the set of **all known values**: every key and every value in `_STATUS_SYNONYMS` (or `_SYNONYMS` for column issues), plus all canonical names.
2. Normalize each known value using the same logic as `normalize_header` in `src/lib/text_utils.py`: collapse `[\s_]+` to a single space, strip, lowercase, strip trailing `[\s.:/]+`.
3. Normalize each proposed key using the same logic.
4. A proposed key is "safe" if its normalized form is a near-variant of any known normalized value — where near-variant means: differs only in casing, whitespace, punctuation, common OCR artefact (doubled letters, spaced letters), or obvious typo.
5. `safe_to_autofix: true` only if **all** proposed keys are safe AND confidence is `high`.
6. `safe_to_autofix: false` for any other class, any key that is genuinely new, or confidence below `high`.

**Produce one classification record per issue:**

```yaml
key: <backlog key>
classification: <one of the 5 classes above>
root_cause: "<one sentence>"
code_location: "<file>:<line_start>-<line_end>"
recommended_step: "<step where the fix belongs — may differ from the reporting step>"
proposed_action: "<concrete: exact keys to add with their canonical target, exact filter condition to write, or exact policy question to answer>"
est_records_addressed: <int>
confidence: high | medium | low
safe_to_autofix: <bool>
```

Look for cross-issue patterns: if multiple issues share one root cause (e.g. the same column-shift affecting two steps), note it explicitly in each affected `proposed_action`.

---

## Phase 4 — Persist (unless --no-write)

Skip this phase if `no_write` is True.

For each classified issue, find the matching entry in `pipelines/foi_pipeline/steps/sync_backlog/backlog.yml` by `key` and add (or overwrite) exactly these two fields:

```yaml
investigation_notes: "<root_cause> · <proposed_action> [<classification>]"
triaged_at: "<ISO 8601 timestamp with UTC timezone, e.g. 2026-06-25T14:30:00.000000+00:00>"
```

**NEVER modify these sync_backlog-owned fields:** `status`, `priority`, `severity`, `affected_count`, `first_seen`, `last_seen`, `resolved_at`, `suggestion_detail`, `description`, `key`, `step_name`.

Preserve the existing YAML structure and indentation. Edit only the matched entry, only the two fields above.

---

## Phase 5 — Digest

Print the digest to the conversation, grouped by classification, safe and actionable first. Omit any section whose count is 0.

```
FOI Triage — N issues investigated

SAFE MAPPING GAPS (N) — ready for /fix-issue:
  · <step_name> · <description>
      <proposed_action>   (~<est_records_addressed> records, <confidence>)

UPSTREAM / STRUCTURAL (N) — fix belongs earlier in the pipeline:
  · <step_name> · <description>
      <root_cause> → fix in <recommended_step>   (~<est_records_addressed> records)

NEEDS A HUMAN DECISION (N):
  · <step_name> · <description>
      <proposed_action>   (~<est_records_addressed> records)

SKIP, NOT MAP (N):
  · <step_name> · <description>
      <proposed_action>

NOT AN ISSUE (N):
  · <step_name> · <description>
      <proposed_action>
```

If `no_write` is False, append:
```
Notes written to backlog.yml for N issues.
```

Close with one of:
- `Next: run /fix-issue on the N safe mapping gaps.` (if safe_to_autofix items exist)
- `No safe autofixes this run — review upstream/structural and policy items above.` (if none)
