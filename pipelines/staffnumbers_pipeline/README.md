# staffnumbers_pipeline

Adds full-time-equivalent staff numbers to the public bodies dataset, from the Department of Public Expenditure's public service numbers CSV. Publishes `staff-numbers` via `scripts/transform_staff_numbers.py`.

| # | Step | What it does |
|---:|---|---|
| 1 | `fetch_staff_numbers` | Downloads the CSV (or reads `--source` / `$STAFF_NUMBERS_SOURCE_FILE`), keeps the latest quarter, derives `source_name` (`Level_6`, else `Level_5`), parses FTE (`"3,960.56"`) |
| 2 | `match_public_bodies` | Deterministic matching only: identical normalised name, or the local-authority rewrite. Near-misses and suggestions go to `match_log.json` |
| 3 | `apply_overrides` | Applies `override.json`; keeps every row; lists unreviewed unmatched rows in `errors.json` |

```bash
uv run python pipelines/staffnumbers_pipeline/process.py pipelines/staffnumbers_pipeline --force --stop-on-error
uv run python scripts/transform_staff_numbers.py
```

## Reviewing matches

`errors.json` (step 3) lists each unmatched row nobody has decided on. For each, add its `source_key` to `steps/apply_overrides/override.json` with either the canonical `public_body_id`, or `null` to record "reviewed: no single canonical body" (an aggregate or sub-unit). `match_log.json` (step 2) shows the closest canonical names. Do not accept a near-miss without checking it is the same body: a renamed or successor body (e.g. Policing Authority vs Policing and Community Safety Authority) is a judgement call.

An override that targets an unknown body, names a `source_key` not in the source, or duplicates a deterministic match fails the step. Overrides are keyed on `Level_4 | Level_5 | Level_6`, so a source relabelling shows up as a stale key rather than a silent mismatch.

The paid-step rules do not apply: no step here spends money. The PER site's certificate chain may not verify in some sandboxes; supply a downloaded copy via `STAFF_NUMBERS_SOURCE_FILE` rather than disabling verification.
