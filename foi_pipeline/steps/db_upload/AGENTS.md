# db_upload - Agent Documentation

The final pipeline step that writes all pipeline data to a libSQL database.

## Database Configuration

The target database is controlled by environment variables (set in `.env.admin`):

| Variable | Local dev | Production |
|----------|-----------|------------|
| `DATABASE_URL` | `file:./local.db` | Bunny dashboard connection URL (`https://...`) |
| `DATABASE_AUTH_TOKEN` | *(leave empty)* | Bunny auth token |

## Implementation Details

`../../scripts/db_client.py` abstracts sqlite3 (local) and libSQL HTTP v2 (remote) behind a single `DbClient` interface.

The canonical schema lives at `../../public/schema.sql`.

## Database Tables

The step clears and re-populates six pipeline-data tables:
- `public_bodies`
- `disclosure_files`
- `foi_disclosures`
- `topics`
- Plus supporting tables for relationships

## Running with Local SQLite

To populate a local SQLite database from existing pipeline output:

```bash
DATABASE_URL=file:./local.db python process.py --from export_status
```

## Running This Step

```bash
# From the foi_pipeline directory
cd ..
PYTHONPATH=. python steps/db_upload/process.py \
  --input steps/generate_topics/output.json \
  --output steps/db_upload/output.json \
  --force
```

> **Note:** This step requires the `DATABASE_URL` environment variable to be set. For production, also set `DATABASE_AUTH_TOKEN`.
