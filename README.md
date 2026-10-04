# PublicInformation.ie - Data Pipeline

**Open data pipeline for Irish Freedom of Information (FOI) public body information**

[![Codeberg](https://codeberg.org/publicinformation-ie/publicinformation-data/badge)](https://codeberg.org/publicinformation-ie/publicinformation-data)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

This repository contains the data processing pipeline for [PublicInformation.ie](https://publicinformation.ie), a project that tracks and publishes Freedom of Information (FOI) data from Irish public bodies. The pipeline extracts, transforms, and loads data about FOI pages, email addresses, disclosure logs, and disclosure files from hundreds of Irish government and public sector websites.

## Features

- **Comprehensive Coverage**: Processes data from all Irish public bodies subject to FOI legislation
- **Multi-step Pipeline**: Sequential processing steps from discovery to database upload
- **Automated Extraction**: Scrapes websites for FOI pages, contact information, and disclosure documents
- **Data Normalization**: Standardizes and cleans extracted data for consistency
- **Override System**: Manual corrections preserved across automated runs
- **Open Output**: Publishes consolidated JSON data files for public use
- **Database Integration**: Populates a libSQL database with structured FOI data

## Quick Start

### Get the Data

Start at [`public/index.html`](public/index.html) — a landing page with three entry points depending on what you need:

- [`public/get-the-data.html`](public/get-the-data.html) — plain CSV downloads, no technical background needed
- [`public/quickstart.html`](public/quickstart.html) — a runnable code example for fetching and using the JSON-LD data programmatically
- [`public/data-quality.html`](public/data-quality.html) — how extraction quality is tracked, and how to report or fix a problem

#### Curated Linked Data datasets

Six datasets are published as versioned Linked Data under `public/latest/<dataset>/` (always the newest release) and `public/vX.Y.Z/<dataset>/` (immutable per-version snapshots), each with its own JSON-LD, CSV, and CSV metadata, plus a dataset-specific `README.md`:

| Dataset | Version | Records | Docs |
|---------|---------|---------|------|
| Public Bodies | v2.0.0 | 883 | [`public/latest/public-bodies/README.md`](public/latest/public-bodies/README.md) |
| FOI Disclosures | v1.0.0 | 60,177 | [`public/latest/foi-disclosures/README.md`](public/latest/foi-disclosures/README.md) |
| FOI Request Files | v1.0.0 | 1,593 | [`public/latest/foi-request-files/README.md`](public/latest/foi-request-files/README.md) |
| Who Does What | v1.0.0 | 27 | [`public/latest/who-does-what/README.md`](public/latest/who-does-what/README.md) |
| Public Body Actions | v1.0.0 | 186 | [`public/latest/public-body-actions/README.md`](public/latest/public-body-actions/README.md) |
| Motions | v1.0.0 | 3,959 | [`public/latest/motions/README.md`](public/latest/motions/README.md) |

`public-bodies` is regenerated automatically by the FOI pipeline's `export_status` step on every full run (logic in `src/lib/publish_public_bodies.py`), so it always stays in lockstep with `pipeline-data.json`; the other datasets are produced by standalone `scripts/transform_*.py` — seven such scripts as of this writing (`ls scripts/transform_*.py`).

Supporting technical-reference files: [`public/catalog/`](public/catalog/) (one DCAT-AP `.ttl` per dataset) and [`public/schemas/`](public/schemas/) (one JSON Schema per dataset).

#### Raw pipeline outputs

Separate from the curated datasets above, the pipeline also writes unversioned raw outputs directly to `public/` on every run:

| File | Description |
|------|-------------|
| [`public/pipeline-data.json`](public/pipeline-data.json) | Consolidated status of all public bodies |
| [`public/foi-disclosures.json`](public/foi-disclosures.json) | All extracted FOI request records (pre-Linked-Data raw export) |
| [`public/disclosure-files.json`](public/disclosure-files.json) | All discovered disclosure document URLs |
| [`public/topics.json`](public/topics.json) | Topic groupings for FOI records |

These are regenerated automatically when the pipeline runs and are safe to use directly, but carry no versioning or schema guarantees — prefer the curated datasets above for stable programmatic use.

### Run the Pipeline Locally

There are four pipelines under `pipelines/`, each with its own `pipeline.json` step order. `process.py` takes the pipeline directory as its first (mandatory) argument:

| Pipeline | What it does |
|----------|---------------|
| `foi_pipeline` | The main pipeline — discovers public bodies, FOI pages, disclosure logs and files, and extracts FOI request records |
| `cso_pipeline` | Ingests Ireland's [CSO Register of Public Sector Bodies](https://www.cso.ie/) as a more authoritative source of body/website/sector data; also supplies the `resolve_website_urls` step reused by `foi_pipeline` |
| `wdw_pipeline` | Builds the "Who Does What" dataset — links from public bodies to their plain-English gov.ie description |
| `datagovie_pipeline` | Links public bodies to their organisation page on [data.gov.ie](https://data.gov.ie/), Ireland's open data portal |

```bash
# Clone the repository
git clone https://codeberg.org/publicinformation-ie/publicinformation-data.git
cd publicinformation-data

# Run a pipeline (pass its directory explicitly)
python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force
```

This processes all steps (defined in `<pipeline>/pipeline.json`) and generates output files in `<pipeline>/steps/<step_name>/output.json`. Swap `pipelines/foi_pipeline` for `pipelines/cso_pipeline`, `pipelines/wdw_pipeline`, or `pipelines/datagovie_pipeline` to run those instead.

The consolidated output appears in `pipelines/foi_pipeline/steps/export_status/output.json` and is copied to `public/pipeline-data.json`.

## Installation

### Prerequisites

- Python 3.11+ (recommended: 3.12)
- Git
- uv (Python package manager) - optional but recommended

### Python Environment Setup

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (using uv)
uv pip install -r pipelines/foi_pipeline/requirements.txt
```

Or using pip directly:

```bash
pip install -r pipelines/foi_pipeline/requirements.txt
```

Some steps use an LLM as a judge and support pluggable backends via `EVAL_JUDGE_PROVIDER` (`anthropic`, `openai`, or `mistral`) — install the matching SDK (e.g. `uv pip install anthropic`) if you use one. See the comments in `pipelines/foi_pipeline/requirements.txt` for details.

### Environment Configuration

For database operations, create a `.env.admin` file from the example:

```bash
cp .env.admin.example .env.admin
# Edit .env.admin with your database credentials
```

Required variables for production database upload:
- `DATABASE_URL`: libSQL database connection URL
- `DATABASE_AUTH_TOKEN`: Bunny/CDN authentication token

Optional variables for LLM-judge-backed steps:
- `EVAL_JUDGE_PROVIDER`: `anthropic`, `openai`, or `mistral`
- `EVAL_JUDGE_MODEL`, `EVAL_JUDGE_BASE_URL`: model name and (for local/OpenAI-compatible servers) base URL

For local development, the default SQLite database (`local.db`) is used.

## Usage

### Pipeline Commands

| Command | Description |
|---------|-------------|
| `python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force` | Run the complete pipeline from scratch |
| `python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --from export_status --force` | Run from a specific step |
| `python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --from generate_topics` | Run from a step without forcing |
| `python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --to export_status --force` | Run only up to and including a step |
| `python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --from find_foi_pages --to get_foi_emails --force` | Run an inclusive window of steps |

### Individual Step Execution

Each step can be run independently:

```bash
cd pipelines/foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force
```

### Running Tests

```bash
cd pipelines/foi_pipeline
uv run pytest tests/ -q
```

### Experiments & Evaluation

Two related but distinct tools live alongside `foi_pipeline`:

- **Experiments** (`pipelines/foi_pipeline/experiments/`) — dated, one-off investigations into extraction-quality questions (e.g. a pdfplumber parameter sweep). See [`experiments/README.md`](pipelines/foi_pipeline/experiments/README.md) for how to run and add one.
- **Evaluation** (`pipelines/foi_pipeline/evaluate.py`) — the ongoing quality-scoring framework that runs per-step `eval/evaluate.py` scripts, checks for regressions against a baseline, and prints a north-star metric. See [`evaluation/AGENTS.md`](pipelines/foi_pipeline/evaluation/AGENTS.md) for usage and LLM-judge configuration.

### Common Workflows

**Update all data and rebuild website:**
```bash
python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force
cd ../publicinformation-web
npm run build
```

**Quick data refresh (from export_status):**
```bash
python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --from export_status --force
```

**Check data status:**
```bash
# Count public bodies
python3 -c "import json; d=json.load(open('pipelines/foi_pipeline/steps/export_status/output.json')); print(f'Public bodies: {len(d[\"public_bodies\"])}')"

# Validate output structure
python3 -c "import json; d=json.load(open('public/pipeline-data.json')); print('Metadata:', d.get('metadata')); print('Sample body:', d['public_bodies'][0] if d['public_bodies'] else 'None')"
```

## Project Structure

```
publicinformation-data/
├── README.md                      # This file - project overview
├── AGENTS.md                      # Agent/automation documentation index — start here for full detail
├── .env.admin.example             # Environment configuration template
├── local.db                       # Local SQLite database (gitignored)
│
├── pipelines/                     # Four independent pipelines, each with process.py + pipeline.json
│   ├── foi_pipeline/               # Main pipeline — see pipelines/foi_pipeline/AGENTS.md
│   │   ├── steps/                  # Step implementations — see steps/README.md
│   │   ├── experiments/            # Ad-hoc extraction-quality investigations — see experiments/README.md
│   │   └── evaluation/             # Quality scoring framework — see evaluation/AGENTS.md
│   ├── cso_pipeline/               # CSO Register ingestion
│   ├── wdw_pipeline/               # "Who Does What" link builder
│   └── datagovie_pipeline/         # data.gov.ie organisation-link builder
│
├── scripts/                       # Helper and admin scripts — see scripts/README.md
│
└── public/                        # Public-facing output files, served via Codeberg Pages
    ├── index.html                 # Landing page
    ├── get-the-data.html          # Non-technical CSV download guide
    ├── quickstart.html            # Developer quickstart with runnable example
    ├── data-quality.html          # Data quality & contributing guide
    ├── pipeline-data.json         # Raw: consolidated public body status
    ├── foi-disclosures.json       # Raw: all FOI request records
    ├── disclosure-files.json      # Raw: all disclosure document URLs
    ├── topics.json                # Raw: topic groupings
    ├── schema.sql                 # Database schema
    ├── LICENSE                    # CC-BY 4.0 license for public data
    ├── CHANGELOG.md               # Changelog for public bodies dataset
    ├── catalog/                   # DCAT-AP metadata, one .ttl per dataset
    ├── schemas/                   # JSON Schema, one per dataset
    ├── vocabularies/              # Controlled vocabularies
    │   ├── body-type.csv
    │   └── foi-scope.csv
    ├── latest/                    # Curated Linked Data datasets (mirrors newest version)
    │   ├── public-bodies/
    │   ├── foi-disclosures/
    │   ├── foi-request-files/
    │   └── who-does-what/
    └── vX.Y.Z/                    # Immutable versioned dataset releases
```

## Pipeline Steps

The step sequence is defined in [`pipelines/foi_pipeline/pipeline.json`](pipelines/foi_pipeline/pipeline.json) — that file and [`pipelines/foi_pipeline/steps/README.md`](pipelines/foi_pipeline/steps/README.md) are the authoritative, up-to-date references (the pipeline currently runs 25+ steps and changes as data-quality issues are found and fixed). At a high level, each pipeline run moves through these phases:

1. **Discovery** — find public bodies, their websites, FOI pages, FOI contact emails, and disclosure log pages
2. **Collection** — find and download disclosure files (PDFs, spreadsheets) linked from disclosure log pages
3. **Extraction & normalization** — convert files to structured rows, detect/repair header rows, normalize cell values and dates
4. **Canonicalization** — map raw columns to canonical FOI fields, normalize status values, deduplicate records
5. **Export** — `export_status` fans in every step's output into the consolidated status report and public JSON files; `generate_topics` and `db_upload` run last

`export_status` is the critical fan-in step: if data is missing on the website, check whether it has been run.

## Data Model

### Public Body Status Structure

The main output (`export_status/output.json` and `public/pipeline-data.json`) contains:

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
      "official_website_url": "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
      "status": {
        "website_url": {"url": "...", "status": "success" | "failed" | "not_attempted"},
        "foi_page": {"url": "...", "status": "success" | "failed" | "not_attempted"},
        "foi_email": {"email": "...", "status": "success" | "failed" | "not_attempted"},
        "disclosures_page": {"url": "...", "status": "success" | "failed" | "not_attempted"},
        "disclosure_files": {"total": 5, "valid": 5, "failed": 0, "status": "success" | "failed" | "not_attempted"},
        "foi_requests": {"valid": 100, "errors": 0, "status": "success" | "failed" | "not_attempted"}
      }
    }
  ]
}
```

### Status Field Values

| Value | Meaning |
|-------|---------|
| `"success"` | Operation completed successfully for this body |
| `"failed"` | Operation attempted but failed for this body |
| `"not_attempted"` | Operation not run or body not in results |

## Override System

Manual corrections in a step's `override.json` (marked `"source_method": "manual", "overridden": true`) are **never overwritten** by automated runs. Add or edit a record, commit it to git, and the pipeline will skip re-processing that body for that step. See [`pipelines/foi_pipeline/AGENTS.md#override-system`](pipelines/foi_pipeline/AGENTS.md#override-system) for the full mechanism, including per-file column-mapping overrides.

## Data Outputs

All files in the `public/` directory are safe for direct use. There are two tiers:

### Curated Linked Data datasets

The curated datasets — Public Bodies, FOI Disclosures, FOI Request Files, Who Does What, data.gov.ie Links, lobbying.ie Links, Public Body Actions, and Motions — implement 3-4 star Linked Data best practices and are published as JSON-LD + CSV under `public/latest/<dataset>/` (always the newest release) and `public/vX.Y.Z/<dataset>/` (immutable per-version snapshots). Each dataset has its own `README.md` documenting its data model, versioning, and provenance — see the table in [Get the Data](#get-the-data) above. Shared technical-reference files:

- **`public/catalog/`**: DCAT-AP 3.0 compliant dataset metadata (RDF/Turtle), one `.ttl` per dataset
- **`public/schemas/`**: JSON Schema for validation, one per dataset
- **`public/vocabularies/`**: Controlled vocabularies (`body-type.csv`, `foi-scope.csv`)
- **`public/LICENSE`**: CC-BY 4.0 license for the public data
- **`public/CHANGELOG.md`**: Version history

### Raw pipeline outputs

Unversioned files written directly to `public/` on every pipeline run:

- **`pipeline-data.json`**: Consolidated status of all public bodies (updated on each pipeline run)
- **`foi-disclosures.json`**: All extracted FOI request records with full details
- **`disclosure-files.json`**: All discovered disclosure document URLs
- **`topics.json`**: Topic groupings with matched FOI records

### Database Schema

The pipeline populates a libSQL database with the following tables:

- `public_bodies` - Core public body information
- `disclosure_files` - Disclosure document metadata
- `foi_disclosures` - FOI request records
- `topics` - Topic definitions
- `disclosure_topic_matches` - Links between disclosures and topics

The canonical schema is defined in [`public/schema.sql`](public/schema.sql).

## Publishing

`data.publicinformation.ie` was historically served from a `pages` branch on Codeberg Pages, rebuilt from `public/` by `scripts/publish_pages.sh`. That pipeline is **legacy/inactive** on the current host. Large data files under `public/`, FOI pipeline state, and eval inputs are stored via **Git LFS**: run `git lfs install` once per clone, and use `GIT_LFS_SKIP_SMUDGE=1` for code-only clones. Run `git lfs pull` before running tests that read `pipelines/**/eval/input.json`.

## Contributing

Contributions are welcome! Please follow these guidelines:

### Getting Started

1. Fork the repository on GitHub (`https://github.com/publicinformation-ie/publicinformation-data`)
2. Clone your fork locally
3. Create a feature branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Run tests: `cd pipelines/foi_pipeline && uv run pytest tests/ -q`
6. Commit your changes with descriptive messages
7. Push to your fork and submit a pull request

### Code Style

- Follow the existing code style in the surrounding files
- Use type hints where appropriate
- Keep functions focused and single-purpose
- For pipeline transform/canonicalization steps, see the core data-handling principle in [`AGENTS.md`](AGENTS.md): don't guess at malformed values, don't silently null or rewrite a field to make it fit — write an error and let a human reviewer handle it

### Documentation

- Update relevant documentation when adding new features
- Follow the existing documentation format
- Use consistent heading levels and formatting

### Testing

- Add tests for new functionality
- Ensure existing tests continue to pass
- Test edge cases and error conditions

### Pipeline Steps

When adding a new step:

1. Create a directory under `pipelines/foi_pipeline/steps/<step_name>/`
2. Add a `process.py` entry point
3. Define an `output_schema.json` for validation
4. Create a `README.md` documenting the step
5. Add the step to `pipelines/foi_pipeline/pipeline.json`
6. Implement a merger function if the step contributes to `export_status`
7. Update `pipelines/foi_pipeline/steps/README.md`

## Troubleshooting

**Data missing on website**: check whether `export_status` has been run and `public/pipeline-data.json` has data.

**Pipeline step fails**: check the step's `errors.json`, then re-run it manually with `--force`.

```bash
# Check which steps have output
ls -la pipelines/foi_pipeline/steps/*/output.json

# Check for errors in a specific step
cat pipelines/foi_pipeline/steps/<step_name>/errors.json | python -m json.tool
```

See [`AGENTS.md`](AGENTS.md#troubleshooting-guide) for the full troubleshooting guide and decision tree.

## Architecture Decisions

The pipeline is broken into small, resumable, isolated steps (each independently testable, re-runnable, and override-preserving) that read/write plain JSON (human-readable, diffable, schema-validated via `output_schema.json`) and feed a libSQL database (HTTP-based, SQLite-compatible, suited to static-site/serverless hosting).

## License

This project is licensed under the GNU Affero General Public License version 3.0 (AGPL-3.0) - see the [LICENSE](LICENSE) file for details.

The AGPL-3.0 license ensures that any modifications to this software that are used over a network (such as a web service) must have their source code made available to users. This ensures the data processing pipeline remains open and accessible to all.

## Support

### Reporting Issues

Please report issues on the Codeberg repository:

- [Issues](https://codeberg.org/publicinformation-ie/publicinformation-data/issues)
- [Discussions](https://codeberg.org/publicinformation-ie/publicinformation-data/discussions)

Include as much detail as possible:
- Pipeline step that failed
- Error messages
- Reproduction steps
- Environment information (Python version, OS, etc.)

### Contributing Fixes

For bug fixes and improvements, please:

1. Check existing issues to avoid duplicates
2. Fork the repository and create a topic branch
3. Make minimal, focused changes
4. Include tests if possible
5. Submit a pull request with a clear description

## Related Projects

- [PublicInformation.ie Website](https://codeberg.org/publicinformation-ie/publicinformation-web) - The frontend website that consumes this data
- [foi.gov.ie](https://foi.gov.ie) - The official Irish FOI portal (source of public body list)

## Acknowledgments

- The Irish Government for maintaining the official FOI portal and public body registry
- All contributors who have submitted corrections and improvements
- The open source community for the tools and libraries that make this project possible

---

*For the most up-to-date technical information, see [AGENTS.md](AGENTS.md).*

*Licensed under [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0)*
