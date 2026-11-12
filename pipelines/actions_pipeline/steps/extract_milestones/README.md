# extract_milestones

Fourth step of `actions_pipeline`, reading `resolve_action_identity/output.json`. Splits each action's `original_deadline_milestones` prose into one record per milestone, so multi-milestone rows (for example SMP 2026–2030 action 4) are queryable.

It is a separate step because it applies a new technique (text splitting) and must never rewrite upstream files. No model call, no cost.

## Rules (see `milestones.py`)

- A milestone starts at a marker: `Qn YYYY` followed by a dash or colon, `YYYY:`, `YYYY interim target -`, or a bare `YYYY` / `YYYY onwards` before a spaced dash at the start of the text or after a sentence end. `IMMAC 2025-2030` and prose such as `by Q4 2030.` never split.
- A cell made only of quarters (`Q2 2023; Q4 2023`) yields dated records with empty text.
- A date is published only when a marker states it. Text with no marker is one undated milestone; empty input yields none.
- The split is lossless: pieces re-join to the whitespace-normalised input. On failure the action falls back to one undated record and `MilestoneRoundTripFailed` is logged to `errors.json`.

## Output

`output.json`: `{"metadata": {...}, "milestones": [...]}`. Each record: `milestone_id` (`<action_id>/m<ordinal>`), `action_id`, `ordinal`, `due_label`, `due_start`, `due_end`, `due_precision`, `milestone_text`.
