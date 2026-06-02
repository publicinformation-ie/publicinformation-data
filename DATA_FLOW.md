# Data Flow Documentation - PublicInformation.ie

This document provides an overview of how data flows from the FOI pipeline to the publicinfo-prototype website. For detailed information, see the specialized documentation files.

## Quick Reference

| Document | Purpose | Location |
|----------|---------|----------|
| **AGENTS.md** (Pipeline) | How data is produced by the FOI pipeline | `foi_pipeline/AGENTS.md` |
| **DATA_CONSUMPTION.md** (Website) | How data is consumed by the website | `publicinfo-prototype/DATA_CONSUMPTION.md` |
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

The FOI pipeline consists of 14 sequential steps that process public body data:

1. **find_public_bodies** - Base data (scrapes foi.gov.ie)
2. **resolve_website_urls** - Second-pass URL resolution
3. **validate_websites** - Checks website reachability
4. **find_foi_pages** - Discovers FOI pages
5. **check_foi_pages** - Validates FOI pages
6. **get_foi_emails** - Extracts FOI email addresses
7. **find_disclosure_pages** - Locates disclosure pages
8. **find_disclosure_files** - Finds disclosure documents
9. **transform_disclosure_files** - Processes files
10. **extract_disclosures_detect_header_row** - Detects header row
11. **extract_disclosures_canonicalize** - Extracts canonical FOI records
12. **export_status** - Fan-in merge (status consolidator for the website)
13. **generate_topics** - Groups records into keyword topics
14. **db_upload** - Populates the libSQL database

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
cd foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force
```

Then rebuild the website:
```bash
cd publicinfo-prototype
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
cd foi_pipeline
python process.py --force

# 2. Build the website (automatically copies export_status/output.json)
cd publicinfo-prototype
npm run build

# 3. Check the output
open dist/data-status/index.html
```

### Quick Test (minimal data)

```bash
# 1. Ensure at least find_public_bodies has run
cd foi_pipeline
python steps/find_public_bodies/process.py --input . --output steps/find_public_bodies/output.json --force

# 2. Run export_status to merge and add short_name
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force

# 3. Build website
cd publicinfo-prototype
npm run build
```

## File Locations

| File | Purpose | Generated? |
|------|---------|------------|
| `foi_pipeline/steps/*/output.json` | Step outputs | Yes (by pipeline) |
| `foi_pipeline/steps/export_status/output.json` | **Final consolidated output** | Yes |
| `publicinfo-prototype/src/data/pipeline-status.json` | Website data input | Yes (by prebuild) |
| `publicinfo-prototype/dist/data-status/index.html` | Built page | Yes (by Astro) |

## Testing Your Setup

Verify the data flow is working:

```bash
# Check export_status output exists and has data
ls -lh foi_pipeline/steps/export_status/output.json
python3 -c "import json; d=json.load(open('foi_pipeline/steps/export_status/output.json')); print(f\"Bodies: {len(d['public_bodies'])}, Step: {d['metadata']['step']}\")"

# Check website data file
ls -lh publicinfo-prototype/src/data/pipeline-status.json
python3 -c "import json; d=json.load(open('publicinfo-prototype/src/data/pipeline-status.json')); print(f\"Bodies: {len(d['public_bodies'])}\")"

# Check built HTML has data
grep -c "Department of" publicinfo-prototype/dist/data-status/index.html
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

See `foi_pipeline/AGENTS.md` for:
- Detailed step-by-step pipeline architecture
- Merging logic in export_status
- Running individual steps
- Data structure evolution
- Troubleshooting pipeline issues

### For Website Developers

See `publicinfo-prototype/DATA_CONSUMPTION.md` for:
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
