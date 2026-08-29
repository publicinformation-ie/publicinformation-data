# resolve_action_identity

First step in `actions_pipeline`'s own step sequence (after the cross-pipeline `document_pipeline/steps/extract_actions` reference in `pipeline.json`). Unlike every step upstream, this one is corpus-shaped: it reads `document_pipeline`'s *entire* output at once — every plan's actions and every report's observations — rather than one document at a time, because minting a stable identity and joining a report onto its plan both require seeing the whole set together.

## Why

Upstream, an action is identified by where its text sat on a page (`p009-t01-r01`, from `extract_actions`). That is a fine provenance record and a terrible identity: it changes if the PDF is re-typeset, and it says nothing about which action the document itself calls "action 48". This step derives identity from what the document *states*:

```
action_id = {plan_slug}#{action_number}
```

The plan edition is deliberately part of the key. An action renumbered in a later plan is genuinely a different published row — a citation of "SMP action 48" means the 2022-2025 one — so continuity across editions is expressed as a relationship (`extract_relationships`, next step), never by collapsing two rows into one. Action numbers are unique only within a plan, which is exactly why the key is namespaced by `plan_slug`.

Two further jobs:

- **The original deadline comes from the plan that declares the action, never from a progress report.** A deadline in a report is a *reported* deadline. Sourcing the baseline from the earliest report instead was considered and rejected: it agrees with the plan on ~91% of the SMP corpus, which is what makes it dangerous rather than merely imprecise — it would look right almost everywhere while being wrong on exactly the actions that slipped earliest, the highest-value rows in a dataset about slippage.
- **Observations join to actions via the report's explicit `reports_on`**, never inferred from content or filename. An observation whose number has no matching plan action is `UnresolvedActionNumber`: skipped and logged, never guessed onto a neighbouring action.

## What it does

1. For every plan record in `extract_actions/output.json`, strips the leading ordinal (`"1. \x07Develop…"` → `(1, "Develop…")`) off each action cell to recover its published number, and mints `{plan_slug}#{action_number}`. A cell with no leading ordinal has no stated number and is `UnresolvedActionNumber` — skipped, never assigned a synthetic one.
2. Resolves each action's **original deadline** (`resolve_original_deadline`): prefers a real deadline column (`raw_date`) over the plan's `TIMELINE & OUTPUT` cell; within that cell, prefers a single unambiguous date (`confidence: "stated"`) over inferring one from a multi-milestone narrative (`confidence: "interpreted"`, taking the latest year introduced as a milestone — `Q<n> <year>` or `<year>:`). A year that is part of a range or contract name (`IMMAC 2025-2030`) is never read as a deadline; unlabelled years with no milestone marker are refused rather than guessed at. A non-empty timeline cell that yields no confident date is `DateParseError` — the raw text is kept, structured fields stay null.
3. Reads `lead`/`support`/`output` off the plan's own table columns (`column_value`, case-insensitive alias lookup — `extract_actions` keys `columns` with `normalize_text`, not `normalize_header`, so keys keep source casing like `LEAD`/`OWNER`).
4. Joins every `role: report` document's observations (`extract_action_status/output.json`) onto their action via the report's own `reports_on` + the observation's `action_number`. An observation naming an unknown plan, or a number with no match in that plan, is `UnresolvedActionNumber` — skipped, never attached to a neighbour.
5. For the *earliest* report mentioning each action, compares its reported deadline against the action's original deadline. A mismatch is `DeadlineDivergedAtFirstReport` — informational, not a fault: it means the action had already slipped before the first progress report was written, which is exactly the kind of row this dataset exists to surface.

## Inputs

- `--input`: `document_pipeline/steps/extract_actions/output.json` (wired via `pipeline.json`'s `input_steps` — the runner asserts it exists and is non-empty, exiting with "run document_pipeline first" otherwise).
- `document_pipeline/steps/extract_action_status/output.json` — located as a sibling of `--input`'s parent step directory; missing it is fatal (`sys.exit`), since this step's join is meaningless without it.
- `documents.yml`, via `document_pipeline.documents.load_documents()` — plan `doc_title`/`url`/`public_body_id` provenance, keyed by `doc_slug`.

## Output

`output.json` — `{ metadata, actions: [...], observations: [...] }`.

| `actions[]` field | Description |
|---|---|
| `action_id` | `{plan_slug}#{action_number}` — this step's minted identity |
| `public_body_id` / `plan_slug` / `plan_title` / `source_url` | Plan provenance, from `documents.yml` |
| `action_number` / `action_text` | Recovered from the leading ordinal, stripped of BEL artifacts |
| `original_deadline_raw` / `original_deadline_start` / `original_deadline_end` / `original_deadline_precision` | Structured baseline deadline, or all null if unresolved |
| `original_deadline_confidence` | `"stated"` / `"interpreted"` / `None` — never guessed silently |
| `original_timeline_raw` | The plan's own timeline cell text, preserved verbatim regardless of parse outcome |
| `lead` / `support` / `output` | Read off the plan table's own columns |
| `source_page` / `source_ref` | Positional provenance only — never identity |

| `observations[]` field | Description |
|---|---|
| `action_id` | The action this observation was joined to |
| `report_slug` / `report_title` / `as_of` | Report provenance |
| `status` / `progress_text` / `asi` | Carried through from `extract_action_status` |
| `reported_deadline_raw` / `reported_deadline_start` / `reported_deadline_end` / `reported_deadline_precision` | The report's own re-stated deadline — never merged into the action's original deadline |
| `source_page` / `source_ref` | Positional provenance |

## Errors

| `error_type` | Scope | Cause |
|---|---|---|
| `UnresolvedActionNumber` | plan action / observation | No leading ordinal on a plan action cell, or an observation's `action_number` (under its report's `reports_on`) matches no plan action; skipped, never guessed onto a neighbour |
| `DateParseError` | plan action | A non-empty timeline cell yielded no confident deadline; raw text kept, structured fields null |
| `DeadlineDivergedAtFirstReport` | observation | Informational only — the earliest report's deadline for an action differs from the plan's original deadline, i.e. the action had already slipped before the first report |

## Running it

```bash
cd pipelines/actions_pipeline
uv run python process.py --force --stop-on-error --verbose
```

This step always recomputes in full regardless of `--force` — it is a whole-corpus join, not an incrementally-resumable per-record step, so there is no meaningful "already up to date" state for it to skip.
