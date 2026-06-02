# PublicInformation.ie - Data Pipeline

**Open data pipeline for Irish Freedom of Information (FOI) public body information**

[![Codeberg](https://codeberg.org/gingertechie/publicinformation-data/badge)](https://codeberg.org/gingertechie/publicinformation-data)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains the data processing pipeline for [PublicInformation.ie](https://publicinformation.ie), a project that tracks and publishes Freedom of Information (FOI) data from Irish public bodies. The pipeline extracts, transforms, and loads data about FOI pages, email addresses, disclosure logs, and disclosure files from hundreds of Irish government and public sector websites.

## Features

- **Comprehensive Coverage**: Processes data from all Irish public bodies subject to FOI legislation
- **Multi-step Pipeline**: 15 sequential processing steps from discovery to database upload
- **Automated Extraction**: Scrapes websites for FOI pages, contact information, and disclosure documents
- **Data Normalization**: Standardizes and cleans extracted data for consistency
- **Override System**: Manual corrections preserved across automated runs
- **Open Output**: Publishes consolidated JSON data files for public use
- **Database Integration**: Populates a libSQL database with structured FOI data

## Quick Start

### Get the Data

The latest processed data is available in the `public/` directory:

| File | Description | Size (approx.) |
|------|-------------|---------------|
| [`public/pipeline-data.json`](public/pipeline-data.json) | Consolidated status of all public bodies | ~150 KB |
| [`public/foi-disclosures.json`](public/foi-disclosures.json) | All extracted FOI request records | ~38 MB |
| [`public/disclosure-files.json`](public/disclosure-files.json) | All discovered disclosure document URLs | ~200 KB |
| [`public/topics.json`](public/topics.json) | Topic groupings for FOI records | ~2.5 MB |

These files are regenerated automatically when the pipeline runs and are safe to use directly.

### Run the Pipeline Locally

```bash
# Clone the repository
git clone https://codeberg.org/gingertechie/publicinformation-data.git
cd publicinformation-data

# Run the full pipeline
cd foi_pipeline
python process.py --force
```

This will process all 15 steps and generate output files in `foi_pipeline/steps/<step_name>/output.json`.

The consolidated output appears in `foi_pipeline/steps/export_status/output.json` and is copied to `public/pipeline-data.json`.

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
uv pip install -r foi_pipeline/requirements.txt
```

Or using pip directly:

```bash
pip install requests beautifulsoup4 lxml tablib sqlparse python-dotenv
```

### Environment Configuration

For database operations, create a `.env.admin` file from the example:

```bash
cp .env.admin.example .env.admin
# Edit .env.admin with your database credentials
```

Required variables for production database upload:
- `DATABASE_URL`: libSQL database connection URL
- `DATABASE_AUTH_TOKEN`: Bunny/CDN authentication token

For local development, the default SQLite database (`local.db`) is used.

## Usage

### Pipeline Commands

| Command | Description |
|---------|-------------|
| `python process.py --force` | Run the complete pipeline from scratch |
| `python process.py --from export_status --force` | Run from a specific step |
| `python process.py --from generate_topics` | Run from a step without forcing |

### Individual Step Execution

Each step can be run independently:

```bash
cd foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force
```

### Running Tests

```bash
cd foi_pipeline
uv run pytest tests/ -q
```

### Common Workflows

**Update all data and rebuild website:**
```bash
cd foi_pipeline
python process.py --force
cd ../publicinfo-prototype
npm run build
```

**Quick data refresh (from export_status):**
```bash
cd foi_pipeline
python process.py --from export_status --force
```

**Check data status:**
```bash
# Count public bodies
python3 -c "import json; d=json.load(open('foi_pipeline/steps/export_status/output.json')); print(f'Public bodies: {len(d[\"public_bodies\"])}')"

# Validate output structure
python3 -c "import json; d=json.load(open('public/pipeline-data.json')); print('Metadata:', d.get('metadata')); print('Sample body:', d['public_bodies'][0] if d['public_bodies'] else 'None')"
```

## Project Structure

```
publicinformation-data/
├── README.md                      # This file - project overview
├── AGENTS.md                      # Agent/automation documentation index
├── DATA_FLOW.md                   # End-to-end data flow documentation
├── .env.admin.example             # Environment configuration template
├── local.db                       # Local SQLite database (gitignored)
│
├── docs/                          # Project documentation and plans
│   ├── style-guide.md             # Code and documentation style guide
│   ├── deployment-migration-bunny.md
│   └── <date>-<description>.md    # Design documents and meeting notes
│
├── foi_pipeline/                  # Main pipeline directory
│   ├── AGENTS.md                  # Pipeline architecture and operations
│   ├── process.py                 # Pipeline orchestration engine
│   ├── pipeline.json              # Authoritative step order configuration
│   ├── requirements.txt           # Python dependencies
│   └── steps/                     # Pipeline step implementations
│       ├── AGENTS.md              # Step directory management guidelines
│       ├── README.md              # Complete step sequence documentation
│       └── <step_name>/           # Individual pipeline steps
│           ├── README.md          # Step-specific documentation
│           ├── process.py         # Step entry point
│           ├── output.json        # Step output data
│           ├── output_schema.json # JSON schema for validation
│           ├── override.json       # Manual override records
│           ├── errors.json        # Per-record errors and warnings
│           └── dirty_ids.json      # IDs with changed upstream data
│
├── scripts/                       # Helper and admin scripts
│   ├── README.md                  # Script documentation
│   ├── db_client.py               # Database client abstraction
│   └── admin-corrections.mjs      # Interactive correction review CLI
│
└── public/                        # Public-facing output files
    ├── pipeline-data.json         # Consolidated public body status
    ├── foi-disclosures.json       # All FOI request records
    ├── disclosure-files.json      # All disclosure document URLs
    └── topics.json                # Topic groupings
```

## Pipeline Steps

The FOI pipeline consists of 15 sequential steps:

| # | Step | Description |
|---|------|-------------|
| 1 | `find_public_bodies` | Scrapes the master list from foi.gov.ie |
| 2 | `resolve_website_urls` | Resolves gov.ie stub URLs to actual websites |
| 3 | `validate_websites` | Checks website reachability |
| 4 | `find_foi_pages` | Discovers FOI-specific pages on each website |
| 5 | `check_foi_pages` | Validates FOI page accessibility |
| 6 | `get_foi_emails` | Extracts FOI email addresses |
| 7 | `find_disclosure_pages` | Locates disclosure log pages |
| 8 | `find_disclosure_files` | Collects disclosure document links (PDFs, CSVs, etc.) |
| 9 | `transform_disclosure_files` | Processes files into structured data |
| 10 | `normalize_disclosure_cells` | Normalizes string cell values |
| 11 | `extract_disclosures_detect_header_row` | Detects header rows in spreadsheets |
| 12 | `extract_disclosures_canonicalize` | Maps raw columns to canonical FOI fields |
| 13 | `export_status` | **Critical**: Fan-in merge of all outputs (used by website) |
| 14 | `generate_topics` | Groups FOI records into keyword-defined topics |
| 15 | `db_upload` | Populates the libSQL database |

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

Some automated results may be incorrect due to website changes or scraping limitations. The override system allows manual corrections that are **never overwritten** by automated runs.

### How to Add an Override

1. Navigate to the step directory: `foi_pipeline/steps/<step_name>/`
2. Edit or create `override.json`
3. Add a complete record with `"source_method": "manual"` and `"overridden": true`
4. Commit the file to git

Example (`foi_pipeline/steps/find_foi_pages/override.json`):

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

## Data Outputs

### Public JSON Files

All files in the `public/` directory are safe for direct use:

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

## Contributing

Contributions are welcome! Please follow these guidelines:

### Getting Started

1. Fork the repository on Codeberg
2. Clone your fork locally
3. Create a feature branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Run tests: `cd foi_pipeline && uv run pytest tests/ -q`
6. Commit your changes with descriptive messages
7. Push to your fork and submit a pull request

### Code Style

- Follow the existing code style (see [`docs/style-guide.md`](docs/style-guide.md))
- Use type hints where appropriate
- Include docstrings for functions and modules
- Keep functions focused and single-purpose

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

1. Create a directory under `foi_pipeline/steps/<step_name>/`
2. Add a `process.py` entry point
3. Define an `output_schema.json` for validation
4. Create a `README.md` documenting the step
5. Add the step to `pipeline.json`
6. Implement a merger function if the step contributes to `export_status`
7. Update `foi_pipeline/steps/README.md`

## Troubleshooting

### Common Issues

**Data missing on website**:
- Ensure `export_status` has been run
- Check `public/pipeline-data.json` exists and has data
- Verify the website has been rebuilt

**All statuses show as "not_attempted"**:
- Only `find_public_bodies` has been run
- Run the full pipeline or at minimum through `export_status`

**Pipeline step fails**:
- Check the step's `errors.json` for specific errors
- Run the step manually with `--force` to retry
- Check network connectivity for scraping steps

### Debugging Commands

```bash
# Check which steps have output
ls -la foi_pipeline/steps/*/output.json

# View pipeline status
cat foi_pipeline/steps/export_status/status.json

# Check for errors in a specific step
cat foi_pipeline/steps/<step_name>/errors.json | python -m json.tool

# Validate output JSON
python3 -c "import json; json.load(open('foi_pipeline/steps/<step>/output.json'))" && echo "Valid JSON"
```

## Architecture Decisions

### Why a Multi-step Pipeline?

The pipeline is broken into small, focused steps because:

1. **Isolation**: Each step can be developed, tested, and debugged independently
2. **Resumability**: Steps can be re-run from any point without reprocessing everything
3. **Incremental Updates**: Only stale steps are re-run by default
4. **Override Preservation**: Manual corrections in earlier steps propagate through later steps
5. **Error Containment**: A failure in one step doesn't cascade to unrelated data

### Why JSON Output?

JSON is used for intermediate and final outputs because:

- Human-readable and easy to inspect
- Widely supported across programming languages
- Schema-validation available via `output_schema.json`
- Easy to version control and diff
- Works well with the website's JavaScript/TypeScript consumption

### Why libSQL?

The project uses libSQL (via Bunny) for the production database because:

- HTTP-based access suitable for serverless/edge environments
- SQL-compatible with SQLite familiar syntax
- Scalable and managed hosting available
- Works well with static site generators

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

### Reporting Issues

Please report issues on the Codeberg repository:

- [Issues](https://codeberg.org/gingertechie/publicinformation-data/issues)
- [Discussions](https://codeberg.org/gingertechie/publicinformation-data/discussions)

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

- [PublicInformation.ie Website](https://codeberg.org/gingertechie/publicinfo-prototype) - The frontend website that consumes this data
- [foi.gov.ie](https://foi.gov.ie) - The official Irish FOI portal (source of public body list)

## Acknowledgments

- The Irish Government for maintaining the official FOI portal and public body registry
- All contributors who have submitted corrections and improvements
- The open source community for the tools and libraries that make this project possible

---

*This README was last updated on June 2, 2026. For the most up-to-date information, see the project documentation in [AGENTS.md](AGENTS.md) and [DATA_FLOW.md](DATA_FLOW.md).*
