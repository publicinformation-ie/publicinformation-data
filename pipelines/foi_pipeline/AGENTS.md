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

> **Always use `process.py` rather than calling individual step scripts directly.** This ensures dependencies are respected and prevents redundant execution. `process.py --from <step> --force` (see above) covers running "just one step forward" — reach for direct step invocation only for isolated debugging.

**To run a single step manually (debugging only):**
```bash
cd pipelines/foi_pipeline
PYTHONPATH=".:../../src" python steps/export_status/process.py \
  --input steps/extract_disclosures_canonicalize/output.json \
  --output steps/export_status/output.json \
  --force
```
`PYTHONPATH` needs **both** the pipeline dir (`.`, for `steps.*` imports) **and** `../../src` (for `lib.*` imports) — `PYTHONPATH=.` alone fails with `ModuleNotFoundError: No module named 'lib'`.

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
10. `fingerprint_disclosure_pages` - Hashes disclosure page file links to detect changes between runs
11. `find_disclosure_files` - Collects disclosure document links
12. `transform_disclosure_files` - Processes files into structured data
13. `normalize_disclosure_cells` - Normalizes string cell values
14. `filter_phantom_rows` - Drops blank rows (all file types) and merges wrapped-cell PDF fragments into their parent rows; single authoritative row-structure repair layer
15. `extract_disclosures_detect_header_row` - Detects header rows
16. `extract_disclosures_normalize_header` - Repairs null cells in detected header rows (continuation merge + forward-fill)
17. `extract_disclosures_normalize_rows` - Normalizes date values to ISO 8601 format
18. `extract_disclosures_canonicalize` - Maps columns to canonical fields
19. `extract_disclosures_canonicalize_rows` - Normalizes decision_status field values to canonical statuses
20. `extract_disclosures_deduplicate` - Removes duplicate FOI records
21. `export_status` - Fan-in merge of all step outputs (website data source)
22. `generate_topics` - Groups FOI records into topics
23. `db_upload` - Populates the libSQL database

### Data Flow

```
find_public_bodies -> find_public_bodies_subject_to_foi -> resolve_website_urls -> validate_websites
    -> find_foi_pages -> find_foi_pages_search -> check_foi_pages
    -> get_foi_emails -> find_disclosure_pages -> fingerprint_disclosure_pages -> find_disclosure_files
    -> transform_disclosure_files -> normalize_disclosure_cells -> filter_phantom_rows
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

### Single step execution (debugging only — prefer `process.py --from <step>` above)

```bash
cd pipelines/foi_pipeline
PYTHONPATH=".:../../src" python steps/<step>/process.py \
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

**Always verify `public_body_id` against the canonical source before writing an override entry.** Look it up in `steps/find_public_bodies/output.json` (or `data/public_bodies.csv`) by name — never type an id from memory or infer it from a nearby/similar id. A wrong id silently attaches the record to whatever unrelated body happens to hold that id in the canonical map. If that body isn't in `find_public_bodies_subject_to_foi/output.json`'s inclusions, `export_status` will fail loudly with an "orphan" `ValueError` (recoverable — see the incident below); if it *is* in the inclusions, the record merges into the wrong body's data with **no error at all**. (Incident: commit `7638972` added override entries for 4 departments using wrong ids that happened to belong to unrelated bodies — Adare Heritage Trust, An Foras Teanga, An Grianán Theatre, An Post GeoDirectory — none of which are FOI-subject-inclusions bodies, so it surfaced as an export_status orphan error rather than silent corruption. Fixed 2026-07-23 by correcting the ids in the override files and surgically patching every downstream `output.json`/`errors.json` that had already baked in the wrong id.)

The `extract_disclosures_canonicalize` step additionally supports **file-level column mapping overrides** via `steps/extract_disclosures_canonicalize/column_mappings.json`. Each entry maps a `file_url` to a manual column mapping that bypasses automated header detection. Keys are string column indices (`"0"`, `"1"`, …); values are a canonical field name (string), an array of field names (splits cell by whitespace), or `null` (skip column). Add an entry when a file's headers cannot be resolved automatically (e.g. bilingual Irish PDFs). See `steps/extract_disclosures_canonicalize/README.md` for full details.

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

## Data quality tasks

After completing any data quality task, run the pipeline before marking the task complete:

```bash
cd pipelines/foi_pipeline && python status.py --assert-fresh
```

If stale, run the pipeline first:

```bash
cd pipelines/foi_pipeline && python process.py
```
