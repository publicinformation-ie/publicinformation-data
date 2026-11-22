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
