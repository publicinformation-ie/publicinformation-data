# db_upload

Populates the libSQL database from pipeline output. Runs last in the pipeline.

## What it does

1. Initialises the schema (idempotent — uses `CREATE TABLE IF NOT EXISTS`)
2. Clears the six pipeline-data tables in dependency order
3. Re-populates them from upstream step outputs

Tables written (in order):

| Table | Source step |
|---|---|
| `public_bodies` | `export_status` |
| `disclosure_files` | `find_disclosure_files` |
| `foi_disclosures` | `extract_disclosures_canonicalize` |
| `topics` | `generate_topics` |
| `topic_keywords` | `generate_topics` |
| `topic_disclosures` | `generate_topics` |

Tables **not** touched: `corrections`, `outreach_requests`, `outreach_messages`, `message_classifications`.

## Input

Reads directly from sibling step directories (not via `--input`):
- `export_status/output.json`
- `find_disclosure_files/output.json`
- `extract_disclosures_canonicalize/output.json`
- `generate_topics/output.json`
- `public/schema.sql`

## Output

`output.json` — metadata and row counts per table:

```json
{
  "metadata": { "step": "db_upload", "completed_at": "..." },
  "counts": {
    "public_bodies": 120,
    "disclosure_files": 450,
    "foi_disclosures": 1200,
    "topics": 8
  }
}
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `local.db` (SQLite file at repo root) | `file:./local.db` for SQLite, `https://…` for libSQL HTTP |
| `DATABASE_AUTH_TOKEN` | *(empty)* | Bearer token for libSQL HTTP (not needed for local SQLite) |

Set these in `.env.admin` (copy `.env.admin.example`).

## Local dev

```bash
DATABASE_URL=file:./local.db python foi_pipeline/steps/db_upload/process.py \
  --input foi_pipeline/steps/generate_topics/output.json \
  --output foi_pipeline/steps/db_upload/output.json \
  --force
```

Or run the full pipeline from `export_status` onward:

```bash
DATABASE_URL=file:./local.db python foi_pipeline/process.py --from export_status
```

## Notable files

- `process.py` — step entry point; also exports `upload_*` and `clear_pipeline_tables` functions used in tests
- `../../scripts/db_client.py` — sqlite3 / libSQL HTTP abstraction used by this step
- `../../public/schema.sql` — canonical schema; owned by this repo
