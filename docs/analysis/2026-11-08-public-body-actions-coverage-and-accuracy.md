# public-body-actions: coverage, accuracy and dates (2026-11-08)

Audit of the `public-body-actions` dataset (release 2.1.0, `public/latest/public-body-actions/`) ahead of planning a date-based view and a public-body-based view of actions. Read-only: no pipeline was run, no paid step was triggered, nothing was changed.

## 1. Coverage

Only 6 of the 36 curated documents in `pipelines/document_pipeline/documents.yml` are checked for actions. All six belong to the Sustainable Mobility Policy (SMP):

- Two action plans (2022-2025: 91 actions; 2026-2030: 95 actions) give 186 actions.
- Four progress reports (Year One 15, Year Two 82, Year Three 91, Final 91 observations) give 279 status observations.
- All 186 actions carry `public_body_id` 1213 (Department of Transport).

The other 30 documents are skipped by design:

- 21 `primary` documents. `extract_actions` reads only `policy_role: action-plan`.
- 9 Climate Action Plan (CAP) progress reports. Their plans are not action sources, and the CAP annexes are not ingested.

The CAP expansion (`openspec/changes/add-climate-action-plan-actions`) is a scaffold and is blocked on four decisions: non-integer action codes (`EL/23/1`) against the integer `action_number` schema, no cross-plan attribution, reports spanning plan years, and no spreadsheet intake.

Within the covered documents extraction is complete and fail-closed: the 2022-2025 plan matches its `expected_action_count` of 91, the Final report's status split (Complete 58 / Delayed 28 / Modified 5 of 91) matches the report's own published figures, and `extract_actions` / `extract_action_status` have empty `errors.json`. 95 actions (all 2026-2030) have no observation; null `latest_status` means "not yet reported".

## 2. Accuracy

No prior measured accuracy figure existed (no labelled sample, only structural checks and tests). This audit adds one, run over every row rather than a sample, because the source PDFs are local (`document_pipeline/steps/fetch_pdfs/pdfs/`).

**Method.** For each action and observation, find the row by action number in `pdftotext -layout` output for its `source_page` (independent of the pipeline's PyMuPDF extraction), and check the published value appears in that row's text. This tests extraction fidelity, not whether the source document is itself correct.

| Check | Rows | Result |
|---|---|---|
| Stated original deadlines: raw text in PDF row | 162 (163 stated, less 2022-2025 #32, row not found) | 161 match; the exception (2026-2030 #64) is probably a wrapped-text layout artefact |
| Parsed start/end consistent with raw (stated and reported) | 162 + 279 | 0 errors, all precisions |
| Interpreted deadlines: chosen year appears in the row | 23 | 23 of 23 |
| Reported deadlines: raw text in PDF row | 279 | 278 match; 1 row not located |
| Reported status: in PDF row | 97 (Year One + Year Two) | 97 of 97; 28 of these are `OnSchedule` matched across a line wrap ("On / Schedule") |

Result: no extraction errors found among the values checked. Not mechanically verified:

- 3 rows reported as `unverified` by the script: 2026-2030 #64 (deadline text not in row), 2022-2025 #32 (row regex miss), 2022-2025 #48 in the Final report (row not found).
- 182 Year Three / Final statuses. They are taken from section headings, not table rows, so the row check skips them; only the Final report's published totals reconcile.
- 101 observations whose `progress_text` does not begin with the same words as the PDF row (probably text repairs and hyphenation; not checked).

**Repeat it:** `python scripts/audit_public_body_actions.py [--json] [--check]` (needs `pdftotext` and the local PDFs). `--check` fails on mismatches only; layout-artefact rows are reported as `unverified`.

Known text defects are separate: 87 records have PDF extraction artefacts (`submitet d`, `batet ry`); 138 occurrences are repaired in `_clean` fields, 42 remain in raw-only fields, about 5 (`Lifef y`) are unmapped. See `2026-11-07-public-body-actions-data-quality.md`.

## 3. Dates

| Source | Count | Reliability |
|---|---|---|
| 2026-2030 plan, separate deadline column | 92 `stated` (dated) | High, verified |
| 2022-2025 plan, single date in timeline cell | 63 `stated` (dated) | High, verified |
| 2022-2025 plan, multi-milestone prose ("last milestone wins") | 23 `interpreted` | Read correctly, meaning uncertain (below) |
| Open-ended originals (`stated`: 3 in 2026-2030, 5 in 2022-2025) | 4 `annual`, 4 `ongoing` | No dates by design |
| **Total original deadlines** | **186** | |
| Report-restated deadlines | 279 observations (261 quarter, 17 ongoing, 1 year) | High, verified |

**Interpreted deadlines.** The year is correct for all 23 by the stated rule, but "deadline" means "latest year-labelled milestone", which is not always a completion date:

- Recurring: 2022-2025 #1 (end 2023, but "annual reports published thereafter"), #22 ("on an annual basis").
- Commencement milestone: #23, #24, #52, #78 ("commenced"), so the year is a start, not an end.
- The remaining 17 are plain completion milestones.

The commencement problem is not limited to interpreted rows: `stated` 2022-2025 #32 is a single milestone, "2022: Connecting Ireland programme commenced…", so its deadline is also a start year. Stated rows have not been swept for this.

**Slippage marker is noisy.** `DeadlineDivergedAtFirstReport` logs 76 of 91 actions because it compares start dates, so a plan's `2022` (start 1 Jan) against a report's `2022 Q4` (start 1 Oct) counts as divergence. Comparing end dates at month level gives 3 genuine divergences out of 86 comparable actions (2022-2025 #1, #47, #89). Do not build a "slipped" view on this marker as it stands.

**Other date facts.** Observations come from four report dates only (2023-10-20: 15, 2024-08-27: 82, 2025-10-03: 91, 2026-08-26: 91). Original deadlines are 127 year / 51 quarter / 8 open-ended; reported deadlines are almost all quarter, so plan-versus-report comparison needs a common bucket.

## Implications for the two views

- **Public-body view.** Trivially works today (single body, 1213). It becomes meaningful only with CAP or other policy coverage, which is gated on the CAP decisions, chiefly the `action_number` schema question (a MAJOR bump if widened to a string).
- **Date view.** Safe for stated deadlines and report-restated deadlines, with the caveat that some milestones (stated or interpreted) are commencements, not completions. For interpreted deadlines, keep the `interpreted` flag visible, show `original_deadline_label` or the milestones prose rather than a bare year, and bucket `annual`/`ongoing` separately.

## Suggested follow-ups

1. Fix the divergence check to compare end dates at month level (the rule measured in section 3), with tests.
2. Decide whether rows whose (final) milestone is a commencement or a recurrence, stated or interpreted, should be flagged (new confidence value or note) or left as is. Sweep the stated rows for commencements first.
3. Resolve the unverified rows listed in section 2.
4. Decide the CAP identity and schema question before planning a cross-body view.
