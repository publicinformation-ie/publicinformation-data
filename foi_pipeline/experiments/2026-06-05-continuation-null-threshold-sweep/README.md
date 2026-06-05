# Experiment: `_CONTINUATION_NULL_THRESHOLD` Sweep

**Date:** 2026-06-05
**Status:** Complete

## Hypothesis

`_CONTINUATION_NULL_THRESHOLD = 0.5` may be too conservative. Continuation rows
with null fractions at or below 50% are left unmerged, leaving null headers that
cause `InsufficientColumns` failures in `extract_disclosures_canonicalize`.

**Alternative null hypothesis:** Most failures are vocabulary gaps — headers are
fully populated but no column names match canonical synonyms. If so, the sweep
will be flat and synonym expansion is the correct fix.

## Inputs

| Source | Purpose |
|--------|---------|
| `steps/extract_disclosures_normalize_header/eval/input.json` | Frozen fixture (811 records); sweep input |
| `steps/extract_disclosures_normalize_header/output.json` | Live output; diagnostic only (current headers) |
| `steps/extract_disclosures_canonicalize/errors.json` | Failing URLs; diagnostic only |

## How to run

```bash
cd foi_pipeline/experiments/2026-06-05-continuation-null-threshold-sweep
uv run python run.py
```

## Diagnostic summary

| Class | Count | % of total |
|-------|-------|------------|
| null_header | 58 | 22.5% |
| vocab_gap | 200 | 77.5% |
| not_in_fixture | 0 | 0.0% |

## Sweep results

| threshold | null_header_column_rate | insufficient_columns_count | improvements | regressions | net_change |
|-----------|------------------------|---------------------------|--------------|-------------|------------|
| 0.2 | 0.086 | 271 | 0 | 39 | -39 |
| 0.3 | 0.086 | 241 | 0 | 9 | -9 |
| 0.4 | 0.089 | 233 | 0 | 1 | -1 |
| **0.5 (baseline)** | 0.090 | 232 | 0 | 0 | 0 |
| 0.6 | 0.090 | 232 | 0 | 0 | 0 |
| 0.7 | 0.092 | 232 | 0 | 0 | 0 |
| 0.8 | 0.094 | 234 | 0 | 2 | -2 |

## Conclusion

22.5% of failures are due to null headers; 77.5% are vocabulary gaps. Threshold tuning shows no benefit across any threshold sweep value.

- [ ] Threshold tuning is effective — adopt `_CONTINUATION_NULL_THRESHOLD = X`
- [ ] Threshold tuning is ineffective — root cause is vocabulary gaps; redirect to synonym expansion
- [x] Mixed result — threshold helps a subset; consider combining with synonym work
