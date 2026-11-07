# public-body-actions data-quality report (release 2.1.0)

## Summary

The `public-body-actions` dataset gains a display heading and detail for each deadline, open-ended precision values, a corrected final-milestone rule, repaired display text for confirmed PDF artefacts, an audited body hierarchy, and a MINOR version bump (`2.1.0`). Raw columns (`original_deadline_raw`, `action_text`, `progress_text`) are untouched; all fixes are additive columns or enumeration values. The pipeline reruns locally (no network or LLM) and the dataset is republished at `/v2.1.0/public-body-actions/` with `latest/` mirroring it.

## Counts before/after

Baseline from the spec's measured baseline (2026-11-07); "after" computed from `pipelines/actions_pipeline/steps/resolve_action_identity/output.json` and the published `public/latest/public-body-actions/*.csv`.

| Measure | Before | After |
|---|---|---|
| Actions / observations | 186 / 279 | 186 / 279 |
| `original_deadline_raw` longer than 40 chars | 45 | 45 (untouched by design) |
| `original_deadline_precision` year / quarter / annual / ongoing / null | 127 / 51 / – / – / 8 | 127 / 51 / 4 / 4 / 0 |
| `reported_deadline_precision` quarter / year / ongoing / null | 261 / 1 / – / 17 | 261 / 1 / 17 / 0 |
| Actions with a non-empty `original_deadline_label` | n/a (column absent) | 186 |
| Actions with `original_deadline_milestones` | n/a | 145 (76 from 2022–2025, 69 from 2026–2030) |
| Original-deadline confidence stated / interpreted | – | 163 / 23 (2022–2025: 68 / 23; 2026–2030: 95 / 0) |
| `…2022-2025#20` deadline | 2023 | 2025 (2025-01-01 – 2025-12-31) |
| Actions with `action_text_clean` differing from `action_text` | n/a | 14 of 186 |
| Observations with `progress_text_clean` differing from `progress_text` | n/a | 51 of 279 |
| Records with confirmed broken text | 87 | 87 records, 140 mapped occurrences (spec said 146 occurrences; the audit counts non-overlapping, URL-guarded matches per field) |
| Mapped artefacts remaining in clean fields | n/a | 0 |
| Actions with no observation | 95 | 95 (all 2026–2030) |
| Hard hierarchy findings / soft department mismatches | – / 2 | 0 / 2 |

## Rows changed

**Issue 1 – deadline label/milestones.** 186 labels added; 145 milestone cells populated (76 from the 2022–2025 timeline prose, 69 from the 2026–2030 interim-milestone column); the 45 long raw cells left untouched.

**Issue 2 – open-ended precision.** Original precision moved from null to `annual` (`…2026-2030#40`, `…2026-2030#64`, `…2022-2025#2`, `…2022-2025#62`) or `ongoing` (`…2026-2030#69`, `…2022-2025#4`, `…2022-2025#56`, `…2022-2025#61`). 17 observation rows moved from null to `ongoing` reported precision.

**Issue 3 – final milestone.** `sustainable-mobility-policy-action-plan-2022-2025#20`: 2023 → 2025.

**Issue 4 – text artefacts.** 140 mapped occurrences, full list (field, record id, before → after) in `docs/analysis/2026-11-07-text-audit.json`. By field: `progress_text` 83 and `action_text` 15 (status `repaired`: the `_clean` twin carries the repair); raw-only `output` 16, `original_deadline_raw` 10, `original_timeline_raw` 10, `support` 6 (status `flagged`, left as extracted). Most frequent repairs: `submitet d`→submitted (30), `batet ry`→battery (22), `platof rm`→platform (13), `betet r`→better (7), `efef ct`→effect (7), `thereafet r`→thereafter (7), `atet nd`→attend (7), `Commitet e`→Committee (6), `Letet rkenny`→Letterkenny (5), `efof rt`→effort (5), plus 22 rarer patterns.

**Issue 5 – no observation.** 95 actions, all in the 2026–2030 plan, have no observation. Null `latest_status` means "not yet reported", not "unknown".

**Issue 6 – hierarchy.** 0 hard findings. 2 soft parent/department mismatches, source-backed and left as is (see `docs/body-hierarchy.md`): First Home Scheme Ireland DAC (Housing dept vs parent Permanent TSB's Finance) and Stepping Out (Athlone) Ltd (Justice vs parent Rehab Group's Children/Disability/Equality).

## Unresolved / accepted

- 46 suspicious spans not in the repair map. Most are legitimate prose matching the heuristic (`target of/for/to/by` 18, `fleet …` 12, `Cabinet for` 2, `platof rms` 3 which the `platof rm` repair already handles).
- Probable real artefacts **not mapped** (not added: the map is human-reviewed): `Lifef y` (5: `…2026-2030#16` milestones and the 2022-2025 `#23` progress text in two reports), `Constructoi n` (`…2026-2030#35` milestones), `Evaluatoi n` (`…2026-2030#37` milestones). The two milestone hits are in a clean field but unmapped, so `--check` does not fail on them; a reviewer should decide on map additions.
- Raw-only fields still contain 42 mapped artefacts (flagged, by design).
- The 2 soft hierarchy mismatches above.

## Verification

| Command | Result |
|---|---|
| `cd pipelines/document_pipeline && uv run python process.py --from extract_actions --to extract_action_status --force --stop-on-error` | OK (2 plan docs, 4 report docs) |
| `cd pipelines/actions_pipeline && uv run python process.py --force --stop-on-error` | 186 actions, 279 observations, 50 relationships |
| `uv run python scripts/transform_public_body_actions.py` | published 186 / 279 / 50 |
| `uv run pytest tests/ -q` | 360 passed |
| `uv run pytest pipelines/actions_pipeline/tests -q` | 73 passed |
| `uv run pytest pipelines/document_pipeline/tests -q` | 294 passed, 4 skipped |
| `uv run pyright` | 0 errors |
| `uv run python scripts/audit_body_hierarchy.py --check` | exit 0 (hard 0, soft 2) |
| `uv run python scripts/audit_text_artefacts.py --check` | exit 0 (0 failures) |

## Site handoff

Not changed in the site repo (`publicinformation-web`).

- New `actions.csv` columns: `original_deadline_label`, `original_deadline_milestones`, `action_text_clean`.
- New `action-status-observations.csv` column: `progress_text_clean`.
- Changed enumerations: `original_deadline_precision` and `reported_deadline_precision` gain `annual` and `ongoing`.
- Unchanged raw columns: `original_deadline_raw`, `action_text`, `progress_text`.
- Recommended site use: label as the heading; milestones as detail; clean fields for prose; sort date precisions by `start` and bucket `annual`/`ongoing` separately; null `latest_status` = not yet reported.
- Body hierarchy: use `parent_id` for group pages and `government_department_id` for department pages.
- New base path: `/v2.1.0/public-body-actions/`; `latest/` mirrors it.
