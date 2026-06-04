# FOI Pipeline — Experiments

Experiments live in dated subdirectories (`YYYY-MM-DD-<slug>/`). Each has its own `README.md` with hypothesis, results, and conclusion.

## Index

| Date | Experiment | Outcome |
|------|-----------|---------|
| 2026-06-04 | [pdfplumber-param-sweep](2026-06-04-pdfplumber-param-sweep/) | `snap_tolerance=6` adds +6.7pp clean rate; adopted as config 4 |

## Before running an experiment

**`transform_disclosure_files` is slow.** It takes ~4.5 minutes to process 500 files. Never re-run the full step to test extraction changes — instead, operate directly on cached bytes as the pdfplumber sweep does. The cache lives at `steps/transform_disclosure_files/cache/` (URL → SHA256).

**Use the eval fixture, not live output.** `steps/transform_disclosure_files/eval/input.json` is a frozen snapshot of step output used for reproducible scoring. Refresh it with:
```bash
uv run python steps/transform_disclosure_files/eval/evaluate.py \
  --refresh-fixture steps/transform_disclosure_files/output.json
```

**Score against the eval functions, not raw output.** `steps/transform_disclosure_files/eval/evaluate.py` exports `has_null_first_row`, `has_null_column`, `has_newline_split_row`. These are the canonical flag definitions — use them in experiment scoring scripts to stay aligned with the eval framework.

**Track regressions explicitly.** Record the set of baseline-clean URLs and intersect with each config's flagged set. A config that improves the aggregate metric while regressing 1–2 specific PDFs is usually not worth adopting.

## What the eval flags mean

| Flag | Definition | Root cause |
|------|-----------|------------|
| `null_first_row` | Any `None` in `rows[0]` | Title/caption row pulled into table; merged header cell; detection starting on wrong row |
| `null_column` | Any column where every row is `None` | Phantom vertical line detected as a column edge |
| `newline_split_row` | Non-header row with exactly 1 non-`None` cell across ≥3 columns | pdfplumber splits wrapped text into a separate physical row |

A PDF can trigger multiple flags. In production (post config-4 adoption), the flag distribution across ~469 flagged PDFs is:

| Flags | Count |
|-------|-------|
| `newline_split_row + null_first_row` | 161 |
| `newline_split_row + null_column` | 98 |
| `newline_split_row + null_column + null_first_row` | 69 |
| `null_column` only | 63 |
| `null_first_row` only | 59 |
| `null_column + null_first_row` | 10 |
| `newline_split_row` only | 9 |

## Learnings

### pdfplumber parameters (2026-06-04)

- `snap_tolerance` is the dominant lever for column detection quality. The default (3) is too conservative; 6 is better.
- `edge_min_length=20` is dangerous — it prunes real table edges and causes consistent regressions. Stay at 10 or below.
- `snap_y_tolerance` has diminishing returns above 6, and ≥10 can merge document title rows into tables (see the 2016 gov.ie disclosure log regression).
- The `newline_split_row` flag barely responds to extraction parameter tuning — it is a structural PDF rendering issue (text reflow), not an edge detection issue. Address it downstream.

### Downstream fixes are often better than extraction tuning

pdfplumber parameter sweeps hit a ceiling because many PDF quality issues are structural, not edge-detection failures. Post-extraction normalization in `normalize_disclosure_cells` is the right layer for:
- Merging continuation rows (`_merge_continuation_rows`, implemented 2026-06-04)
- Pruning all-None columns (`_prune_null_columns`, implemented 2026-06-04)

Header detection issues (`null_first_row`) are better addressed in `extract_disclosures_detect_header_row`.

## Adding a new experiment

1. Create `experiments/YYYY-MM-DD-<slug>/`
2. Add `README.md` with hypothesis, parameter grid, actionability criteria, and reproduce instructions
3. Write a `run.py` that reads from the eval fixture and cached bytes, not live pipeline output
4. After running, fill in Results and Conclusion sections
5. Add a row to the index table above
