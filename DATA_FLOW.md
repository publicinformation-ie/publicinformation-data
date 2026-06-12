# Data Flow Documentation - PublicInformation.ie

This document provides an overview of how data flows from the FOI pipeline to the publicinformation-web website. For detailed information, see the specialized documentation files.

## Quick Reference

| Document | Purpose | Location |
|----------|---------|----------|
| **AGENTS.md** (Pipeline) | How data is produced by the FOI pipeline | `pipelines/foi_pipeline/AGENTS.md` |
| **DATA_CONSUMPTION.md** (Website) | How data is consumed by the website | `../publicinformation-web/DATA_CONSUMPTION.md` |
| **This File** | Overview of the complete data flow | `DATA_FLOW.md` |

## End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FOI Pipeline                                  │
│  (Python-based data extraction and processing)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. find_public_bodies       2. validate_websites                  │
│     ├── output.json            ├── output.json                       │
│     └── status.json            └── status.json                      │
│                                   ...                                 │
│  9. extract_disclosures       10. export_status ✨                 │
│     ├── output.json            ├── output.json (CONSOLIDATED)       │
│     └── status.json            └── status.json                      │
│                                                                      │
└──────────────────┬────────────────────────────────────────────────┘
                   │
                   │ copies
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Prebuild Script (package.json)                     │
│                                                                      │
│  Fallback Chain:                                                    │
│  1. export_status/output.json ────► pipeline-status.json             │
│  2. find_public_bodies/output.json ─► pipeline-status.json           │
│  3. Empty JSON ───────────────────► pipeline-status.json             │
│                                                                      │
└──────────────────┬────────────────────────────────────────────────┘
                   │
                   │ imports
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   PublicInfo Prototype Website                        │
│  (Astro-based static site generator)                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  src/data/pipeline-status.json (consumed at build time)              │
│                       │                                             │
│                       ▼                                             │
│  src/pages/data-status.astro                                        │
│     ├── Imports JSON data                                           │
│     ├── Renders status table                                        │
│     └── Outputs: dist/data-status/index.html                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### Pipeline Steps

The step sequence is defined in [`pipelines/foi_pipeline/pipeline.json`](pipelines/foi_pipeline/pipeline.json) (authoritative). Current steps:

1. **find_public_bodies** - Base data (scrapes foi.gov.ie)
2. **find_public_bodies_subject_to_foi** - Filters to bodies subject to FOI legislation
3. **resolve_website_urls** - Second-pass URL resolution
4. **validate_websites** - Checks website reachability
5. **find_foi_pages** - Discovers FOI pages
6. **find_foi_pages_search** - Apify batch search for bodies where crawl failed
7. **check_foi_pages** - Validates FOI pages
8. **get_foi_emails** - Extracts FOI email addresses
9. **find_disclosure_pages** - Locates disclosure pages
10. **find_disclosure_files** - Finds disclosure documents
11. **transform_disclosure_files** - Processes files
12. **normalize_disclosure_cells** - Normalizes string cell values
13. **extract_disclosures_detect_header_row** - Detects header row
14. **extract_disclosures_normalize_header** - Repairs null cells in header rows
15. **extract_disclosures_normalize_rows** - Normalizes date values to ISO 8601
16. **extract_disclosures_canonicalize** - Extracts canonical FOI records
17. **extract_disclosures_canonicalize_rows** - Normalizes decision_status values
18. **extract_disclosures_deduplicate** - Removes duplicate FOI records
19. **export_status** - Fan-in merge (status consolidator for the website)
20. **generate_topics** - Groups records into keyword topics
21. **db_upload** - Populates the libSQL database

Each step reads from the previous step's output and adds its own data.

### Status Field Values

All status fields use a consistent 3-state system:

| Value | Unicode | Color | Meaning |
|-------|---------|-------|---------|
| `"success"` | ✓ | Green | Operation completed successfully |
| `"failed"` | ✗ | Red | Operation attempted but failed |
| `"not_attempted"` | — | Grey | Operation not run or body not in results |

### Data Structure

The final `export_status/output.json` contains:

```json
{
  "metadata": {
    "step": "export_status",
    "completed_at": "2026-05-05T20:00:00+00:00"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Agriculture, Food and the Marine",
      "short_name": "DAFM",
      "official_website_url": "https://www.gov.ie/...",
      "status": {
        "website_url": {"url": "...", "status": "success"},
        "foi_page": {"url": "...", "status": "success"},
        "foi_email": {"email": "...", "status": "not_attempted"},
        "disclosures_page": {"url": null, "status": "not_attempted"},
        "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "not_attempted"},
        "foi_requests": {"valid": 0, "errors": 0, "status": "not_attempted"}
      }
    }
  ]
}
```

## Common Issues & Fixes

### Issue: Data-status page is empty

**Root Cause**: `export_status/output.json` doesn't exist, prebuild creates empty file.

**Fix**:
```bash
cd pipelines/foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force
```

Then rebuild the website:
```bash
cd ../publicinformation-web
npm run build
```

### Issue: Data exists but no short names

**Root Cause**: Using `find_public_bodies/output.json` fallback which lacks `short_name`.

**Fix**: Run export_status step (which generates short_name) or update the prebuild to use export_status.

### Issue: All status show as "—" (not_attempted)

**Root Cause**: Using `find_public_bodies/output.json` which only has base data.

**Fix**: Run the full pipeline to generate all step outputs, then run export_status to merge them.

## Running the Complete Workflow

### Full Pipeline + Website Build

```bash
# 1. Run the full pipeline
python pipelines/foi_pipeline/process.py --force

# 2. Build the website (automatically copies export_status/output.json)
cd ../publicinformation-web
npm run build

# 3. Check the output
open dist/data-status/index.html
```

### Quick Test (minimal data)

```bash
# 1. Ensure at least find_public_bodies has run
cd pipelines/foi_pipeline
python steps/find_public_bodies/process.py --input . --output steps/find_public_bodies/output.json --force

# 2. Run export_status to merge and add short_name
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force

# 3. Build website
cd ../../publicinformation-web
npm run build
```

## File Locations

| File | Purpose | Generated? |
|------|---------|------------|
| `pipelines/foi_pipeline/steps/*/output.json` | Step outputs | Yes (by pipeline) |
| `pipelines/foi_pipeline/steps/export_status/output.json` | **Final consolidated output** | Yes |
| `../publicinformation-web/src/data/pipeline-status.json` | Website data input | Yes (by prebuild) |
| `../publicinformation-web/dist/data-status/index.html` | Built page | Yes (by Astro) |

## Testing Your Setup

Verify the data flow is working:

```bash
# Check export_status output exists and has data
ls -lh pipelines/foi_pipeline/steps/export_status/output.json
python3 -c "import json; d=json.load(open('pipelines/foi_pipeline/steps/export_status/output.json')); print(f\"Bodies: {len(d['public_bodies'])}, Step: {d['metadata']['step']}\")"

# Check website data file
ls -lh ../publicinformation-web/src/data/pipeline-status.json
python3 -c "import json; d=json.load(open('../publicinformation-web/src/data/pipeline-status.json')); print(f\"Bodies: {len(d['public_bodies'])}\")"

# Check built HTML has data
grep -c "Department of" ../publicinformation-web/dist/data-status/index.html
```

## Troubleshooting Decision Tree

```
Is data-status page empty?
  │
  ├─► No → Data is flowing correctly ✓
  │
  ▼ Yes
  │
  ├─► Is export_status/output.json present?
  │     │
  │     ├─► No → Run export_status step
  │     │         │
  │     │         └─► Does find_public_bodies/output.json exist?
  │     │               │
  │     │               ├─► No → Run find_public_bodies step first
  │     │               └─► Yes → Run export_status with --force
  │     │
  │     ▼ Yes
  │       │
  │       ├─► Does it have public_bodies?
  │       │     │
  │       │     ├─► No → Check for JSON corruption
  │       │     └─► Yes → Rebuild website (npm run build)
  │       │
  │       └─► Is prebuild copying it?
  │             │
  │             └─► Check prebuild script in package.json
```

## Documentation Index

### For Pipeline Developers

See `pipelines/foi_pipeline/AGENTS.md` for:
- Detailed step-by-step pipeline architecture
- Merging logic in export_status
- Running individual steps
- Data structure evolution
- Troubleshooting pipeline issues

### For Website Developers

See `../publicinformation-web/DATA_CONSUMPTION.md` for:
- Prebuild script behavior
- Data structure expected by the page
- Status rendering (colors, characters)
- Page features and CSS
- Testing and verification commands
- Troubleshooting website issues

### For Both

This file (`DATA_FLOW.md`) provides:
- End-to-end data flow overview
- Quick reference for common issues
- Integration points between pipeline and website
- Testing workflows
