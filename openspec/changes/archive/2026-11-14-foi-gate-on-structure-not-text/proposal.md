# Proposal

## Why

FOI disclosures cannot be released while the post-PR #26 build sits 6,769 records (10.7%) below the Nov-12 baseline: 56,390 records against 63,159. The main cause is the `assess_table_structure` gate. It empties 163 PDFs that yielded 6,162 baseline records, and 84 of those files fail **only** on checks that measure no structural defect:

| Single failed check | Files | Baseline records | Junk share in baseline* | Data rows in the current extraction |
|---|---|---|---|---|
| `split_word_rate` | 67 | 2,699 | 4% (110) | 2,298 in the 54 files that pass under this change |
| `repeated_header_share` | 17 | 813 | 2% (15), 0 header-like | 895 after header rows are removed |
| `width_uniformity` (for contrast: the gate works here) | 33 | 594 | **35%** (206) | — |

\*Junk means no reference, no date received and no decision date. Measured 2026-11-14 on the working-tree outputs from PR #26 and on `foi-before-snapshot-2026-11-12`.

- **The `split_word_rate` failures are mostly false positives.** The check counts a "split pair" whenever one cell ends in a letter and the next starts lowercase. In 52 of the 67 files that rule alone breaks the 0.02 threshold. A sample of the pairs shows they are ordinary adjacent values, such as `Journalist` | `all records relating to…` and `Client` | `social housing`. A word broken by a column boundary (`S` | `ummary`) is rare. The other component counts run-together tokens such as `informaQon`, `andThe` and `yearsThe`. Those are defects in the cell text, not in the table structure. Rejecting the whole file for them throws away correct rows.
- **The `repeated_header_share` failures are already repaired downstream.** `extract_disclosures_canonicalize` drops repeated header rows (`_is_repeated_header_row`), and none of the 813 baseline records from these 17 files are header-like. The gate rejects files for a defect the pipeline already fixes.

The current extraction was re-scored offline with exactly the rules below. Three things changed: run-together tokens no longer gate; a cross-cell pair counts only when one side is a word stub of 3 letters or fewer that is not a common word; and header-equal rows are removed before scoring. Under those rules, **71 of the 84 files pass (3,193 data rows)**: 54 of the 67 split-word files and all 17 repeated-header files. **None** of the currently passing PDFs fails, and the overridden PDFs are excluded. Those figures hold whether or not removed header rows stay in the denominators. They are estimates on the currently selected candidates. Nothing has been re-run.

## What Changes

- **The gate rejects on structural defects only.** The rejection checks are width uniformity, fragment share, column-type purity, minimum rows and words split across columns. Run-together tokens inside a cell no longer reject a file. They are still measured and recorded per file.
- **Cross-cell split detection is narrowed.** A pair counts only when the column boundary leaves a word stub. Two adjacent complete values never count.
- **Repeated header rows no longer cause rejection.** Rows identical to the detected header are removed before the other metrics are computed, the same treatment fix D gave year dividers. The repeated-header share is still recorded, but no file fails on it.
- **The composite score uses the corrected measurement**, so candidate selection can change for any PDF. That blast radius is measured over all bodies (see design D3), not assumed.
- **The gate records why each file passed or failed.** The text-defect rate and the structural split rate are recorded separately in each file's `table_structure` score, so reviewers can find files with poor text.
- **The thresholds themselves do not change** (width 0.92, fragment 0.08, split 0.02).

**Out of scope, recorded as follow-ups** (ranked by impact, measured on the same outputs):

1. **Column mis-mapping publishes wrong values.** In bodies 1295, 1207 and 1122, requester_type holds statuses (`Granted`, `Part Grant`, `Refuse`) and decision_status holds requesters (`Journalist`, `Client`). StatusValueIsDate is 467, of which 1295 has 242 and 1864 has 114.
2. **Fragment junk in files that pass:** 3,115 records with no reference and no dates, concentrated in 1486, 1655, 1235 and 1390.
3. **RTE (1655) cell text:** trailing-period vocabulary (`Journalist.`, `Member of the public.`, about 950 `UnrecognizedRequesterType`) and glyph-split cells (`J ournalist`, `R S efused. ection`). These need cell repair in `normalize_disclosure_cells`, which is also where run-together repair (`informaQon`) belongs.
4. **Zero-record bodies 1496 (F) and 1758 (G):** a missing header and a two-row header. Fix with code or overrides.
5. **Files gated on width alone** (33 files, 35% junk) stay gated. Rescue them per file through `column_mappings.json` overrides.

## Capabilities

### New Capabilities
- `foi-table-structure-gate`: what makes the FOI pipeline accept or reject an extracted PDF table, which signals are structural and which are textual, and what a rejection records.

### Modified Capabilities
None. `foi-disclosures-dataset` covers storage and publishing, and this change does not touch them.

## Impact

- Code: `src/lib/table_structure.py` (split-pair rule, header-row removal, failed-check set, score fields); `pipelines/foi_pipeline/steps/assess_table_structure/process.py` (error context); tests under `pipelines/foi_pipeline/tests/` and `src/lib` tests.
- Selection: `transform_disclosure_files` candidate choice through the composite score. An all-bodies re-run is required (no downloads, no paid OCR, `extract_motions` not involved).
- Data: up to about 3,200 more data rows reach canonicalize; the record count is set by the all-bodies run and is not promised here. No published output changes until a separate release decision.
- Experiment: the gold-set confusion in `experiments/2026-11-14-pdf-extractor-bakeoff` must be re-measured. Precision (0.65 on a provisional 10-file set) will probably fall further, because the gate gets looser.
