# Table ligature repair: corpus audit

`extract_pages` scrambled table cell text at ligature glyphs ("batet ry", "staf.f").
`repair_ligature_widths` (steps/extract_pages/ligatures.py) now fixes char widths
before `Table.extract()` runs. This experiment regenerates the whole document
corpus and checks that no action was gained, lost or renumbered.

## Method

1. Baseline: unscoped `uv run python process.py --force --stop-on-error --from extract_pages`
   on the code *without* the fix (`extract_pages/process.py` as of 4226e91e).
2. After: the same command with the fix.
3. `python audit.py BASELINE_DIR AFTER_DIR` (each dir holds `<step>/output.json` and `<step>/errors.json`).

The baseline must be a fresh run. A first attempt compared against the
on-disk outputs, which were stale leftovers of earlier scoped runs. It reported
`errors.json` counts rising in five steps (extract_figures 10 to 4345, and so on),
on documents with no ligature changes. A like-for-like baseline passes check (e).

## Audit output

```
Changed actions per doc: {
 "sustainable-mobility-policy-action-plan-2022-2025": 10,
 "sustainable-mobility-policy-action-plan-2026-2030": 29
}
Top new words: [('platform', 6), ('Committee', 6), ('battery', 3), ('platforms', 3), ('submitted', 2), ('thereafter', 2), ('effectiveness', 2), ('different', 2), ('Platform', 2), ('better', 2), ('affordable', 2), ('Better', 1), ('Letterkenny', 1), ('patterns', 1), ('effective', 1)]
Damaged tokens before/after: 6 / 0
RESULT: PASS
```

All five hard checks pass. About 22 changed SMP 2026-2030 actions were
expected; 29 changed. The extra ones carry the same kind of fix (the new-word
list is all genuine words), and check (c) shows no letters moved.

## Published bundles

15 documents changed (`full.md`, `meta.json`, `bundle.tar.gz`, plus `index.json`),
e.g. "staf f&" becomes "staff &" and "afet r" becomes "after" in
ev-infrastructure-strategy. Only files that differ between baseline and after were
committed. Bundles for the climate-action-plan-* documents show as deleted by an
unscoped publish even without the fix (the baseline run does it too), and 42 other
bundles drift from HEAD with or without the fix. Neither is part of this change and
neither is committed.

## Tracker check (SMP 2026-2030)

Compared with `SMP Action Plan 2026 - 2030 Tracker.csv`: 95 of 95 action numbers
match. 13 action texts differ, not the 2 the plan expected. None is a letter-order scramble:

- 3, 6, 9, 29, 52, 61, 77: a line-wrap hyphen leaves a space ("Multi- Annual"). Not a ligature issue.
- 8, 59: tracker has no trailing full stop. 35: tracker has an extra comma.
- 74: "atti udes". The `tti` ligature is followed by a space char the PDF stream
  carries in the glyph's advance gap. Unchanged by this fix; see follow-ups.
- 82: "aligned to" vs tracker "aligned with".
- 88: the footnote is dropped (`extract_actions`, separate follow-up).

## Decision

The width-spreading repair keeps cell membership unchanged and touches only
table chars. Clipping chars to cell bounds was rejected because it can move text
between cells.

## Follow-ups

- Line-wrap hyphen leaves "Multi- Annual" in action text.
- Space after a `tti` ligature ("atti udes", action 74).
- Action 88 footnote; SMP Goal; `action_number` split.
