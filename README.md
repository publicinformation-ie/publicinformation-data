# PublicInformation.ie - Data Pipeline

Open data pipeline for Irish Freedom of Information (FOI) public body information

[![CI](https://github.com/publicinformation-ie/publicinformation-data/actions/workflows/ci.yml/badge.svg)](https://github.com/publicinformation-ie/publicinformation-data/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

This repository contains the data processing pipeline for [PublicInformation.ie](https://publicinformation.ie). The project tracks and publishes Freedom of Information (FOI) data from Irish public bodies. The pipeline extracts, transforms and loads data about FOI pages, email addresses, disclosure logs and disclosure files. Its sources are hundreds of Irish government and public sector websites.

## Features

- Comprehensive coverage: the pipeline processes data from all Irish public bodies that are subject to FOI law.
- Multi-step pipeline: the steps run in sequence, from discovery to database upload.
- Automated extraction: the pipeline reads websites for FOI pages, contact information and disclosure documents.
- Data normalization: the pipeline standardizes and cleans extracted data.
- Override system: manual corrections survive later automated runs.
- Open output: the pipeline publishes consolidated JSON files for public use.
- Database integration: the pipeline fills a libSQL database with structured FOI data.

## Quick Start

### Get the Data

Start at [`public/README.md`](public/README.md). It is the data hub and has one entry point for each need:

- [`public/GET_THE_DATA.md`](public/GET_THE_DATA.md): plain CSV downloads for readers without a technical background.
- [`public/QUICKSTART.md`](public/QUICKSTART.md): a runnable code example that fetches and uses the JSON-LD data.
- [`public/DATA_QUALITY.md`](public/DATA_QUALITY.md): how the project tracks extraction quality, and how you report or fix a problem.

#### Curated Linked Data datasets

Twelve datasets are published as versioned Linked Data. Each dataset is under `public/latest/<dataset>/` (the newest release) and `public/vX.Y.Z/<dataset>/` (immutable snapshots for each version). Each dataset has JSON-LD, CSV and CSV metadata, plus its own `README.md`. Transport Policies is the exception: it has CSV and CSV metadata only, and no JSON-LD.

| Dataset | Version | Records | Docs |
|---------|---------|---------|------|
| Public Bodies | v2.0.0 | 883 | [`public/latest/public-bodies/README.md`](public/latest/public-bodies/README.md) |
| FOI Disclosures | v1.0.0 | 57,685 | [`public/latest/foi-disclosures/README.md`](public/latest/foi-disclosures/README.md) |
| FOI Request Files | v1.0.0 | 1,593 | [`public/latest/foi-request-files/README.md`](public/latest/foi-request-files/README.md) |
| Who Does What | v1.0.0 | 27 | [`public/latest/who-does-what/README.md`](public/latest/who-does-what/README.md) |
| Transport Policies | v1.0.0 | 21 | [`public/latest/transport-policies/README.md`](public/latest/transport-policies/README.md) |
| data.gov.ie Links | v1.0.0 | 137 | [`public/latest/data-gov-ie-links/README.md`](public/latest/data-gov-ie-links/README.md) |
| datacatalogue.gov.ie Links | v1.0.0 | 76 | [`public/latest/datacatalogue-gov-ie-links/README.md`](public/latest/datacatalogue-gov-ie-links/README.md) |
| lobbying.ie Links | v1.0.0 | 121 | [`public/latest/lobbying-ie-links/README.md`](public/latest/lobbying-ie-links/README.md) |
| Staff Numbers | v1.0.0 | 220 | [`public/latest/staff-numbers/README.md`](public/latest/staff-numbers/README.md) |
| Public Body Actions | v3.2.0 | 839 | [`public/latest/public-body-actions/README.md`](public/latest/public-body-actions/README.md) |
| Motions | v1.0.0 | 3,959 | [`public/latest/motions/README.md`](public/latest/motions/README.md) |
| Active Travel Allocations | v1.0.0 | 4,875 | [`public/latest/active-travel-allocations/README.md`](public/latest/active-travel-allocations/README.md) |

`public-bodies` is regenerated automatically by the FOI pipeline's `export_status` step on every full run. The logic is in `src/lib/publish_public_bodies.py`. This keeps the dataset in step with `pipeline-data.json`. Standalone `scripts/transform_*.py` scripts produce the other datasets. There are eleven such scripts as of this writing (`ls scripts/transform_*.py`).

The supporting technical-reference files are [`public/catalog/`](public/catalog/) (one DCAT-AP `.ttl` file for each dataset) and [`public/schemas/`](public/schemas/) (one JSON Schema for each dataset).

#### Raw pipeline outputs

The pipeline also writes unversioned raw outputs to `public/` on every run. These outputs are separate from the curated datasets above:

| File | Description |
|------|-------------|
| [`public/pipeline-data.json`](public/pipeline-data.json) | Consolidated status of all public bodies |
| [`public/foi-disclosures.json`](public/foi-disclosures.json) | All extracted FOI request records (pre-Linked-Data raw export). Built from `public/latest/foi-disclosures/bodies/*.ndjson`, not committed: run `python scripts/build_foi_combined.py` |
| [`public/disclosure-files.json`](public/disclosure-files.json) | All discovered disclosure document URLs |
| [`public/topics.json`](public/topics.json) | Topic groupings for FOI records |

These files are regenerated automatically when the pipeline runs. You can use them directly, but they have no versioning or schema guarantees. Prefer the curated datasets above for stable programmatic use.

### Run the Pipeline Locally

`pipelines/` holds thirteen pipelines. Each pipeline has its own step order in `pipeline.json`. `process.py` takes the pipeline directory as its first argument, and that argument is mandatory. The table lists the pipelines that people use most:

| Pipeline | What it does |
|----------|---------------|
| `foi_pipeline` | The main pipeline. It finds public bodies, FOI pages, disclosure logs and files, and extracts FOI request records. |
| `document_pipeline` | Turns curated public-interest PDFs into section Markdown, figures and published document bundles. It OCRs the image-only pages that the curator lists. |
| `minutes_pipeline` | Reads local-authority meeting minutes, OCRs scanned documents, and extracts and publishes motions. |
| `cso_pipeline` | Ingests Ireland's [CSO Register of Public Sector Bodies](https://www.cso.ie/) as a more authoritative source of body, website and sector data. It also supplies the `resolve_website_urls` step that `foi_pipeline` reuses. |
| `wdw_pipeline` | Builds the "Who Does What" dataset. It links public bodies to their plain-English description on gov.ie. |
| `datagovie_pipeline` | Links public bodies to their organization page on [data.gov.ie](https://data.gov.ie/), Ireland's open data portal. |
| `datacatalogue_pipeline` | Links public bodies to their organization page on [datacatalogue.gov.ie](https://datacatalogue.gov.ie/), the Public Service Data Catalogue. |

```bash
# Clone the repository
git clone https://github.com/publicinformation-ie/publicinformation-data.git
cd publicinformation-data

# Run a pipeline (pass its directory explicitly)
python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force
```

This command runs all steps in `<pipeline>/pipeline.json`. It writes output files to `<pipeline>/steps/<step_name>/output.json`. Replace `pipelines/foi_pipeline` with another pipeline directory, for example `pipelines/cso_pipeline`, to run that pipeline.

The consolidated output appears in `pipelines/foi_pipeline/steps/export_status/output.json`. The pipeline copies it to `public/pipeline-data.json`.

## Installation

### Prerequisites

- Python 3.11+ (recommended: 3.12)
- Git
- uv (Python package manager), optional but recommended

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

`document_pipeline` and `minutes_pipeline` use the same OCR dependencies: `pymupdf`, `pillow` and `pytesseract`. They are pinned in [`pipelines/document_pipeline/requirements.txt`](pipelines/document_pipeline/requirements.txt). OCR also needs the `tesseract` system binary on `PATH` (for example, `brew install tesseract` on macOS).

Some steps use a large language model (LLM) as a judge. These steps support three backends through `EVAL_JUDGE_PROVIDER`: `anthropic`, `openai` and `mistral`. If you use one, install the matching SDK, for example `uv pip install anthropic`. See the comments in `pipelines/foi_pipeline/requirements.txt` for details.

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

Two related but separate tools live beside `foi_pipeline`:

- Experiments (`pipelines/foi_pipeline/experiments/`): dated, one-off investigations into extraction-quality questions, for example a pdfplumber parameter sweep. See [`experiments/README.md`](pipelines/foi_pipeline/experiments/README.md) for how to run one and how to add one.
- Evaluation (`pipelines/foi_pipeline/evaluate.py`): the ongoing quality-scoring framework. It runs the per-step `eval/evaluate.py` scripts, checks for regressions against a baseline and prints a north-star metric. See [`evaluation/AGENTS.md`](pipelines/foi_pipeline/evaluation/AGENTS.md) for usage and LLM-judge configuration.

### Common Workflows

Update all data and rebuild the website:
```bash
python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force
cd ../publicinformation-web
npm run build
```

Quick data refresh (from `export_status`):
```bash
python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --from export_status --force
```

Check data status:
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
├── pipelines/                     # Independent pipelines, each with process.py + pipeline.json
│   ├── foi_pipeline/               # Main pipeline. See pipelines/foi_pipeline/README.md and AGENTS.md
│   │   ├── steps/                  # Step implementations — see steps/README.md
│   │   ├── experiments/            # Ad-hoc extraction-quality investigations — see experiments/README.md
│   │   └── evaluation/             # Quality scoring framework — see evaluation/AGENTS.md
│   ├── document_pipeline/          # Curated PDFs → document bundles — see pipelines/document_pipeline/README.md
│   ├── minutes_pipeline/           # Council minutes → motions — see pipelines/minutes_pipeline/README.md
│   ├── cso_pipeline/               # CSO Register ingestion
│   ├── wdw_pipeline/               # "Who Does What" link builder
│   ├── datagovie_pipeline/         # data.gov.ie organisation-link builder
│   └── datacatalogue_pipeline/     # datacatalogue.gov.ie organisation-link builder
│
├── scripts/                       # Helper and admin scripts — see scripts/README.md
│
└── public/                        # Public-facing output files, served via GitHub Pages
    ├── README.md                    # Data hub (browsable entry point)
    ├── GET_THE_DATA.md              # Non-technical CSV download guide
    ├── QUICKSTART.md                # Developer quickstart with runnable example
    ├── DATA_QUALITY.md              # Data quality & contributing guide
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

The step sequence is in [`pipelines/foi_pipeline/pipeline.json`](pipelines/foi_pipeline/pipeline.json). That file and [`pipelines/foi_pipeline/steps/README.md`](pipelines/foi_pipeline/steps/README.md) are the authoritative references. The pipeline currently runs 28 steps. The count changes when data-quality issues are found and fixed. At a high level, each run moves through these phases:

1. Discovery: find public bodies, their websites, FOI pages, FOI contact emails and disclosure log pages.
2. Collection: find and download the disclosure files (PDFs and spreadsheets) that the disclosure log pages link to.
3. Extraction and normalization: convert files to structured rows, detect and repair header rows, and normalize cell values and dates.
4. Canonicalization: map raw columns to canonical FOI fields, normalize status values and remove duplicate records.
5. Export: `export_status` merges every step's output into the consolidated status report and the public JSON files. `generate_topics` and `db_upload` run last.

`export_status` is the critical merge step. If data is missing on the website, first make sure that `export_status` ran.

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

Manual corrections in a step's `override.json` are marked `"source_method": "manual"` and `"overridden": true`. Later automated runs never overwrite them. Add or edit a record and commit it to git. The pipeline then skips that body for that step. See [`pipelines/foi_pipeline/AGENTS.md#override-system`](pipelines/foi_pipeline/AGENTS.md#override-system) for the full mechanism, including the column-mapping overrides for each file.

## Data Outputs

All files in the `public/` directory are safe for direct use. There are two tiers:

### Curated Linked Data datasets

The curated datasets follow 3 to 4 star Linked Data practices. They are Public Bodies, FOI Disclosures, FOI Request Files, Who Does What, data.gov.ie Links, lobbying.ie Links, Staff Numbers, Public Body Actions, Motions and Transport Policies. They are published as JSON-LD and CSV under `public/latest/<dataset>/` (the newest release) and `public/vX.Y.Z/<dataset>/` (immutable snapshots for each version). Transport Policies is the exception: it has CSV only. Each dataset has its own `README.md` that documents its data model, versioning and provenance. See the table in [Get the Data](#get-the-data) above. The shared technical-reference files are:

- `public/catalog/`: DCAT-AP 3.0 dataset metadata in RDF/Turtle, one `.ttl` file for each dataset.
- `public/schemas/`: JSON Schema files for validation, one for each dataset.
- `public/vocabularies/`: controlled vocabularies (`body-type.csv`, `foi-scope.csv`).
- `public/LICENSE`: the CC-BY 4.0 license for the public data.
- `public/CHANGELOG.md`: the version history.

### Raw pipeline outputs

These unversioned files are written directly to `public/` on every pipeline run:

- `pipeline-data.json`: consolidated status for all public bodies. The pipeline updates it on each run.
- `foi-disclosures.json`: all extracted FOI request records with full details.
- `disclosure-files.json`: all discovered disclosure document URLs.
- `topics.json`: topic groupings with the FOI records that matched.

### Database Schema

The pipeline populates a libSQL database with the following tables:

- `public_bodies` - Core public body information
- `disclosure_files` - Disclosure document metadata
- `foi_disclosures` - FOI request records
- `topics` - Topic definitions
- `disclosure_topic_matches` - Links between disclosures and topics

The canonical schema is defined in [`public/schema.sql`](public/schema.sql).

## Publishing

`data.publicinformation.ie` is served by GitHub Pages from the `public/` directory. The `deploy-pages.yml` workflow deploys it. Every push to `main` that touches `public/**` uploads `public/` as a Pages artifact and deploys it. A manual `workflow_dispatch` run deploys on demand. Set the custom domain in the repository Settings, under Pages, with source "GitHub Actions". This requires the repository to be public. Review the generated public-data diff before you merge to `main`, because the merge publishes the data. See [`AGENTS.md`](AGENTS.md#pages-publishing) for details.

Hosting policy: this project prefers EU-based service providers. GitHub is a deliberate, temporary interim host. See [`AGENTS.md`](AGENTS.md#hosting--service-providers) for the full policy.

## Contributing

Contributions are welcome. Follow these guidelines:

### Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a feature branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Run tests: `cd pipelines/foi_pipeline && uv run pytest tests/ -q`
6. Commit your changes with descriptive messages
7. Push to your fork and submit a pull request

### Code Style

- Follow the code style of the files around your change.
- Use type hints where they help.
- Keep each function focused on one purpose.
- For pipeline transform and canonicalization steps, read the core data-handling principle in [`AGENTS.md`](AGENTS.md). Do not guess at malformed values. Do not silently null or rewrite a field to make it fit. Write an error and let a human reviewer handle it.

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

If data is missing on the website, make sure that `export_status` ran and that `public/pipeline-data.json` contains data.

If a pipeline step fails, read the step's `errors.json`, then run the step again with `--force`.

```bash
# Check which steps have output
ls -la pipelines/foi_pipeline/steps/*/output.json

# Check for errors in a specific step
cat pipelines/foi_pipeline/steps/<step_name>/errors.json | python -m json.tool
```

See [`AGENTS.md`](AGENTS.md#troubleshooting-guide) for the full troubleshooting guide and decision tree.

## Architecture Decisions

The pipeline uses small, resumable and isolated steps. Each step is independently testable, can run again, and keeps manual overrides. Each step reads and writes plain JSON. The JSON is human-readable, diffable and validated against a schema with `output_schema.json`. The steps feed a libSQL database. libSQL uses HTTP, is compatible with SQLite, and suits static-site and serverless hosting.

## License

This project is licensed under the GNU Affero General Public License version 3.0 (AGPL-3.0) - see the [LICENSE](LICENSE) file for details.

The AGPL-3.0 license applies when someone uses a modified version of this software over a network, such as a web service. That use requires the source code to be available to users. This keeps the data processing pipeline open and accessible to all.

## Support

### Reporting Issues

Please report issues on the GitHub repository:

- [Issues](https://github.com/publicinformation-ie/publicinformation-data/issues)

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

- [PublicInformation.ie Website](https://www.publicinformation.ie): the frontend website that uses this data.
- [foi.gov.ie](https://foi.gov.ie): the official Irish FOI portal and the source of the public body list.

## Acknowledgments

- The Irish Government for maintaining the official FOI portal and public body registry
- All contributors who have submitted corrections and improvements
- The open source community for the tools and libraries that make this project possible

---

*For the most up-to-date technical information, see [AGENTS.md](AGENTS.md).*

*Licensed under [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0)*
