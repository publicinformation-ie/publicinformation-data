# find_public_bodies_subject_to_foi

**Step Number:** 2 (after `find_public_bodies`, before `resolve_website_urls`)

## What This Step Does

Filters the master list of public bodies to those **subject to FOI**, which
determines the canonical body set for the whole FOI pipeline (`export_status`
merges from this step's output).

The inclusion set is resolved from two sources:

1. **foi.gov.ie's official directory** (`foi.gov.ie/all-foi-bodies/`) via
   `foigovie_pipeline/steps/apply_overrides/output.json`. Several foi.gov.ie
   entries can resolve to one canonical body (e.g. HSE regions), hence a set.
2. **Curated additions** (`inclusion_overrides.json`) — bodies that are subject
   to FOI but that the directory does not list. The directory is the primary
   source, not an exhaustive one.

The step is fatal if the foi.gov.ie source is missing or empty, if a curated
addition names a body that does not exist in `find_public_bodies/output.json`,
or if a curated addition has no `reason` — any of those would silently distort
the FOI pipeline rather than fail it.

There is no `exclusion_reason` mechanism: exclusion is simply "not in the
resolved inclusion set".

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

Same structure as input, with bodies outside the resolved inclusion set
removed. All downstream steps operate on this filtered set.

## Notable Files

| File | Purpose |
|------|---------|
| `process.py` | Main processing script |
| `output.json` | Filtered list of FOI-subject public bodies |
| `pipeline-status.json` | Execution metadata |
| `inclusions.json` | **Generated.** The resolved inclusion set this run used, rewritten every run. `src/lib/publish_public_bodies.py` reads it for the published `foi_subject` column, so the catalog cannot drift from the set the pipeline actually crawled. Do not hand-edit. |
| `inclusion_overrides.json` | **Hand-curated, committed.** Bodies subject to FOI that foi.gov.ie's directory omits. Each entry needs `public_body_id`, `name` and a `reason`. Remove an entry once foi.gov.ie lists the body, or when a reviewer confirms it is no longer subject to FOI. |

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

When called with `--public-body <ID>` without `--force`, this step confirms the body is in the filtered output and exits 0 without modifying the file. If the body is not in the inclusion set (i.e. it is not subject to FOI), the step exits with an error.
