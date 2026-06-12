# find_public_bodies_subject_to_foi

**Step Number:** 2 (after `find_public_bodies`, before `resolve_website_urls`)

## What This Step Does

Filters the master list of public bodies to only those that are subject to FOI legislation. Bodies with an `exclusion_reason` field set are excluded; all others pass through unchanged.

## Input

**File:** `steps/find_public_bodies/output.json`

**Structure:**
```json
{
  "metadata": {...},
  "public_bodies": [
    {
      "public_body_id": 123,
      "name": "Body Name",
      "exclusion_reason": "not_subject_to_foi",
      ...
    }
  ]
}
```

## Output

**File:** `steps/find_public_bodies_subject_to_foi/output.json`

Same structure as input, with bodies that have any `exclusion_reason` removed. All downstream steps operate on this filtered set.

## Notable Files

| File | Purpose |
|------|---------|
| `process.py` | Main processing script |
| `output.json` | Filtered list of FOI-subject public bodies |
| `pipeline-status.json` | Execution metadata |

## Running This Step

From the `foi_pipeline` directory:

```bash
# Run as part of full pipeline
python process.py --force

# Run this step only
PYTHONPATH=. python steps/find_public_bodies_subject_to_foi/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/find_public_bodies_subject_to_foi/output.json \
  --force
```

## Scoped Run Behaviour

When called with `--public-body <ID>` without `--force`, this step confirms the body is in the filtered output and exits 0 without modifying the file. If the body has an `exclusion_reason` (i.e., it is not subject to FOI), the step exits with an error.
