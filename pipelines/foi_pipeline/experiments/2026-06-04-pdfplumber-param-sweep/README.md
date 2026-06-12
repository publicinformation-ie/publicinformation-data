# pdfplumber Parameter Sweep — 2026-06-04

**Hypothesis:** Tuning pdfplumber's table-detection parameters can reduce phantom null rows, improving `clean_extraction_rate` beyond the 35% baseline.

**Parameter grid:** 18 total — baseline (config 0: snap_y=3, snap=3, edge_min=3) + 17 param configs from snap_y_tolerance ∈ {3,6,10} × snap_tolerance ∈ {3,6} × edge_min_length ∈ {3,10,20} (excluding the (3,3,3) baseline).

**PDFs evaluated:** 524 cached (of 721 total in eval fixture with non-null rows)

## Results

Ranked by `clean_extraction_rate` descending, `regressions` ascending. ★ = actionable (clean_rate ≥ 0.40 and regressions = 0).

```
cfg  snap_y  snap  edge_min  clean_rate  null_1st  null_col  newline  regress
---  ------  ----  --------  ----------  --------  --------  -------  -------
 15      10     6         3       0.500     0.319     0.183    0.324        1
 16      10     6        10       0.500     0.319     0.183    0.324        1
 17      10     6        20       0.500     0.319     0.162    0.311        6
 10       6     6        10       0.496     0.317     0.177    0.344        0  ★
  4       3     6        10       0.494     0.321     0.172    0.336        0  ★
  9       6     6         3       0.492     0.317     0.183    0.344        0  ★
 11       6     6        20       0.494     0.319     0.156    0.330        6
  3       3     6         3       0.490     0.319     0.177    0.338        0  ★
  5       3     6        20       0.492     0.323     0.158    0.330        6
 14      10     3        20       0.462     0.368     0.263    0.342        7
  8       6     3        20       0.448     0.368     0.288    0.366        7
 13      10     3        10       0.456     0.355     0.279    0.365        1
 12      10     3         3       0.456     0.355     0.279    0.365        1
  7       6     3        10       0.445     0.353     0.300    0.380        0  ★
  6       6     3         3       0.441     0.355     0.303    0.380        0  ★
  2       3     3        20       0.441     0.374     0.296    0.374        7
  1       3     3        10       0.431     0.359     0.307    0.378        0  ★
  0       3     3         3       0.427     0.359     0.311    0.380        0  ← baseline
```

### Key findings

- **`snap_tolerance` is the dominant parameter.** Jumping 3→6 adds ~6–7pp of `clean_extraction_rate` across all other settings. All other parameters are secondary.
- **`edge_min_length=20` reliably causes 6–7 regressions.** It prunes real table edges. Never use it.
- **`snap_y_tolerance=10` causes 1 regression** (see below). Stick to 3 or 6.
- **Best zero-regression config is config 4** (`snap_y=3, snap=6, edge_min=10`): lowest `null_column_rate` (0.172) and `newline_split_row_rate` (0.336) among zero-regression candidates.

### The config 15 / 16 regression

The one PDF that regresses at `snap_y=10`:

```
https://assets.gov.ie/static/documents/foi-disclosure-log-2016-64edfc30-e580-453e-9208-b4150c48200d.pdf
```

The PDF has a document title ("FOI DISCLOSURE LOG 2016") in a merged cell spanning the table width, immediately above the header row. At `snap_y=3`, pdfplumber sees the vertical gap and excludes the title row; at `snap_y=10`, it snaps the title into the table as row 0 with `None` in every other column, triggering `null_first_row`. Not fixable by parameter tuning — it's a structural PDF pattern (merged spanning title above table) that a tighter `snap_y` correctly excludes.

## Conclusion

**Hypothesis confirmed.** `snap_tolerance=6` is the lever. Multiple configurations are actionable.

**Adopted:** config 4 — `snap_y_tolerance=3, snap_tolerance=6, edge_min_length=10`

Applied to `_DEFAULT_PDF_TABLE_SETTINGS` in `steps/transform_disclosure_files/process.py`. This raises `clean_extraction_rate` from 0.427 → 0.494 (+6.7pp) with zero regressions.

**Ceiling at ~50%.** The remaining failures are dominated by:
- `newline_split_row` (34% of PDFs): pdfplumber physically splits wrapped cell text into separate rows — not addressable by extraction parameters
- `null_column` (17%): residual phantom columns
- `null_first_row` (32%): title/caption rows or merged headers — partially handled downstream by `extract_disclosures_detect_header_row`

`newline_split_row` barely moved with parameter tuning (0.38 → 0.336), confirming that the next lever is post-extraction structural fixes in `normalize_disclosure_cells`. Both `_merge_continuation_rows` and `_prune_null_columns` were implemented there (2026-06-04).

## Reproduce

```bash
cd foi_pipeline
uv run python experiments/2026-06-04-pdfplumber-param-sweep/run.py
```
