# Tasks

## 1. Preserve the comparison point

- [x] 1.1 Copy `output.json`, `errors.json`, `dirty_ids.json` and `pipeline-status.json` for every step from `transform_disclosure_files` to `extract_disclosures_canonicalize_rows` into `/Volumes/ext/dev/publicinformation/foi-after-pr26-snapshot-2026-11-14/<step>/`. Verify: the snapshot's canonicalize_rows `results` length is 56,390 and assess `errors.json` has 163 entries.

## 2. Scorer: separate text from structure (TDD)

- [x] 2.1 Add failing tests in the `table_structure` tests:
  - (a) `Journalist` | `all records…` and `Client` | `social housing` pairs do not count;
  - (b) `S` | `ummary` counts;
  - (c) a sound table whose cells hold run-together tokens above 2% passes `failed_checks`;
  - (d) a table repeating its header on every page passes and reports `repeated_header_share` > 0;
  - (e) a width-broken table still fails `width_uniformity`.

  Use rows taken from real gated files (one courts.ie split-word file, one 1207 or 1122 repeated-header file) as fixtures. Verify: the new tests fail on HEAD.
- [x] 2.2 Add `run_together_rate` and `cross_cell_split_rate` to `StructureScore`, keep `split_word_rate` as the structural alias, and implement the D2 stub rule. Verify: tests 2.1 a–c pass.
- [x] 2.3 Remove header-equal rows in `_data_rows`, record `repeated_header_share` before removal, and drop it from `failed_checks` (D4). Verify: test 2.1 d passes.
- [x] 2.4 Keep the composite formula and feed it the corrected cross-cell count (D3). Verify: the full test suite passes (`uv run pytest`) and pyright shows no new errors in the touched files.
- [x] 2.5 Update the module docstring and `pipelines/foi_pipeline/steps/assess_table_structure` README/AGENTS notes, so they say which checks gate and which only record. Verify: the docs name both new fields.

## 3. Offline pre-check (no runner)

- [x] 3.1 Re-score `transform_disclosure_files/output.json` rows with the new scorer in a scratch script. Report:
  - how many of the 163 gated files now pass, by original failed-check combination;
  - how many currently passing PDFs would now fail (expected: 0; the offline simulation predicts 71 of 84 recovered, 3,193 rows);
  - data rows recovered.

  Verify: the numbers are recorded in a new experiment results file `results/gate_structure_not_text_precheck.md`.

## 4. All-bodies re-run and comparison

- [x] 4.1 Reset `errors.json` to `[]` for every step in range. Run `transform_disclosure_files --force --processes 8` directly, then the runner `--from assess_table_structure --to extract_disclosures_canonicalize_rows --force --stop-on-error`. No downloads, no `--allow-paid-ocr`, nothing past canonicalize_rows. Verify: exit 0 and fresh mtimes on every step output in range.
- [x] 4.2 Run `before_after.py --bodies <union of ids>` against both the 1.1 snapshot and the Nov-12 baseline, and list every file whose `pdf_extractor` changed. Verify: a results file records total records, bodies below baseline, zero-record bodies, `TableStructureUnreliable` count and the selection-change list.
- [x] 4.3 Acceptance checks, recorded in the same results file:
  - (a) no body falls more than 5% against the 1.1 snapshot without a written explanation;
  - (b) zero records from un-gated repeated-header files carry a field value that `canonicalize_headers` maps to a canonical field;
  - (c) the junk share (no reference, no dates) of records from newly accepted files is ≤ 5%;
  - (d) all 33 width-only files remain rejected;
  - (e) gold-set confusion is re-measured and reported (not a pass bar).

  Verify: each check is marked PASS/FAIL with numbers.

## 5. Hand-off

- [x] 5.1 Write the follow-ups from proposal.md (column mis-mapping in 1295/1207/1122, fragment junk in 1486/1655/1235/1390, cell repair incl. RTE vocabulary and run-together text, 1496/1758, width-only overrides) into the experiment results file, with current counts after the re-run. Verify: the file lists each one with a number.

## Workflow follow-up

- Do not commit regenerated `output.json` files. Release, dedup, export and `db_upload` remain a separate decision for the user.
- Archive with `/opsx:archive` after merge.
