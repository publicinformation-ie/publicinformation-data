# PublicInformation.ie - Agent Documentation Index

This is the top-level entry point for agent documentation in the publicinformation.ie repository. Use this file to navigate to all agent-relevant documentation.

## Core Data-Handling Principle

**If a record cannot be reasonably and deterministically reconstructed, write an error and let a human reviewer handle it.** Forcing a manual review is always preferable to risking a false positive or silently losing information.

Concretely, in the transform and canonicalization steps (`transform_disclosure_files`, `normalize_*`, `extract_disclosures_*`):

- **Don't guess.** Don't reconstruct malformed values with elaborate or fragile heuristics/regexes. If you can't map a value confidently, classify the problem, write an error to the step's `errors.json`, and move on.
- **Never silently null or rewrite a field** to make it "fit". A confidently-wrong value (false positive) or a quietly-dropped field is worse than an explicit, reviewable error.
- **Confirmed contamination** (e.g. a date or a column header sitting in `decision_status`) may be dropped from output — but always with an error logged so a human can find it. It is fine to declare a record or file "too malformed to reconstruct".

## Repository Structure

```
publicinformation-data/
├── AGENTS.md                          # This file - top-level index
├── DATA_FLOW.md                      # End-to-end data flow overview
├── pipelines/
│   └── foi_pipeline/
│       ├── AGENTS.md                 # FOI pipeline architecture and operations
│       ├── process.py                # Pipeline execution engine
│       ├── pipeline.json              # Authoritative step order configuration
│       └── steps/
│           ├── AGENTS.md              # Steps directory management guidelines
│           ├── README.md              # Complete step sequence and descriptions
│           └── <step_name>/
│               ├── README.md          # Step-specific documentation
│               ├── process.py         # Step entry point
│               └── AGENTS.md          # (Some steps may have their own)
├── scripts/
│   ├── AGENTS.md                      # Which helper script to use, and when
│   └── README.md                     # Helper scripts documentation
└── public/
    └── *.json                        # Public-facing output files
```

## Documentation Index

### Core Documentation Files

| File | Purpose | Audience |
|------|---------|----------|
| **[AGENTS.md](AGENTS.md)** | This top-level index | All agents |
| **[DATA_FLOW.md](DATA_FLOW.md)** | End-to-end data flow from pipeline to website | Pipeline & Website |
| **[pipelines/foi_pipeline/AGENTS.md](pipelines/foi_pipeline/AGENTS.md)** | Pipeline architecture, running steps, troubleshooting | Pipeline agents |
| **[pipelines/foi_pipeline/steps/AGENTS.md](pipelines/foi_pipeline/steps/AGENTS.md)** | Step directory management, adding new steps | Pipeline developers |
| **[pipelines/foi_pipeline/steps/README.md](pipelines/foi_pipeline/steps/README.md)** | Complete step sequence with descriptions | Pipeline users |
| **[scripts/AGENTS.md](scripts/AGENTS.md)** | Which helper script answers a given question (data-quality triage, tracing a file, migrations) | All agents |
| **[scripts/README.md](scripts/README.md)** | Helper and admin scripts — full usage | Maintainers |

## Tool Use
### For Python Files
1. **Do not use your native tools** (`grep_search`, `file_search`, `read_file`, `replace_string_in_file`) for inspecting, exploring, or navigating Python code unless Serena explicitly fails.
2. For all Python-related symbol discovery, dependency tracking, and outline reading, you **MUST use Serena's tools** (e.g., `find_symbol`, `symbol_overview`, `find_referencing_symbols`).
3. For editing Python files, prioritize Serena's structural editing tools (`replace_symbol_body`, `insert_after_symbol`, etc.) over broad string replacements.

### Quick Start: Running the Pipeline

**To run the full pipeline:**
```bash
python pipelines/foi_pipeline/process.py --force
```

**To run from a specific step:**
```bash
python pipelines/foi_pipeline/process.py --from export_status --force
```

**To run a single step manually:**
```bash
cd pipelines/foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force
```

> **Note:** When Vibe CLI attempts to run pipeline scripts, it may try multiple times. To prevent redundant execution, ensure you're using the process script (`process.py`) rather than calling individual step scripts directly. The process script handles dependencies and staleness checks.

### Step Directories

Each pipeline step has its own directory under `pipelines/foi_pipeline/steps/` with the following structure:

```
steps/<step_name>/
├── README.md         # Step documentation (what it does, input, output)
├── process.py        # Main processing script (entry point)
├── output.json       # Step output data
├── errors.json       # Per-record errors and warnings
├── override.json     # Manual overrides (never overwritten by automation)
├── dirty_ids.json    # IDs with changed upstream data
└── output_schema.json # JSON schema for output validation
```

**Step documentation:** Each step's README.md follows a consistent format:
- What the step does
- Input files and sources
- Output format and files
- Notable files in the directory

See [pipelines/foi_pipeline/steps/README.md](pipelines/foi_pipeline/steps/README.md) for the complete list of steps in order.

### Key Concepts

#### Pipeline Steps
The step sequence is defined in [`pipelines/foi_pipeline/pipeline.json`](pipelines/foi_pipeline/pipeline.json) (authoritative). Current steps:

1. **find_public_bodies** - Scrapes gov.ie for the master list
2. **find_public_bodies_subject_to_foi** - Filters to bodies subject to FOI legislation
3. **resolve_website_urls** - Resolves gov.ie stub URLs
4. **validate_websites** - Checks website reachability
5. **find_foi_pages** - Discovers FOI pages on each website
6. **find_foi_pages_search** - Apify batch search for bodies where crawl failed
7. **check_foi_pages** - Validates FOI page accessibility
8. **get_foi_emails** - Extracts FOI email addresses
9. **find_disclosure_pages** - Locates disclosure log pages
10. **find_disclosure_files** - Collects disclosure document links
11. **transform_disclosure_files** - Processes files into structured data
12. **normalize_disclosure_cells** - Normalizes string cell values
13. **extract_disclosures_detect_header_row** - Detects header rows in spreadsheets
14. **extract_disclosures_normalize_header** - Repairs null cells in header rows
15. **extract_disclosures_normalize_rows** - Normalizes date values to ISO 8601
16. **extract_disclosures_canonicalize** - Maps columns to canonical fields
17. **extract_disclosures_canonicalize_rows** - Normalizes decision_status values
18. **extract_disclosures_deduplicate** - Removes duplicate FOI records
19. **export_status** - Fan-in merge of all step outputs (CRITICAL for website)
20. **generate_topics** - Groups FOI records into topics
21. **db_upload** - Populates the libSQL database

**Critical Step:** `export_status` is the final aggregator that merges all step outputs into a single file consumed by the website. If data is missing on the site, check if this step has been run.

#### Data Flow

```
find_public_bodies → validate_websites → find_foi_pages → check_foi_pages → ... 
    → export_status → public/pipeline-data.json → Website consumption
```

See [DATA_FLOW.md](DATA_FLOW.md) for the complete end-to-end flow including website integration.

#### Override System

Each step directory may contain an `override.json` file with manually-curated records. These records:
- Are **never overwritten** by automated re-runs
- Use `"source_method": "manual"` and `"overridden": true` markers
- Bypass normal processing (no HTTP calls made for overridden bodies)
- Are committed to git as the source of truth

See [pipelines/foi_pipeline/AGENTS.md - Override System](pipelines/foi_pipeline/AGENTS.md#override-system) for details.

### Troubleshooting Guide

**Problem: Scripts are being run multiple times by Vibe**

This happens when Vibe CLI tries to execute step scripts directly. To prevent this:

1. **Always use the process script** for pipeline execution:
   ```bash
   python pipelines/foi_pipeline/process.py --force
   ```

2. **The process script's staleness checks** prevent re-running steps that are up-to-date. Use `--force` to bypass.

3. **For individual step testing**, use the process script with `--from`:
   ```bash
   python pipelines/foi_pipeline/process.py --from export_status --force
   ```

**Problem: Data missing on website**

Check the fallback chain:
1. Has `export_status` been run? (creates `steps/export_status/output.json`)
2. Has the website been rebuilt? (`cd ../publicinformation-web && npm run build`)
3. Check `../publicinformation-web/src/data/pipeline-status.json` source

See [DATA_FLOW.md - Troubleshooting](DATA_FLOW.md#troubleshooting-decision-tree) for the complete decision tree.

**Problem: All status show as "not_attempted"**

This means only `find_public_bodies` has been run. Run the full pipeline or at minimum through `export_status`.

### Codeberg Pages Publishing

`data.publicinformation.ie` is served from the `pages` branch by Codeberg
Pages. The `pages` branch is never edited by hand — it is fully rebuilt from
`public/` (plus a generated `index.html` and the `.domains` custom-domain
file) by `scripts/publish_pages.sh` every time a commit on `main` touches
`public/`.

**One-time setup per clone** (git does not auto-install hooks from a
committed directory):

```bash
git config core.hooksPath .githooks
```

Without this, commits to `public/` on `main` will not trigger a Pages
rebuild, and `scripts/publish_pages.sh` must be run manually instead.

- `scripts/generate_pages_index.py <dir>` — writes a plain directory-listing
  `index.html` into `<dir>`. Only ever run against the `pages` build
  snapshot, never against `public/` on `main`.
- `scripts/publish_pages.sh` — rebuilds and pushes the `pages` branch from
  scratch. No force-push; fails loudly (no retry) if the push is rejected —
  re-run it manually once any conflict on `pages` is resolved.
- `.githooks/post-commit` — no-ops unless the commit is on `main` and
  touched `public/`; otherwise runs `publish_pages.sh`.

### Common Commands Reference

| Task | Command |
|------|---------|
| Run full pipeline | `python pipelines/foi_pipeline/process.py --force` |
| Run from export_status | `python pipelines/foi_pipeline/process.py --from export_status --force` |
| Run single step | `cd pipelines/foi_pipeline && PYTHONPATH=. python steps/<step>/process.py --input ... --output ... --force` |
| Run tests | `cd pipelines/foi_pipeline && uv run pytest tests/ -q` |
| Build website | `cd ../publicinformation-web && npm run build` |
| One-time hook setup (Pages publishing) | `git config core.hooksPath .githooks` |
| Manually rebuild + publish `pages` branch | `scripts/publish_pages.sh` |
| Check export_status output | `ls -lh pipelines/foi_pipeline/steps/export_status/output.json` |
| Validate output | `python3 -c "import json; d=json.load(open('pipelines/foi_pipeline/steps/export_status/output.json')); print(f'Bodies: {len(d[\"public_bodies\"])}')"` |

### File Locations Reference

| File | Purpose | Generated |
|------|---------|-----------|
| `pipelines/foi_pipeline/pipeline.json` | Step order configuration | No |
| `pipelines/foi_pipeline/steps/*/output.json` | Individual step outputs | Yes |
| `pipelines/foi_pipeline/steps/export_status/output.json` | **Consolidated output for website** | Yes |
| `public/pipeline-data.json` | Public-facing consolidated data | Yes |
| `public/disclosure-files.json` | All disclosure file URLs | Yes |
| `public/foi-disclosures.json` | All FOI request records | Yes |
| `public/topics.json` | Topic groupings | Yes |

### When to Use Which Documentation

| Scenario | Start Here |
|----------|------------|
| **New to the project** | This file (AGENTS.md) → DATA_FLOW.md |
| **Need to run the pipeline** | [pipelines/foi_pipeline/AGENTS.md - Running the Pipeline](pipelines/foi_pipeline/AGENTS.md#running-the-pipeline) |
| **Adding a new step** | [pipelines/foi_pipeline/steps/AGENTS.md](pipelines/foi_pipeline/steps/AGENTS.md) |
| **Troubleshooting data issues** | [DATA_FLOW.md - Troubleshooting](DATA_FLOW.md#common-issues--fixes) |
| **Finding which files/bodies contribute the most errors, tracing a file, or running a one-off migration** | [scripts/AGENTS.md](scripts/AGENTS.md) — check before writing a new one-off script |
| **Understanding data model** | [pipelines/foi_pipeline/AGENTS.md - Data Model](pipelines/foi_pipeline/AGENTS.md#data-model-evolution) |
| **Using override system** | [pipelines/foi_pipeline/AGENTS.md - Override System](pipelines/foi_pipeline/AGENTS.md#override-system) |
| **Website data consumption** | [../publicinformation-web/DATA_CONSUMPTION.md](../publicinformation-web/DATA_CONSUMPTION.md) |

