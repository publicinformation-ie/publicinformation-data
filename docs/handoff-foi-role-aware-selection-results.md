# FOI role-aware selection: results

Branch `feat/foi-role-aware-selection` (on top of `feat/foi-gate-on-structure-not-text`). Spec: `docs/handoff-foi-role-aware-selection.md`. All numbers are from existing step outputs; nothing was rerun for this report. Result files are under `pipelines/foi_pipeline/experiments/2026-11-14-pdf-extractor-bakeoff/results/` (gitignored, key ones force-added). Measurement script: `final_measures.py` (output `task12_final_measures.md`).

## 1. Read this first: the role gate withholds a lot of probably-good data

Errors fell 2,875 to 1,308 (-54%). Work packages 1 and 2 (vocabulary and header mapping) did most of that cleanly: 2,875 to 1,757 with records unchanged. The role gate (work package 3) is where the cost is.

**Blast radius of the gate** (before = `foi-before-role-aware-2026-11-14`, after = current outputs):

| | number |
|---|---|
| files newly withheld (`TableStructureUnreliable`) | 66 (63 from the role gate, 2 override files with records, plus Fingal 2016 flagged but shielded, see below) |
| records lost from them | 2,903 (2,672 from the 63 gate files plus 231 from the 2 override files) |
| net record change, all causes | 59,600 to 56,850 (-2,750, -4.6%) |
| errors those 66 files carried before | 566 |
| newly withheld files that had 0 errors before and published records | 29 files, 1,320 records |
| newly withheld files with under 5% error rate before | 36 |
| newly withheld files with 40+ records and 3 or fewer errors before | 17 |

In plain terms: the gate removed about 566 errors and cost 2,903 records. About 40 of the 63 gate-withheld files had 0 canonicalize errors before (this counts files with no records and no errors; the strict count of files that published records with 0 errors is 29). Largest likely-good losses: body 1594 non-personal-requests 2017-2020 (118/152/156/141 records, 0-3 errors each, role contamination about 0.38), DLR 2021 (1244: 153 rows, 0 errors, contamination 0.39, anchored 0.0), Galway 2019 (1342: 199 rows, 3 errors), Louth 2019/2020/2021/2023 (1501: 107/65/88/96 records, 0 errors), CRU 2021-2025 (1153), HIQA 2018/19 (1390), Mayo 2023 Q1/Q2 and 2024/2025 Q2 (1508, contamination 0.20-0.23, just above the 0.2 line). Nobody looked at these files by eye; the "probably good" judgement rests on 0 or few errors before.

**Calibration is thin** (`role_calibration.md`). Chosen thresholds `max_role_contamination = 0.2`, `min_anchored_row_share = 0.8`. The label for "bad" is a per-file cross-role error rate of at least 0.2, and there are only 5 bad files in the even-id fit set and 7 in the odd-id holdout.

| split | TP | FN | FP | TN | recall | FPR | good records withheld |
|---|---|---|---|---|---|---|---|
| even (fit) | 5 | 0 | 49 | 531 | 1.00 | 8.4% | 2,968 / 29,914 (9.9%) |
| odd (holdout) | 6 | 1 | 30 | 511 | 0.86 | 5.5% | 1,495 / 22,573 (6.6%) |

No (contamination, anchored) pair reached recall 0.80 with FPR 0.05 on the fit set, so the pair was chosen by Youden J. A recall of 5/5 and 6/7 means one missed bad file moves recall by 14 points. On the 10-file gold set the flag misfires: `41fa00` (gold accuracy 0.98) is flagged at contamination 0.21; `6ab587` (gold 0.88) is flagged; `494a78` (gold 0.22) is flagged correctly; `e93ccc` (gold 0.00) is flagged correctly.

**Regression: Mayo (1508) Disclosure-Log-Q1-2024 and Q4-2023.** Both switched from `pdfplumber` to `camelot_stream` and now carry an error on every row (43 of 43 and 35 of 35; 0 errors before). The records are still published, with the project description sitting in `requester_type` (for example `requester_type: "Records in relation to project R312 Glenisland Phase 2,"`, `request_description: "Received"`) and a `known_issues` entry. So the selection change turned two clean files into two files of misplaced data that the gate did not stop. Mayo overall lost 274 records (1,138 to 864) and went from 0 to 82 errors.

**Fingal 2016 (1295) is flagged but not fixed.** The gate empties its rows (anchored share 0.776), but `extract_disclosures_normalize_header/override.json` holds a hand-curated 368-row table for that URL which replaces the emptied rows downstream. 119 records and 268 errors (the single worst file, 20% of all remaining errors) are unchanged. Fixing it means editing or removing that table, which was out of scope.

**Expectations that were not met.** The spec expected `misplaced_published` to reach 0. It went 930 to 701 and 701 remain, mostly in files that pass the gate (1594 non-personal-requests 2021-23: 223, 1876: 191, 1244 2024 log: 70, 1340: 63, 1107: 32, 1295: 27). `cross_role` errors did not fall (61 to 63); the gate withheld nothing that shrank them. The total is 1,308, close to the "about 1,200" stop line, so the stop rule did not fire, but the quality gain is smaller than the error count suggests.

### Decision for you on the gate (numbers per option)

| option | effect | cost |
|---|---|---|
| A. Keep as is | 1,308 errors, 56,850 records | 2,903 records withheld (4.6% of the baseline); about 1,320 of those from files that had no errors |
| B. Loosen the contamination threshold to 0.3 | recall on the fit set drops 5/5 to 4/5, odd set unchanged at 6/7; FPR 8.3% (fit) and 4.6% (odd); good records withheld 2,933 (fit) and 1,291 (odd) | saves only about 35 (fit) and 204 (odd) good records. Not a big win because the anchored threshold also withholds. Loosening the anchored threshold (0.8 to a lower value) was not gridded below 0.8 and would need a new calibration |
| C. Gate and fall back to the next candidate instead of withholding | not measured. The selection already ranks all candidates by contamination, so a failing winner means all candidates failed or were unmeasured | would need a rule for which failing candidate to publish; needs a run |
| D. Record-level gating (drop only rows with a foreign-kind cell) | not measured | the Mayo case shows row-level data can be wrong in every row, so this helps mainly for files with a few bad rows |

Recommendation: do not ship A unchanged. Either B plus eye-checking the 17 files named above, or hold the gate output behind a flag until Mayo 1508 and the 17 are checked. The plan said not to tune further, so none of B-D was run.

## 2. Ledgers 00 to 03 side by side

| class | 00 before | 01 WP1+WP2 | 02 role gate | 03 override gate | what changed |
|---|---|---|---|---|---|
| text_variant | 1,004 | 0 | 0 | 0 | punctuation variants now canonicalize (WP1; RTE `Journalist.` etc.) |
| glyph_split | 69 | 69 | 70 | 70 | unchanged; RTE Q4 2020 camelot_lattice 30 errors is the largest |
| composite_cell | 18 | 18 | 2 | 2 | role-aware selection stopped choosing the extractor that merged cells |
| cross_role | 61 | 61 | 68 | 63 | not reduced; +7 then -5 from override gate |
| header_mapping | 844 | 730 | 346 | 346 | WP2 mapping fixes (Waterford 1864) then gate; 262 of the 346 is Fingal 2016 |
| unknown_value | 879 | 879 | 840 | 827 | vocabulary gaps; see section 5 |
| **total** | **2,875** | **1,757** | **1,326** | **1,308** | |
| `misplaced_published` | 930 | 930 | 703 | 701 | |
| records | 59,600 | 59,714 | 57,081 | 56,850 | |
| `TableStructureUnreliable` files | 72 | 72 | 135 | 138 | gate |

Error types, before to after: `UnrecognizedRequesterType` 1,998 to 821, `StatusValueIsDate` 477 to 154, `UnrecognizedDecisionStatus` 369 to 306, `StatusValueIsColumnHeader` 31 to 27, `TableStructureUnreliable` 72 to 138.

Detail files: `cause_ledger_00_before.md`, `01_wp1_wp2.md`, `02_role_gate.md`, `03_override_gate.md`; `wp1_wp2_before_after.md`, `role_gate_before_after.md`, `override_gate_before_after.md`, `role_gate_extractor_changes.md` (every falling body explained except 1389 and 1752: 1389 coru 2022/2024 extractor swapped, 1752 stvincents 2018 now yields 0 records without a gate error).

Override files (task 11): the gate now applies to files in `column_mappings.json`, scored with their mapping. 2 are newly withheld on shape and anchoring, not contamination: Central Bank 2025 (130 records, 4 errors before) and NCCA 2024 (101 records, 14 errors before). Both look mostly good (`override_files_newly_failing.md`). Passing overrides unchanged: Fingal 2022 and 2023, LCC 2023, Meath 2018/2019 H1/H2.

## 3. Errors and records per body (before to after)

35 of 112 bodies changed; 29 lost records, 5 gained. Full list in `task12_final_measures.md`. Largest movers:

| body | errors before | errors after | records before | records after |
|---|---|---|---|---|
| 1655 RTE | 1,101 | 98 | 1,584 | 1,502 |
| 1594 | 54 | 2 | 1,382 | 661 |
| 1501 Louth | 8 | 6 | 1,088 | 628 |
| 1295 Fingal | 554 | 291 | 878 | 993 |
| 1508 Mayo | 0 | 82 | 1,138 | 864 |
| 1153 CRU | 16 | 4 | 328 | 79 |
| 1864 Waterford | 114 | 0 | 6 | 120 |
| 1342 Galway | 16 | 13 | 1,389 | 1,190 |
| 1122 | 84 | 20 | 115 | 18 |
| 1244 DLR | 3 | 3 | 679 | 526 |
| 1200 | 63 | 33 | 813 | 704 |
| 1104 Central Bank | 27 | 23 | 367 | 237 |
| 1552 NCCA | 14 | 0 | 101 | 0 |
| 1390 HIQA | 7 | 7 | 767 | 663 |
| 1388 | 0 | 0 | 224 | 125 |

Caveat: body 1655 RTE records stayed at about 1,500 although about 1,000 errors cleared; many error rows were published with `known_issues` rather than dropped, so an error is not always a lost record (1,185 records carry `known_issues` against 1,308 errors).

## 4. Calibration

Full grids (even-id fit and odd-id holdout, 24 threshold pairs each, with good-records-withheld) are in `role_calibration.md`. Chosen pair and its confusion matrix are in section 1. Population: 1,262 PDF files with mapped roles (1,133 measurable; 129 had no column with 5 or more non-placeholder cells so contamination is unmeasured; 112 roles unmapped; 71 non-PDF or empty). Selection rule: no pair met recall 0.80 and FPR 0.05 on the fit set; the pair with the highest Youden J was chosen, then checked on the holdout. Odd-id recall 0.86 and FPR 5.5% met the plan's bars (recall at least 0.6, FPR at most 10%). Known thin spots: Fingal 2023 worst-role contamination 0.56 (0.52 without header leftovers) against a 0.5 line; forward-filled merged headers can create spurious duplicate roles; a file whose roles are mapped but all cells are `None` is not gated on contamination (the anchored check still applies).

## 5. Files still at or above 20% errors

By `errors / (records + errors)`: 52 files (99 before), 647 errors, 758 surviving records; by share of surviving records carrying `known_issues`: 57 files, 867 records. Table with body, extractor, dominant class and URL is in `task12_final_measures.md`. Reasons by dominant class: unknown_value 37 files (vocabulary gap or description in the requester column; the remaining vocabulary is for you, section 6), cross_role/header_mapping 14 (Fingal 2016 shielded by `override.json`, Fingal 2022 (22 errors), Central Bank 2023 gated-flagged but 69 records still emitted from `mistral_cache`, DLR 2024 log), glyph_split 1 (RTE Q4 2020 `camelot_lattice`, 30 of 54 rows; split letters are not repaired by design). 36 of the 52 use `pdfplumber`, 8 `mistral_cache`, 4 `camelot_stream` (including both Mayo regressions). Most are small files (1 to 45 rows) that were already erroring before and were neither fixed nor withheld; none was fixed beyond the work packages.

## 6. The four decisions

1. **Docling cache.** Files a docling cache run would cover: 138 gated plus 51 not gated with errors at 20% or more = **189 files** (spec expected 100-150). Of the 138 gated, 3 still emit records (257), so 135 files emit nothing and have the most to gain. Docling gold accuracy 0.91 (26/36 passing) versus the chosen selection; run is offline and free but heavy to install, 5-60 s per file (189 files is roughly 15 to 190 minutes). Recommendation: yes, and restrict the first pass to the 66 newly gated files if you want to recover the section 1 losses first. `docling` results for the bake-off sample are in `results/docling/`.
2. **File-level outcome check (withhold a whole file when at least half its rows error).** At 50% or more: **21 files, 251 surviving records, 426 errors** by `errors / (records + errors)`; or **31 files, 275 records, 213 errors** by share of records carrying `known_issues`. Before the work packages the spec counted 46 files and 1,620 records. Of the 21, one is Fingal 2016 (119 records, 268 errors) and two are Mayo Q1-2024/Q4-2023 (78 records); withholding them would cost 251 records and fix the worst remaining misplaced data. The count is now small enough that this can be one pass-through step. Recommendation: yes. It also catches Fingal 2016 despite `override.json`.
3. **Branch and merge order.** `feat/foi-role-aware-selection` was cut from `feat/foi-gate-on-structure-not-text` (PR #26 scorer fixes was merged 2026-11-14). Order: merge `feat/foi-gate-on-structure-not-text` first if it is not yet on `main`, then this branch (its diff contains that branch's work and would otherwise be reviewed twice). Do not merge this branch before you decide section 1: it publishes 2,903 fewer records than the base. The tracked `steps/*/output.json` files are not part of the commits; `transform_disclosure_files/output.json` is modified in the worktree and was never staged.
4. **Vocabulary (`unknown_value`).** 827 errors across about 400 distinct values (`cause_ledger_03_override_gate.md` lists all). Top values; please rule on each as a requester type or status, or say it is a data fault:

| value | count | bodies |
|---|---|---|
| Student | 29 | 1844, 1122, 1775, 1052, 1112 |
| Interested business group | 28 | 1392 |
| Student/Lecturer | 26 | 1207 |
| Member of staff. | 26 | 1655 |
| Refusedon administrative grounds | 16 | 1335 |
| Public Service | 15 | 1456 |
| Others - public | 15 | 1775 |
| SU | 15 | 1574 |
| Closed | 13 | 1573, 1153 |
| Member of staff | 13 | 1655, 1460 |
| provisions of | 11 | 1602 |
| Employee | 11 | 1164, 1122 |
| Community | 10 | 1456 |
| Consultant | 10 | 1207 |
| Client Journalist | 10 | 1112 |
| Students Union | 10 | 1574 |
| Business Representative | 9 | 1587 |
| Member of | 8 | 1211, 1817 |
| FOI | 8 | 1104, 1295 |
| Release with redactions | 8 | 1122 |
| Interest Group Journalist | 8 | 1112 |
| Access Journalist | 6 | 1786 |
| General | 6 | 1868 |
| Partial | 6 | 1679 |
| Catagoir an Iarratasoira | 5 | 1570 |
| Representative | 5 | 1570 |
| Section 15(1)(a) | 5 | 1200, 1834, 1622 |
| Clarification sought | 5 | 1590 |
| Parent | 5 | 1164 |
| Academic | 5 | 1658, 1786 |
| Activist | 5 | 1868 |
| Political Correspondent | 5 | 1094 |
| Union | 4 | 1207 |

Several are not vocabulary at all but extraction faults: `Member of staff.`, `Member of`, `provisions of`, `FOI`, `Section 15(1)(a)`, `Catagoir an Iarratasoira` (a header) and `Refusedon administrative grounds` (a run-together cell). Note also that `Public Rep.` now maps to Elected-Oireachtas (one error, body 1196); please confirm that is right.

## 7. Step 2 measurement: records with no reference and no dates

**3,228** of 56,850 published records have no `foi_reference_id`, no `date_received` and no `decision_date`. The spec's figure was 3,354 of 59,600. The continuation-row merge in the scorer stays, as the plan says; this report does not decide whether `anchored_row_share` makes it unnecessary. Top bodies: 1486 (747), 1235 Dublin City (547; one file, `disclosure-log-2025.pdf`), 1655 RTE (521), 1390 HIQA (444), 1456 (229), 1104 (141), 1112 (111), 1834 (94). Limerick (1486) and HIQA files carry most of it, in files that pass the gate.

## 8. Cleanup done in this task, and follow-ups

Done (commit `chore(foi): drop pdfplumber_lines; selection-key tests; doc cleanups`): `pdfplumber_lines` removed from `candidates.py` (bake-off script follows `CANDIDATE_NAMES`; historical results untouched); stale `select_pdf_table` docstring fixed; normalize_header README now points at `src/lib/table_utils.py` and gives `_MAX_CONTINUATION_ROWS = 6`; the 2026-06-05 sweep experiment is marked stale in its README and `run.py` docstring (not rewritten); 4 tests added for selection-key ordering; Fingal 2024 test pins `mistral_cache`.

Follow-ups not done (all parked from review): date regex accepts `.` separator, thin tests for it; private import of `_STATUS_LOOKUP` and double classify in the gate; no unit test for the placeholder filter (`N/A`, `nil`, `-`, `tbc`) or bare-digit anchors; `_DIGITS_RE` duplicated; headerless pdfplumber table that passes shape is kept without comparison to other candidates; the `pdf_extractor` override config guard test is vacuous until a `column_mappings.json` entry uses that key; the none-candidate test only asserts `res[0] == []`; empty-mapping shape test missing; `wp1_newly_resolved.md` and negative test for requester map missing; `report.py` of the bake-off still lists `pdfplumber_lines` (historical).

Also noted: results for tasks 5, 8, 10 and 11 were measurement-only commits without independent review.
