# extract_disclosures_canonicalize_rows

Normalizes the `decision_status` field values in FOI disclosure records to a canonical set of seven status values.

## What it does

This step takes the flat FOI request records produced by `extract_disclosures_canonicalize` and normalizes the `decision_status` field value for each record. The normalization uses a synonym mapping defined in `status_map.py` with case-insensitive, whitespace-tolerant matching via `normalize_header()`.

For each record:
1. Extracts the raw `decision_status` value
2. If empty or null, passes the record through unchanged
3. Attempts to map the status to a canonical value using the synonym lookup
4. If recognized, updates `decision_status` to the canonical value
5. If unrecognized, logs an error to `errors.json` and passes the record through unchanged

The step supports `--public-body` scoping via Shape b (merge-back) pattern: it filters input to the target body, processes it, then merges the results back into existing output.

## Canonical Status Values

| Canonical Status | Description |
|---|---|
| `Granted` | Request approved in full |
| `Refused` | Request denied |
| `Part-Granted` | Request partially approved |
| `Withdrawn` | Request withdrawn by requester |
| `Handled outside of FOI` | Handled through other means |
| `Transferred` | Transferred to another body |
| `Deemed Refused` | Deemed refused (time limit expired) |

## Input

`extract_disclosures_canonicalize/output.json` — flat list of FOI request records with raw `decision_status` values

## Output

- `output.json` — `{ metadata, results: [...] }` — normalized records with canonical `decision_status` values
- `errors.json` — list of `UnrecognizedDecisionStatus` errors for unrecognized variants

### Output Metadata

The `output.json` metadata includes:
- `total_records_input`: Number of input records processed
- `total_records_output`: Number of output records (same as input, records are never dropped)
- `total_records_normalized`: Number of records with successfully normalized status
- `total_records_unrecognized`: Number of records with unrecognized status (written to errors.json)
- `canonical_status_distribution`: Count of each canonical status in output

## Notable files

- `status_map.py` — Defines `CANONICAL_STATUSES` and the synonym mapping dictionary, plus `canonicalize_status()` function
- `errors.json` — Records with unrecognized status values; review this file to expand the synonym mapping
- `pipeline-status.json` — Execution metadata (record count, completion timestamp)

## Expanding the Synonym Mapping

To add new status variants:

1. Run the step and examine `errors.json` for unrecognized values
2. Edit `status_map.py` and add the new variant to the appropriate canonical status list in `_STATUS_SYNONYMS`
3. Re-run the step to verify the error count decreases
4. Commit the updated mapping

Example addition:

```python
'Granted': [
    'Granted',
    'Grant',
    'GRANTED',
    'Grant - FOI Non Personal',
    'Access: Granted',
    'Access Granted',
    # Add new variant here:
    'Fully Granted',
],
```
