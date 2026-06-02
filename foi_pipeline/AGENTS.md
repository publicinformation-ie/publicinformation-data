# FOI Pipeline - Agent Documentation

This document explains how the FOI pipeline processes public body data for the publicinformation.ie project. For human-facing documentation, see README files in each directory.

## Overview

The pipeline is a series of 16 Python steps that discover Irish public bodies, validate and enrich their contact information, extract disclosure data, and consolidate results into a final status output consumed by the website.

## Quick Start

**To run the full pipeline:**
```bash
python process.py --force
```

**To run from a specific step:**
```bash
python process.py --from export_status --force
```

**To run a single step manually:**
```bash
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/extract_disclosures_canonicalize/output.json \
  --output steps/export_status/output.json \
  --force
```

> **Note:** Always use `process.py` rather than calling individual step scripts directly. This ensures dependencies are respected and prevents redundant execution.

## Pipeline Architecture

### Steps (in order)

1. `find_public_bodies` - Scrapes the master list from foi.gov.ie
2. `resolve_website_urls` - Second-pass resolution of gov.ie stub URLs
3. `validate_websites` - HTTP-checks website reachability
4. `find_foi_pages` - Crawl-only discovery of FOI pages on each website
5. `find_foi_pages_search` - Apify batch search for bodies where crawl failed (`APIFY_TOKEN` required)
6. `check_foi_pages` - Validates FOI page accessibility
7. `get_foi_emails` - Extracts FOI email addresses
8. `find_disclosure_pages` - Locates disclosure log pages (`APIFY_TOKEN` required for gov.ie bodies)
9. `find_disclosure_files` - Collects disclosure document links
10. `transform_disclosure_files` - Processes files into structured data
11. `normalize_disclosure_cells` - Normalizes string cell values
12. `extract_disclosures_detect_header_row` - Detects header rows
13. `extract_disclosures_canonicalize` - Maps columns to canonical fields
14. `export_status` - Fan-in merge of all step outputs (website data source)
15. `generate_topics` - Groups FOI records into topics
16. `db_upload` - Populates the libSQL database

### Data Flow

```
find_public_bodies -> validate_websites -> find_foi_pages -> find_foi_pages_search -> check_foi_pages
    -> get_foi_emails -> find_disclosure_pages -> find_disclosure_files
    -> transform_disclosure_files -> normalize_disclosure_cells
    -> extract_disclosures_detect_header_row -> extract_disclosures_canonicalize
    -> export_status -> generate_topics -> db_upload -> libSQL database
```

## Running the Pipeline

### From the process script

The `process.py` script runs steps in order from `pipeline.json`, skipping stale steps unless `--force` is specified.

```bash
# Full pipeline from first step
python process.py --force

# Resume from a specific step
python process.py --from export_status --force

# Scope to one public body
python process.py --public-body 1001
```

### Single step execution

```bash
cd foi_pipeline
PYTHONPATH=. python steps/<step>/process.py \
  --input steps/<previous>/output.json \
  --output steps/<step>/output.json \
  --force
```

## Python Environment

The project uses `uv` for dependency management. From the `foi_pipeline` directory:

```bash
# Run tests
uv run pytest tests/ -q
```

## Override System

Steps can include manually-curated records in `override.json` that are never overwritten by automation. Records must have `"source_method": "manual"` and `"overridden": true`. When `IncrementalWriter` is constructed, it pre-loads override records and skips processing for those bodies.

For the full documentation sync workflow, see [steps/AGENTS.md](steps/AGENTS.md).

## Scoping to One Public Body

The `--public-body <ID>` flag reprocesses only that body end-to-end, leaving others unchanged:

```bash
python process.py --public-body 1001
python process.py --from validate_websites --public-body 1001
```

> **Note:** `--public-body` never forces. Combining with `--force` reduces output to the single body.

## Environment Variables

| Variable | Required by | Description |
|----------|------------|-------------|
| `APIFY_TOKEN` | `find_foi_pages_search`, `find_disclosure_pages` | Apify API token for batch search Actor runs. |

## Key Concepts

| Concept | Location | Description |
|---------|----------|-------------|
| export_status | [steps/export_status/AGENTS.md](steps/export_status/AGENTS.md) | Fan-in merge of all step outputs (website data source) |
| Database | [steps/db_upload/AGENTS.md](steps/db_upload/AGENTS.md) | libSQL database configuration and upload |
| Evaluation | [evaluation/AGENTS.md](evaluation/AGENTS.md) | Step evaluation framework with LLM judging |
| Step Management | [steps/AGENTS.md](steps/AGENTS.md) | Adding/removing steps, documentation sync |

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues including:
- export_status/output.json not generated
- Data not appearing on website
- short_name missing
- Pipeline output locations
