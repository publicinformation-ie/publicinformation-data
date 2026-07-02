# Scripts

For guidance on *which* script to reach for, see [AGENTS.md](AGENTS.md).

## file_issues.py

Triage view of all FOI disclosure pipeline files, grouped by issue type (errors + dropped-file detection), sourced from each step's `output.json`/`errors.json`. Runs entirely against local pipeline artifacts — no database needed.

### Usage

```bash
# Default: group by issue type -> public body -> file
uv run python -m scripts.file_issues

# Group by public body -> file, to surface the files contributing the most issues
uv run python -m scripts.file_issues --by-file

# Filters (apply in both modes)
uv run python -m scripts.file_issues --step verify_disclosure_files
uv run python -m scripts.file_issues --issue UnrecognizedDecisionStatus
uv run python -m scripts.file_issues --min-errors 5
```

`--by-file` is the one to use when hunting for outliers: a file with many small issue types spread across steps can rank low in the default (issue-type-first) view but still be the single biggest contributor overall.

## audit_disclosures.py

SQL-based data-quality audit of the **exported** `foi_disclosures` table (i.e. after `export_status` has run and data has landed in the DB), ranking source files by total error count across a fixed set of checks (blank descriptions, unparseable dates, decision_status containing a date, etc).

### Usage

```bash
PYTHONPATH=src python scripts/audit_disclosures.py --top 20
python scripts/audit_disclosures.py --check invalid_decision_date
python scripts/audit_disclosures.py --min-errors 5
```

Use this instead of `file_issues.py` when you want to check the DB as actually exported/deployed, rather than the pipeline's intermediate step artifacts.

## migrate_foi_ids_to_cso.py

One-time, idempotent migration that remaps all FOI/disclosure data onto the canonical CSO `public_body_id` namespace.

The FOI pipeline originally numbered public bodies by gov.ie scrape order; CSO later became the canonical body register (numbered alphabetically). Both ID ranges are 1000–1882, so old FOI IDs silently collided with different canonical CSO bodies. This script rebuilds the link by **folded name**: for every disclosure step output (and the hand-maintained `override.json` files) it rewrites each record's `public_body_id` and `name` to the canonical CSO body, then dedups the crawl artifacts.

It is **idempotent and safe to re-run**: a record that is already canonical maps to itself, and a second full run reports 0 remaps and 0 dedup removals. If any record name fails to resolve to a canonical CSO body, the script aborts with a non-zero exit and names the offending value — it never attaches records to the wrong body silently.

### Usage

```bash
# Preview the per-file plan without writing anything:
PYTHONPATH=src python scripts/migrate_foi_ids_to_cso.py --dry-run

# Apply the migration in place:
PYTHONPATH=src python scripts/migrate_foi_ids_to_cso.py
```

`PYTHONPATH=src` is required so the script can import `lib.file_utils` (shared `read_json`/`write_json`).

## admin-corrections.mjs

Interactive CLI for reviewing and actioning pending user-submitted corrections from the public API.

### Prerequisites

Copy `.env.admin.example` to `.env.admin` in the repo root and fill in the values:

```bash
cp .env.admin.example .env.admin
# edit .env.admin and set ADMIN_API_KEY
```

The script requires these three variables in `.env.admin`:

| Variable | Description |
|---|---|
| `CORRECTIONS_URL` | Base URL of the corrections API |
| `ADMIN_API_KEY` | Secret key for authenticating admin API requests |
| `SIGN_KARMA_URL` | URL of the karma-signing service |

The script also reads pipeline `output.json` files to enrich override records, so you should have a recent pipeline run locally before accepting corrections that involve `foi_email`, `disclosures_page`, or `foi_page` fields.

### Usage

```bash
node scripts/admin-corrections.mjs
```

### What it does

For each pending correction, you are shown:

- The public body name and ID
- The field being corrected (`website_url`, `foi_page`, `foi_email`, or `disclosures_page`)
- The current value and the user's suggested value
- The submitter's DID, IP address, and submission timestamp

You then choose:

- **`a` — Accept**: writes an override record to `foi_pipeline/steps/<step>/override.json`, signs +10 karma for the submitter, and marks the correction accepted in the API
- **`r` — Reject**: optionally provide a reason, marks the correction rejected in the API
- **`s` — Skip**: leaves the correction pending for later review

### After accepting corrections

The script prints the next steps, which are roughly:

```bash
git add foi_pipeline/steps/<step>/override.json
git commit -m "feat: accept correction for <field> (body <id>)"
git push
# re-run export_status step and redeploy pipeline data to CDN
```

Override files take effect when the pipeline is re-run — accepted corrections bypass the normal pipeline logic for that body/field combination.

## trace_file.py

Trace a single disclosure file URL through the FOI pipeline.

### Usage

```bash
python scripts/trace_file.py --url "https://example.gov.ie/disclosures.xlsx"
```

### Description

Traces a file through 8 pipeline steps from `transform_disclosure_files` to `extract_disclosures_deduplicate`.

For each step, outputs:
- Step name (35 chars, left-aligned)
- Percentage (4 chars, right-aligned)
- Status: SUCCESS (100%), PARTIAL (0% < p < 100%), or FAILED (0%)

### Exit Codes

- `0`: Success (file traced through all steps)
- `1`: File URL not found in first step output
- `2`: Invalid arguments

### Example

```bash
$ python scripts/trace_file.py --url "https://health.gov.ie/foi-disclosures-2024.xlsx"
transform_disclosure_files             100% SUCCESS
normalize_disclosure_cells              100% SUCCESS
extract_disclosures_detect_header_row  100% SUCCESS
extract_disclosures_normalize_header   100% SUCCESS
extract_disclosures_normalize_rows      100% SUCCESS
extract_disclosures_canonicalize       100% SUCCESS
extract_disclosures_canonicalize_rows   100% SUCCESS
extract_disclosures_deduplicate        100% SUCCESS
```
