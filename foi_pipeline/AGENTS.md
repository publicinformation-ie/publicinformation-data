# FOI Pipeline - Agent Documentation

This document explains how the FOI pipeline processes public body data for the publicinformation.ie project. For human-facing documentation, see README files in each directory.

## Overview

The pipeline is a series of Python steps (defined in [`pipeline.json`](pipeline.json)) that discover Irish public bodies, validate and enrich their contact information, extract disclosure data, and consolidate results into a final status output consumed by the website.

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
2. `find_public_bodies_subject_to_foi` - Filters to bodies actually subject to FOI (removes exclusions)
3. `resolve_website_urls` - Second-pass resolution of gov.ie stub URLs
4. `validate_websites` - HTTP-checks website reachability
5. `find_foi_pages` - Crawl-only discovery of FOI pages on each website
6. `find_foi_pages_search` - Apify batch search for bodies where crawl failed (`APIFY_TOKEN` required)
7. `check_foi_pages` - Validates FOI page accessibility
8. `get_foi_emails` - Extracts FOI email addresses
9. `find_disclosure_pages` - Locates disclosure log pages (`APIFY_TOKEN` required for gov.ie bodies)
10. `find_disclosure_files` - Collects disclosure document links
11. `transform_disclosure_files` - Processes files into structured data
12. `normalize_disclosure_cells` - Normalizes string cell values
13. `extract_disclosures_detect_header_row` - Detects header rows
14. `extract_disclosures_normalize_header` - Repairs null cells in detected header rows (continuation merge + forward-fill)
15. `extract_disclosures_normalize_rows` - Normalizes date values to ISO 8601 format
16. `extract_disclosures_canonicalize` - Maps columns to canonical fields
17. `extract_disclosures_canonicalize_rows` - Normalizes decision_status field values to canonical statuses
18. `extract_disclosures_deduplicate` - Removes duplicate FOI records
19. `export_status` - Fan-in merge of all step outputs (website data source)
20. `generate_topics` - Groups FOI records into topics
21. `db_upload` - Populates the libSQL database

### Data Flow

```
find_public_bodies -> find_public_bodies_subject_to_foi -> resolve_website_urls -> validate_websites
    -> find_foi_pages -> find_foi_pages_search -> check_foi_pages
    -> get_foi_emails -> find_disclosure_pages -> find_disclosure_files
    -> transform_disclosure_files -> normalize_disclosure_cells
    -> extract_disclosures_detect_header_row -> extract_disclosures_normalize_header
    -> extract_disclosures_normalize_rows -> extract_disclosures_canonicalize
    -> extract_disclosures_canonicalize_rows -> extract_disclosures_deduplicate
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
| Experiments | [experiments/README.md](experiments/README.md) | Index of past experiments, learnings, and guidance for running new ones |

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues including:
- export_status/output.json not generated
- Data not appearing on website
- short_name missing
- Pipeline output locations
