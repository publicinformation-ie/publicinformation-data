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
