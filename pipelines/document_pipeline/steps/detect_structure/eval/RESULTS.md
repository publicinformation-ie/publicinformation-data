# Detector-change results log

One entry per measured detector change, newest last. The protocol is in
`openspec/changes/improve-chapter-split-accuracy/design.md` (D0):

1. Implement the rule with unit tests.
2. Run `score.py --baseline eval/baseline.json` and paste the summaries and the per-document diff below.
   Give a reason for every per-document regression.
3. Run `compare.py` over all 40 documents and record detection-method changes, `InvalidStructure`
   count changes and orphaned overrides for the documents without gold.
4. Write the entry, **then** refresh the baseline (`--refresh-baseline`) and commit.

A step that improves no targeted document, or causes a regression it cannot explain, is reverted,
not tuned. The held-out summary is printed every time but is never a design input.

Run from `pipelines/document_pipeline`:

```bash
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py
PYTHONPATH=".:../../src" python steps/detect_structure/eval/compare.py
```

## Entry template

### <step id> — <short name>

- **Change:** <what the rule does, one line>
- **Commit:** <sha measured at>
- **Kind:** detector change | measurement correction

| Summary | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before | | | | | |
| tuning, after | | | | | |
| held out, before | | | | | |
| held out, after | | | | | |
| all, before | | | | | |
| all, after | | | | | |

**Per-document changes** (from the baseline diff):

| Document | Metric | Before | After | Reason (required for every regression) |
|---|---|---:|---:|---|

**Documents without gold (`compare.py`, 30 documents):**

- Detection-method changes: <slug: old -> new, or none>
- `InvalidStructure` count: <before -> after>
- Slug changes / orphaned overrides: <list, or none>

**Notes:** <anything a reader needs to interpret the numbers>

---

## Entries

### 1.4 — Starting baseline (held-out gold added)

- **Change:** none to the detector. Four held-out gold documents added (`ev-infrastructure-strategy` and `sustainable-mobility-policy-action-plan-2022-2025` were tried and registered in `no_toc.json`: malformed contents listing, and no contents page).
- **Commit:** 83214cab
- **Kind:** measurement (baseline extended)

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning | 10 | 2 | 0.47 | 0.34 | 0.83 |
| held out | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all | 14 | 3 | 0.51 | 0.42 | 0.87 |

Held-out documents: `climate-action-plan-2023-annex-of-actions`, `climate-action-plan-2025`, `national-ports-policy`, `nta-statement-of-strategy-2026-2030`.
Tuning numbers are unchanged from the pre-held-out snapshot baseline. The held-out gold was committed before the detector was scored against it. Gold pages were verified against each chapter's opener page in the text layer (divider pages recorded, per `GUIDELINE.md`).

### D1 — One detection entry point (**measurement correction**, not a detector gain)

- **Change:** `detect_document_structure` in `process.py` wraps `filter_outline`, `resolve_outline_positions` and the cascade; `process()` and `score.detect_document` both call it. Before, the eval called `detect_structure()` directly and scored a tree production never writes. Production output is unchanged (the existing tests pass unchanged and a new test asserts `process()` and the eval produce identical trees).
- **Commit:** see git log (`feat(detect_structure): one detection entry point`)
- **Kind:** measurement correction. The movement below is the eval catching up with production; it is not an improvement in detection. This becomes the **post-D1 reference** for D10.

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before | 10 | 2 | 0.47 | 0.34 | 0.83 |
| tuning, after | 10 | 3 | 0.49 | 0.37 | 0.83 |
| held out, before | 4 | 1 | 0.62 | 0.63 | 1.00 |
| held out, after | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all, before | 14 | 3 | 0.51 | 0.42 | 0.87 |
| all, after | 14 | 4 | 0.52 | 0.44 | 0.87 |

**Per-document changes** (baseline diff):

| Document | Metric | Before | After | Reason |
|---|---|---:|---:|---|
| `national-roads-2040-final-report` | page attribution | 0.72 | 1.00 | `_Hlk…` bookmarks no longer scored as chapters (filter_outline now applied); now fully correct |
| `national-roads-2040-final-report` | exact F1 / precision | 0.80 / 0.67 | 1.00 / 1.00 | same |
| `gda-transport-strategy-2022-2042` | tolerant F1 | 0.65 | 0.88 | outline entries moved to their heading page (resolve_outline_positions now applied); exact F1 unchanged, so the remaining GDA boundaries are still wrong by one page or more |

No regressions. Held-out documents did not move (none has a filtered bookmark or a late outline entry).

**Documents without gold** (`production_view.py`, 40 documents): no change. Production output is identical by construction, because `process()` already ran these steps. Method counts: 21 toc, 14 outline, 4 numbering, 1 font; `InvalidStructure` total 12. `compare.py` was not used for this step: it runs its own cascade and does not go through the production entry point. `production_view.py` (new) does, and is the tool for steps D2 to D8.

**Notes:** prediction in the design held: national-roads lost its `_Hlk` chapters, and GDA's boundaries moved.

### D2 — Outline entry normalisation

- **Change:** whitespace is collapsed before the heading number is split (`_split_outline_title`, used by `from_outline` and `resolve_outline_positions`); adjacent same-level, same-page outline fragments are merged only when the joined title is the exact text of a heading line on that page (`merge_wrapped_outline_entries`).
- **Commit:** see git log (`feat(detect_structure): normalise outline entries`)
- **Kind:** detector change

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before (post-D1) | 10 | 3 | 0.49 | 0.37 | 0.83 |
| tuning, after | 10 | 3 | 0.49 | 0.37 | 0.87 |
| held out, before | 4 | 1 | 0.62 | 0.63 | 1.00 |
| held out, after | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all, before | 14 | 4 | 0.52 | 0.44 | 0.87 |
| all, after | 14 | 4 | 0.52 | 0.45 | 0.90 |

**Per-document changes:**

| Document | Metric | Before | After | Reason |
|---|---|---:|---:|---|
| `gda-transport-strategy-2022-2042` | title accuracy | 0.67 | 1.00 | `15. Freight, Delivery and` + `Servicing` is now one chapter |
| `gda-transport-strategy-2022-2042` | page attribution / tolerant F1 | 0.26 / 0.88 | 0.29 / 0.90 | the merge removes a spurious boundary |

No regressions.

**Prediction not met (recorded, not tuned):** the design expected `18. Enviromental` + `Assessment` to merge as well. They do not. The bookmarks name p. 227 but the heading is printed on p. 228, so the joined title is not on the stated page and the exact-match rule declines to merge. This is a bookmark-points-one-page-early fault, a different problem from wrapping; GDA's `override.json` already covers it. Not addressed by this change.

**Documents without gold** (`production_view.py`): no method change; `InvalidStructure` 12 -> 12. Slugs changed on two documents, no override orphaned:
- `gda-transport-strategy-2022-2042`: `15-freight-delivery-and` + `servicing` -> `15-freight-delivery-and-servicing` (override slugs `assessment` and `18-enviromental` are untouched).
- `moving-together-strategy` (no gold): three wrapped appendix headings merged (`appendix-1` + `case-studies`, `appendix-2` + `ensuring-a-just-transition-through-investment`, `appendix-3` + `implementation-plan`); nodes 103 -> 100. Each join was verified against the page text. Its override slugs are not affected.

**Notes:** exact F1 for GDA stays at 0.14: its remaining chapters are on pages that differ from gold by one, so the outline pages themselves are off. That is a separate cause and not part of D2.

### D3 — Outline plausibility

- **Change:** an outline is chapter evidence only if, after filtering, at least two entries sit at its shallowest level (`outline_is_plausible`). Otherwise the cascade continues as if there were no outline and logs an informational `OutlineNotUsed`.
- **Commit:** see git log (`feat(detect_structure): reject implausible outlines`)
- **Kind:** detector change

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before (post-D2) | 10 | 3 | 0.49 | 0.37 | 0.87 |
| tuning, after | 10 | 3 | 0.53 | 0.39 | 0.87 |
| held out, before (post-D2) | 4 | 1 | 0.62 | 0.63 | 1.00 |
| held out, after | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all, before (post-D2) | 14 | 4 | 0.52 | 0.45 | 0.90 |
| all, after | 14 | 4 | 0.55 | 0.46 | 0.90 |

**Per-document changes:**

| Document | Metric | Before | After | Reason |
|---|---|---:|---:|---|
| `climate-action-plan-2023` | exact F1 | 0.00 | 0.53 | its outline was one `Untitled` entry; the cascade now reaches the TOC (method `outline` -> `toc`, 1 -> 193 nodes) |
| `climate-action-plan-2023` | page attribution / exact precision / exact recall | 0.02 / 0.00 / 0.00 | 0.23 / 1.00 / 0.36 | same |
| `climate-action-plan-2025-annex-of-actions` | exact F1 | 0.12 | **0.00 (regression)** | its outline (1 level-1 root, 15 level-2) is rejected, as intended, but the fall-through does not yet find the chapters: the TOC match rate is 14%, below the gate (`LowTocMatchRate`), so the cascade lands on `numbering` with 7 nodes, none at a gold boundary. The old tree was 1 node (the root) that happened to sit on one gold boundary (precision 1.00, recall 0.06). The TOC path is blocked by the `RE \|Title` code mismatch and the side-panel prose in the gate denominator, which are D7 and D6 |
| `climate-action-plan-2025-annex-of-actions` | page attribution / tolerant F1 | 0.09 / 0.12 | 0.07 / 0.21 | same |

One regression, explained and expected to reverse with D6 and D7; checked again in those entries.

**Documents without gold** (`production_view.py`): the only method changes are the two documents above (`climate-action-plan-2023` outline -> toc; `climate-action-plan-2025-annex-of-actions` outline -> numbering). No other document has an outline that fails the check. `InvalidStructure` 12 -> 12. No override is orphaned.

**Notes:** this check does not reach the held-out set; none of the four held-out documents has an implausible outline.

### D5a — TOC printed pages and wrapped-entry continuation

- **Change:** each TOC entry records its `printed_page` (int for arabic, the printed string for roman, none otherwise; matched to its row by position because right-column numbers are read after the left column). A wrapped title is joined onto the entry before it when that entry has no page yet, the line sits directly under it, is not indented less, is in the same type size, has no heading number and does not open with its own label (`Goal 7:`); joining is done only in a TOC that prints page numbers. A bare roman numeral at the right edge is a page number, not an entry. The contents heading itself, with a page after its leaders, is never an entry.
- **Commit:** see git log (`feat(detect_structure): TOC printed pages and wrapped entries`)
- **Kind:** detector change (first of three D5 sub-steps; judged against D10(c) together with 5b and 5c)

Summaries are unchanged from D3 (tuning 10 / 3 fully correct / exact F1 0.53 / page attribution 0.39; held out 4 / 1 / 0.62 / 0.63; all 14 / 4 / 0.55 / 0.46). **No per-document change on any gold document**, and no regression.

**Why no scored gain yet.** The documents this targets, emra and connecting-ireland, are still below the TOC gate (emra: 104 -> 94 entries, matched 42 -> 47, match rate 0.429 -> 0.534, gate 0.60), so they stay on `numbering`. The captured pages are what D6 (gate denominator) and D8 (placement) consume. The scored effect of D5 is therefore judged after 5c.

**Documents without gold** (`production_view.py` and the frozen `compare.py` comparison, which was refreshed for this step: `eval/expected.json`):
- `emra`: 9 genuine wrapped titles joined (`Members of the Eastern and` + `Midland Regional Assembly`, ...).
- `code-of-practice-fishing-vessels-under-15m`: 1 wrapped title joined; slug `8-manning-...-and` -> `8-manning-...-and-organisation-of-working-time`; match rate 0.865 -> 0.871. No override orphaned.
- `climate-action-plan-2023-q2-progress-report`: a junk `ii` entry no longer produced; match rate 0.923 -> 1.0.
- `sustainable-mobility-policy-year-two-progress-report`: 24 -> 23 entries, match rate 0.708 -> 0.739 (see limitation).
- Detection methods unchanged for all 40 documents; `InvalidStructure` 12 -> 12.

**Defects found and fixed while measuring** (each has a test): a roman page-number suffix exposed the contents heading line as an entry (CAP 2023 q1/q3); `Goal 7:` was joined onto the entry before it (`sustainable-mobility-policy-action-plan-2026-2030`); `Foreword` (11 pt) was joined onto the 9.5 pt entry after it (`code-of-practice-recreational-craft`). The label and same-size guards came from those two.

**Known limitation (recorded, not tuned):** a TOC that prints the page number on the *first* line of a wrapped entry is the opposite layout to the one this rule targets. `sustainable-mobility-policy-year-two-progress-report` has one such case (`System in Ireland` + `Case Study: ...`); the joined title will not match the body and is logged `TocEntryUnmatched` for review. It was wrong before (a stray `System in Ireland` entry) and is wrong in a different way now.

**Spec change made while implementing:** the "TOC entry continuation" requirement said a line with its own page number always starts a new entry, which contradicted its own scenario. It now says a line follows an entry only when that entry has no page yet; the guards are in a new requirement, "Continuation guards".

### D5b — TOC chapter labels

- **Change:** `Chapter N` (any case, optional `:`, `–`, `-`, `|`) is read as heading number `N` of a level-1 entry, on the title line or alone on the line above it. A body heading printed with the label (`Chapter 1 | Purpose`) now meets the TOC entry `Purpose` (`build_occurrence_index`). New level signal `label` (after `numbering`, before `indent`, needs at least two labels): unnumbered non-furniture entries between labels are level 2; a repeated chapter number is a section of that chapter; entries before the first label, furniture and division labels (`Appendix A`, `Annex 2`, `Part B`) stay level 1.
- **Commit:** see git log (`feat(detect_structure): TOC chapter labels`)
- **Kind:** detector change

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before | 10 | 3 | 0.53 | 0.39 | 0.87 |
| tuning, after | 10 | 3 | 0.58 | 0.42 | 0.87 |
| held out, before | 4 | 1 | 0.62 | 0.63 | 1.00 |
| held out, after | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all, before | 14 | 4 | 0.55 | 0.46 | 0.90 |
| all, after | 14 | 4 | 0.59 | 0.48 | 0.90 |

**Per-document changes** (baseline diff, before = after 5a):

| Document | Metric | Before | After | Reason |
|---|---|---:|---:|---|
| `sustainable-mobility-policy` | exact F1 | 0.22 | 0.71 | its `Chapter N – …` entries were all level 1 and unmatched; chapters are now level 1 with their sections beneath, and 5 of 9 chapters land exactly |
| `sustainable-mobility-policy` | exact precision / recall | 0.17 / 0.33 | 1.00 / 0.56 | same; the 4 missing chapters are the ones set as artwork (D8) |
| `sustainable-mobility-policy` | page attribution / tolerant F1 | 0.12 / 0.44 | 0.40 / 0.71 | same |

No regressions in the final state. **A regression appeared first and was fixed before this entry** (kept here because it is a real failure mode of the rule): the first version took `all-island-strategic-rail-review-final-report` from fully correct to exact F1 0.10. Its contents list repeats `Chapter 4 |` on six sub-entries (`Decarbonisation`, `Freight`, ...). Previously those entries kept the label in their title, matched nothing, and were dropped by accident; once the label was stripped, the bare titles matched body headings and became six false chapters. Two further defects followed: the body heading for `Chapter 1 | Purpose` no longer met the stripped title (fixed by indexing the body heading without its label), and `Appendix A | …` fell to level 2 after the last chapter. The rules "a repeated chapter number is a section" and "a division label stays level 1" came from this document. After the fix it is fully correct again, with six additional correct level-2 sections (nodes 11 -> 17).

**Documents without gold** (`production_view.py` and `compare.py`, refreshed in `eval/expected.json`): production detection methods unchanged for all 40 documents; `InvalidStructure` 12 -> 12; no override orphaned. In `compare.py`'s TOC view: `emra` match rate 0.534 -> 0.595 (entries 94 -> 85; still just under the 0.60 gate), `code-of-practice-recreational-craft` 0.385 -> 0.462, `climate-action-plan-2025` TOC strategy 4/26 -> 26/26 matched (its production method stays `outline`, which is plausible).

**Notes:** the held-out documents did not move.

### D5c — TOC continuation pages

- **Change:** an untitled page directly after the last TOC page is part of the main TOC when it has at least three right-column page numbers, does not open with a `List of …` title, and (if it shares a running header with the TOC page) that header names the contents. A page after a gap is still a part-TOC and is not parsed. The pages are also excluded from the body occurrence index, as every TOC page is.
- **Commit:** see git log (`feat(detect_structure): TOC continuation pages`)
- **Kind:** detector change

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before (post-5b) | 10 | 3 | 0.58 | 0.42 | 0.87 |
| tuning, after | 10 | 4 | 0.61 | 0.48 | 0.87 |
| held out, before | 4 | 1 | 0.62 | 0.63 | 1.00 |
| held out, after | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all, before | 14 | 4 | 0.59 | 0.48 | 0.90 |
| all, after | 14 | 5 | 0.61 | 0.52 | 0.90 |

**Per-document changes:**

| Document | Metric | Before | After | Reason |
|---|---|---:|---:|---|
| `sustainable-mobility-policy` | exact F1 | 0.71 | 1.00 | its contents list continues on p. 5 (untitled, running header `… | Table of Contents`), so chapters 4 to 9 were never read; the 4 chapters set as artwork are now placed by their TOC entries and the document is fully correct |
| `sustainable-mobility-policy` | page attribution / tolerant F1 / exact recall | 0.40 / 0.71 / 0.56 | 1.00 / 1.00 / 1.00 | same |

No regressions.

**Documents without gold** (`production_view.py`, `compare.py` refreshed in `eval/expected.json`): production detection methods unchanged for all 40 documents; `InvalidStructure` 12 -> 12. Two documents read a fuller TOC: `national-investment-framework-for-transport-in-ireland` (entries 27 -> 73, matched 18 -> 47, nodes 62 -> 65; 18 slugs change) and `code-of-practice-recreational-craft` (entries 13 -> 49, matched 6 -> 27, match rate 0.462 -> 0.551). No override is orphaned, but the first document's published slugs change, so its bundle diff needs the usual review before regeneration.

**D5 as a whole** (5a + 5b + 5c, against the post-D3 reference: tuning exact F1 0.53 -> 0.61, page attribution 0.39 -> 0.48; held out unchanged): the rule improves its target `sustainable-mobility-policy` (exact F1 0.22 -> 1.00, page attribution 0.12 -> 1.00), so D10(c) holds for D5. `emra-regional-spatial-and-economic-strategy` and `connecting-ireland-rural-mobility-plan` did not move: emra's TOC match rate is now 0.595, just under the 0.60 gate (D6 removes its unpaged entries from the denominator), and connecting-ireland's text layer is garbled (a stated non-goal).

**Notes:** `sustainable-mobility-policy` being fully correct also removes its D8 target; D8 is now judged on emra alone.

### D6 — Unpaged TOC entries leave the gate

- **Change:** an entry with no printed page is `unpaged` once a left-edge column of the contents list prints page numbers (at least three entries, half or more paged). Unpaged entries are excluded from the match-rate numerator and denominator, but are still matched, still create a boundary when they match, and are still logged `TocEntryUnmatched` when they do not. Wrapped-title joining is also confined to such a column.
- **Commit:** see git log (`feat(detect_structure): exclude unpaged TOC entries from the gate`)
- **Kind:** detector change

| Summary (raw tree) | Documents | Fully correct | Exact F1 (macro) | Page attribution (macro) | Title accuracy (macro) |
|---|---:|---:|---:|---:|---:|
| tuning, before | 10 | 4 | 0.61 | 0.48 | 0.87 |
| tuning, after | 10 | 4 | 0.63 | 0.50 | 0.96 |
| held out, before | 4 | 1 | 0.62 | 0.63 | 1.00 |
| held out, after | 4 | 1 | 0.62 | 0.63 | 1.00 |
| all, before | 14 | 5 | 0.61 | 0.52 | 0.90 |
| all, after | 14 | 5 | 0.63 | 0.53 | 0.97 |

**Per-document changes:**

| Document | Metric | Before | After | Reason |
|---|---|---:|---:|---|
| `emra-regional-spatial-and-economic-strategy` | exact F1 | 0.17 | 0.44 | its 26 unpaged entries (front-matter roman folios, appendices) left the denominator: match rate 0.595 -> 0.807, above the gate, so the method changes `numbering` -> `toc` and `InvalidStructure` 1 -> 0 |
| `emra-regional-spatial-and-economic-strategy` | title accuracy / page attribution / exact recall | 0.00 / 0.04 / 0.13 | 0.83 / 0.18 / 0.40 | same |

No regressions. (`climate-action-plan-2025-annex-of-actions` does not change here and is the D7 target: 20 of its 36 entries are now excluded as unpaged, but only 4 of the 16 paged entries match until pipe-separated codes are read, match rate 0.139 -> 0.25.)

**Design correction made while implementing (spec updated):** the rule was first written as "at least half of the TOC's entries carry a page number". The corpus case it was written for, the CAP 2025 annex (16 paged chapter entries and 20 prose lines), is only 44% paged, so that rule would not have fired on it. The test is now applied per left-edge column: the contents list is paged, the side panel is a column with no page numbers. A single stray page number in an otherwise pageless list still does not count. This was found by writing the scenario test for the annex shape, not by fitting a threshold to the score.

**Orphaned override (to be handled in 9.3):** `emra-regional-spatial-and-economic-strategy` has an override for slug `1-1-vision` (and a drop of `1-2-eastern-and-midland-regional-assembly`) that was written for the old `numbering` tree, where two headings sit side by side on one baseline. The new `toc` tree has `1-2-...` but not `1-1-vision`, so `merge_overrides` reports that the override targets a slug detection did not produce, and still applies the drop. The published emra tree therefore needs the override re-pointed or removed before regeneration.

**Documents without gold** (`production_view.py`, `compare.py` refreshed): methods unchanged for 39 of 40 documents (emra above); `InvalidStructure` 12 -> 11. Match rates in `compare.py` move slightly because matched unpaged entries no longer count: `sustainable-mobility-policy-action-plan-2026-2030` 0.667 -> 0.80, `ev-infrastructure-strategy` 0.667 -> 0.767, `national-roads-2040-final-report` 0.906 -> 0.966, `code-of-practice-fishing-vessels-under-15m` 0.871 -> 0.870, `national-ports-policy` 0.833 -> 0.829.
