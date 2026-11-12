# Design

## Context

`resolve_action_identity` already preserves each plan's milestone prose in `original_deadline_milestones` and parses deadlines with `lib.date_parse.parse_date`. Downstream, `extract_relationships` shows the pattern for a separate derived table. Corpus profile (2026-11-11): 150 of 206 rows have milestone text — 69 SMP 2026–30, 76 SMP 2022–25, 5 CAP. Formats: `Qn YYYY – text`, `YYYY: text`, `YYYY – text`, `YYYY onwards – text`, `YYYY interim target - text`, undated prose, and CAP date-only lists. See proposal.md for motivation; the full task plan and splitter test list are in `docs/superpowers/plans/2026-11-11-action-milestones.md`.

## Goals / Non-Goals

**Goals:** a queryable one-row-per-milestone table; no change to existing tables; no cost; every plan processed and the result audited.

**Non-Goals:** structured owners/outputs per milestone; linking milestones to progress-report observations; fixing the known CAP `Q 4 2024` upstream parse bug; any date inference.

## Decisions

- **Separate step, not a change to `resolve_action_identity`.** One concern per step; upstream output stays untouched. Alternative (emit milestones from `resolve_action_identity`) rejected: it would couple a new technique to a stable step.
- **Deterministic regex splitter in a pure module (`milestones.py`).** Mirrors `action_references.py`. Alternative (model-based split) rejected: cost and non-determinism for a corpus that is almost entirely regular.
- **Markers partition the normalised text.** Pieces are slices starting at each marker, so nothing is dropped and the round-trip check is exact. Trailing unrelated sentences stay in the last milestone rather than being guessed at.
- **Marker rules are conservative.** `Qn YYYY` needs a following delimiter; a bare year needs `:`, `interim target`, or sits at a sentence start before a spaced dash; `IMMAC 2025-2030` and `by Q4 2030.` never split. Anything unrecognised becomes undated, never a guessed date.
- **Eight columns**: `milestone_id`, `action_id`, `ordinal`, `due_label`, `due_start`, `due_end`, `due_precision`, `milestone_text`. `YYYY onwards` keeps its label verbatim with `year` precision. Raw markers are not published; the lossless guarantee is enforced in-step.
- **Publish via the existing transform** with a keyword-only `milestones=None` parameter so existing callers keep working.

## Risks / Trade-offs

- [Splitter misreads a prose date] → audit task over all 206 rows with exact per-plan counts; review every undated-with-year row and every multi-record 2022–25 row.
- [Known miss: SMP 2022–25 action 20, a year with no delimiter] → recorded in the audit doc; text is retained inside the previous piece.
- [Release timing: v3.1.0 untracked and unreleased] → merge climate work first; fold into 3.1.0 or bump to the next minor.
- [Date-only CAP rows become empty-text records] → documented; consumers can filter on empty `milestone_text`.
