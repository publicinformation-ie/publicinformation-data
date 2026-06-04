# pdfplumber Parameter Sweep — 2026-06-04

**Hypothesis:** Tuning pdfplumber's table-detection parameters can reduce phantom null rows, improving `clean_extraction_rate` beyond the 35% baseline.

**Parameter grid:** 18 total — baseline (config 0: snap_y=3, snap=3, edge_min=3) + 17 param configs from snap_y_tolerance ∈ {3,6,10} × snap_tolerance ∈ {3,6} × edge_min_length ∈ {3,10,20} (excluding the (3,3,3) baseline).

**PDFs evaluated:** 721 (file_type=pdf, rows not None in eval fixture)

## Results

> Fill in after running `run.py`.

## Conclusion

> Fill in after running `run.py`.

A configuration is **actionable** if:
- `clean_extraction_rate` ≥ 0.40 (≥5pp improvement over 0.35 baseline), AND
- `regressions` = 0

If no configuration meets both criteria: pdfplumber settings are not the lever; the `normalize_header` downstream step is the appropriate long-term fix.

## Reproduce

```bash
cd foi_pipeline
uv run python experiments/2026-06-04-pdfplumber-param-sweep/run.py
```
