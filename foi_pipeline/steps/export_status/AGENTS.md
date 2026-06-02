# export_status - Agent Documentation

This step is the **final aggregator** that merges data from all previous pipeline steps into a single, comprehensive output file consumed by the publicinformation-web website.

## Input

- Reads `../pipeline.json` to get the list of all steps
- Uses `../find_public_bodies/output.json` as the base record set
- Merges in data from all other step outputs that exist in the `steps/` directory

## Output Structure

The `output.json` file contains:

```json
{
  "metadata": {
    "step": "export_status",
    "completed_at": "2026-05-05T20:00:00.000000+00:00"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Agriculture, Food and the Marine",
      "short_name": "DAFM",
      "official_website_url": "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
      "status": {
        "website_url": {
          "url": "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
          "status": "success" | "failed" | "not_attempted"
        },
        "foi_page": {
          "url": "https://.../foi" | null,
          "status": "success" | "failed" | "not_attempted"
        },
        "foi_email": {
          "email": "foi@dept.gov.ie" | null,
          "status": "success" | "failed" | "not_attempted"
        },
        "disclosures_page": {
          "url": "https://.../disclosures" | null,
          "status": "success" | "failed" | "not_attempted"
        },
        "disclosure_files": {
          "total": 5,
          "valid": 5,
          "failed": 0,
          "status": "success" | "failed" | "not_attempted"
        },
        "foi_requests": {
          "valid": 0,
          "errors": 0,
          "status": "not_attempted"
        }
      }
    }
  ]
}
```

## Status Field Values

Each status field uses a consistent 3-state system:

- **"success"** - The step completed successfully for this body
- **"failed"** - The step was attempted but failed for this body
- **"not_attempted"** - The step was not run or this body was not in its results

## Public Output Files

In addition to `output.json`, this step writes three public JSON files to `../../public/`:

| File | Contents |
|------|----------|
| `public/pipeline-data.json` | Full merged status for every public body |
| `public/disclosure-files.json` | Flat list of all discovered disclosure log file URLs |
| `public/foi-disclosures.json` | All canonicalized FOI request records |

## Merging Logic

Uses a **fan-in merge** approach:

1. Starts with a deep copy of `find_public_bodies/output.json`
2. For each subsequent step in pipeline.json:
   - If step has a merger function (defined in STEP_MERGERS in process.py), apply it
   - If step output.json exists, load and merge it
   - If step output.json doesn't exist, skip it (fields remain "not_attempted")
3. Adds `short_name` to each body if not already present
4. Writes consolidated output to `export_status/output.json`

## Step Mergers

Each merger function updates specific status fields for public bodies:

| Step | Merger Function | Updates |
|------|----------------|--------|
| validate_websites | merge_validate_websites | status.website_url.status |
| find_foi_pages | merge_find_foi_pages | status.foi_page.url, status.foi_page.status |
| check_foi_pages | merge_check_foi_pages | status.foi_page.status (refines find_foi_pages) |
| get_foi_emails | merge_get_foi_emails | status.foi_email.email, status.foi_email.status |
| find_disclosure_pages | merge_find_disclosure_pages | status.disclosures_page.url, status.disclosures_page.status |
| find_disclosure_files | merge_find_disclosure_files | status.disclosure_files.total/valid/failed/status |
| transform_disclosure_files | merge_transform_disclosure_files | status.disclosure_files.valid (overrides find count with actual transform count) |

> **Note:** Steps without mergers (e.g., `extract_disclosures_detect_header_row`) are skipped during the merge process.

## Running This Step

```bash
# From the foi_pipeline directory
cd ..
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/extract_disclosures_canonicalize/output.json \
  --output steps/export_status/output.json \
  --force
```

The `--input` argument is required by the CLI but **ignored** by export_status. It uses `pipeline.json` and the step directory structure instead.
