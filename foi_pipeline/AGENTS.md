# FOI Pipeline - Agent Documentation

This document explains how the FOI (Freedom of Information) pipeline processes public body data for the publicinformation.ie project.

## Overview

The pipeline is a series of Python steps that:
1. Discover Irish public bodies subject to FOI
2. Validate and enrich their contact information
3. Extract disclosure data
4. Consolidate all results into a final status output

## Pipeline Architecture

### Pipeline Steps (in order)

1. **find_public_bodies** - Scrapes the list of Irish public bodies from foi.gov.ie
2. **resolve_website_urls** - Second-pass resolution of gov.ie stub URLs
3. **validate_websites** - Checks if each public body's website is reachable
4. **find_foi_pages** - Discovers FOI-specific pages on each website
5. **check_foi_pages** - Validates the FOI pages are accessible
6. **get_foi_emails** - Extracts FOI email addresses from websites
7. **find_disclosure_pages** - Locates disclosure/log pages
8. **find_disclosure_files** - Finds disclosure documents (PDFs, CSVs, etc.)
9. **transform_disclosure_files** - Processes disclosure files into structured data
10. **extract_disclosures_detect_header_row** - Detects header row in spreadsheets
11. **extract_disclosures_canonicalize** - Maps raw columns to canonical FOI record fields
12. **export_status** - Fan-in merges all step outputs into a consolidated status report
13. **generate_topics** - Groups FOI records into keyword-defined topics
14. **db_upload** - **Final step** - Populates the libSQL database from pipeline output

### Data Flow

```
find_public_bodies/output.json (base data)
    |
    v
validate_websites/output.json (website status)
    |
    v
find_foi_pages/output.json (FOI page URLs)
    |
    v
check_foi_pages/output.json (FOI page status)
    |
    v
get_foi_emails/output.json (email addresses)
    |
    v
find_disclosure_pages/output.json (disclosure page URLs)
    |
    v
find_disclosure_files/output.json (disclosure file counts)
    |
    v
transform_disclosure_files/output.json (processed files)
    |
    v
extract_disclosures/output.json (extracted records)
    |
    v
export_status/output.json (CONSOLIDATED STATUS - used by website)
    |
    v
generate_topics/output.json (topic groups + matched disclosures)
    |
    v
db_upload → libSQL database (public_bodies, disclosure_files, foi_disclosures, topics, …)
```

## export_status Step (Key Step for Website)

The `export_status` step is the **final aggregator** that merges data from all previous steps into a single, comprehensive output file that the publicinfo-prototype website consumes.

### Input
- Reads `pipeline.json` to get the list of all steps
- Uses `find_public_bodies/output.json` as the base
- Merges in data from all other step outputs that exist

### Output Structure

The `export_status/output.json` contains:

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

### Status Field Values

Each status field can have one of three values:
- **"success"** - The step completed successfully for this body
- **"failed"** - The step was attempted but failed for this body
- **"not_attempted"** - The step was not run or this body was not in its results

### Merging Logic

The export_status step uses a **fan-in merge** approach:

1. Starts with a deep copy of `find_public_bodies/output.json`
2. For each subsequent step in pipeline.json:
   - If step has a merger function (defined in STEP_MERGERS), apply it
   - If step output.json exists, load and merge it
   - If step output.json doesn't exist, skip it (fields remain "not_attempted")
3. Adds `short_name` to each body if not already present
4. Writes consolidated output to `export_status/output.json`

### Step Mergers

Each merger function updates the status fields for public bodies:

| Step | Merger Function | Updates |
|------|----------------|--------|
| validate_websites | merge_validate_websites | status.website_url.status |
| find_foi_pages | merge_find_foi_pages | status.foi_page.url, status.foi_page.status |
| check_foi_pages | merge_check_foi_pages | status.foi_page.status (refines find_foi_pages) |
| get_foi_emails | merge_get_foi_emails | status.foi_email.email, status.foi_email.status |
| find_disclosure_pages | merge_find_disclosure_pages | status.disclosures_page.url, status.disclosures_page.status |
| find_disclosure_files | merge_find_disclosure_files | status.disclosure_files.total/valid/failed/status |
| transform_disclosure_files | merge_transform_disclosure_files | status.disclosure_files.valid (overrides find count with actual transform count) |

Steps without mergers (e.g. extract_disclosures_detect_header_row) are skipped during merge.

## Database (db_upload step)

The final `db_upload` step writes pipeline data to a libSQL database. The target is controlled by two environment variables (set in `.env.admin`):

| Variable | Local dev | Production |
|---|---|---|
| `DATABASE_URL` | `file:./local.db` | Bunny dashboard connection URL (`https://…`) |
| `DATABASE_AUTH_TOKEN` | *(leave empty)* | Bunny auth token |

`scripts/db_client.py` abstracts sqlite3 (local) and libSQL HTTP v2 (remote) behind a single `DbClient` interface. The canonical schema lives at `schema.sql` in the repo root.

To populate a local SQLite database from existing pipeline output:

```bash
DATABASE_URL=file:./local.db python orchestrator.py foi_pipeline/ --from export_status
```

## Python Environment

The project uses `uv` for Python dependency management.

### Running Tests

```bash
cd foi_pipeline
uv run pytest tests/ -q
```

## Running the Pipeline

### Full Pipeline

```bash
source ../scripts/.venv/bin/activate
cd foi_pipeline
python orchestrator.py --force
```

This runs all steps in order from `pipeline.json`.

### From a Specific Step

```bash
cd foi_pipeline
python orchestrator.py --from export_status --force
```

This skips all steps before `export_status` and starts from there.

### Single Step

```bash
cd foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/extract_disclosures/output.json \
  --output steps/export_status/output.json \
  --force
```

Note: The `--input` argument is required by the CLI but ignored by export_status. It uses the pipeline.json and step directory structure instead.

## Pipeline Output Locations

Each step writes its output to:
- `<step_directory>/output.json` - Main output data
- `<step_directory>/status.json` - Step execution status
- `<step_directory>/errors.json` - Any errors encountered
- `<step_directory>/pipeline-status.json` - Copy of output (for debugging)

## Troubleshooting

### export_status/output.json not generated

If the website's data-status page is empty:

1. Check if export_status/output.json exists:
   ```bash
   ls -la foi_pipeline/steps/export_status/output.json
   ```

2. If missing, run the export_status step manually:
   ```bash
   cd foi_pipeline
   PYTHONPATH=. python steps/export_status/process.py \
     --input steps/find_public_bodies/output.json \
     --output steps/export_status/output.json \
     --force
   ```

3. If that fails, check:
   - Does find_public_bodies/output.json exist?
   - Does pipeline.json exist in the foi_pipeline directory?
   - Are there any Python errors?

### Data not appearing on website

The website uses a prebuild script that copies export_status/output.json. If data is missing:

1. The prebuild script has a fallback chain:
   - First tries: `../foi_pipeline/steps/export_status/output.json`
   - Falls back to: `../foi_pipeline/steps/find_public_bodies/output.json`
   - Final fallback: Creates empty JSON `{metadata: {}, public_bodies: []}`

2. Check which file is being used:
   ```bash
   python3 -c "import json; data=json.load(open('publicinfo-prototype/src/data/pipeline-status.json')); print('Source step:', data['metadata'].get('step'))"
   ```

3. If showing "find_public_bodies", the export_status step hasn't been run yet.

### short_name missing

If public bodies show without short names (e.g., "Department of Health ()"):

1. The export_status step generates short_name automatically if missing
2. If using find_public_bodies directly (fallback), short_name won't be present
3. The website handles missing short_name gracefully by omitting the span

To ensure short_name is present, run the export_status step.

## Data Model Evolution

The data model has evolved over time:

- **v1**: find_public_bodies included `short_name` field
- **v2**: short_name was removed from find_public_bodies (commit 3dc28a8)
- **v3**: short_name generation moved to export_status step (this fix)

The current approach centralizes short_name generation in the final export step, ensuring all public bodies have this field regardless of which pipeline steps have been run.

## Override System

Some pipeline steps produce incorrect results that are impractical to fix via automated scraping alone. The override system lets you inject manually-authored records that are **never overwritten** by automated re-runs.

### How It Works

Each step directory may contain an optional `override.json` file. When `IncrementalWriter` is constructed, it reads this file (if present) and pre-loads the records into `processed_keys` before `process()` runs. Because `process()` skips any body whose ID is already in `processed_keys`, no HTTP calls are made for overridden bodies. Manual data is preserved even on `--force` runs.

### Override File Format

`override.json` is an array of complete result records conforming to the step's `output_schema.json`. Two fields distinguish override records from automated results:

- `"source_method": "manual"` — replaces `"crawl"` or `"serper"` (only for steps that have `source_method`)
- `"overridden": true` — explicit marker for filtering and auditing

Example for `find_foi_pages`:

```json
[
  {
    "public_body_id": 1025,
    "name": "Capital Works Management Framework",
    "official_website_url": "https://constructionprocurement.gov.ie/",
    "foi_page_url": "https://constructionprocurement.gov.ie/freedom-of-information/",
    "source_method": "manual",
    "overridden": true
  }
]
```

### Flag Interaction Matrix

| Scenario | Behaviour |
|---|---|
| Normal run, no override.json | No change from current behaviour |
| Normal run, override.json present | Override bodies pre-loaded; skipped by `process()` |
| `--force`, override.json present | Automated results reprocessed; override bodies still skipped |
| `--retry`, override.json present | Only errored bodies retried; override bodies absent from `errors.json` so never retried |
| Override body also in errors.json | Body skipped in processing; error record left as-is |
| Duplicate `public_body_id` in override.json | First record wins |

### Workflow

1. Identify a body whose automated result is wrong (e.g., FOI page URL not found or incorrect)
2. Create `foi_pipeline/steps/<step_name>/override.json` if it does not exist
3. Add a complete result record with `"source_method": "manual"` and `"overridden": true`
4. Commit `override.json` to git — this is the source of truth for manually-curated data
5. Re-run the step normally; the override body will be skipped by automation

### Validation

Records in `override.json` are validated against `output_schema.json` at startup. An invalid record causes an immediate `ValueError` identifying the offending `public_body_id`. Fix the record and re-run. Steps without `output_schema.json` (e.g. `extract_disclosures`) skip validation.

### Uniqueness Pass Interaction (find_foi_pages only)

`find_foi_pages` runs a post-process uniqueness check that removes records sharing a `foi_page_url`. Override records participate in this pass. If an override record shares a `foi_page_url` with an automated result, the automated result is dropped — manual truth wins.
