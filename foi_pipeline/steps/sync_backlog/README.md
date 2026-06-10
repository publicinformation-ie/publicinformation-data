# sync_backlog

## What this step does

Syncs evaluation issues from pipeline steps to Codeberg Issues as a backlog tracking mechanism.

This step:
1. Collects and scores issues from all step `eval/issues.json` files
2. Ensures required labels exist on the Codeberg repository
3. Fetches existing open pipeline issues from Codeberg
4. Reconciles: creates new issues, updates changed ones, closes resolved ones

## Input

- Reads `eval/issues.json` from each step directory in the pipeline
- Uses `pipeline.json` to determine step order for scoring

## Output

- `output.json`: Statistics on sync operations (created, updated, closed, skipped counts)
- Writes to Codeberg Issues API (if `CODEBERG_SYNC_ENABLED=true`)

## Notable files

- `run.py`: Core logic (issue collection, scoring, label management, reconciliation)
- `process.py`: CLI entry point

## Rate Limiting

This step uses a rate-limited session wrapper to avoid 429 errors from Codeberg API.

### Configuration

- `CODEBERG_RATE_LIMIT_DELAY`: Minimum delay in seconds between Codeberg API requests (default: 0.5)
  - This is on top of the global per-domain rate limiting from `lib/http_utils.py` (default: 0.2s)
  - Combined minimum delay: max(0.5, 0.2) = 0.5s for Codeberg
  - Ensures ~120 requests/minute maximum, well below Codeberg's 2000/5min limit

- `CODEBERG_SYNC_ENABLED`: Set to `false` to disable syncing (default: `true`)
- `CODEBERG_TOKEN`: Required for authentication to Codeberg API
- `CODEBERG_REPO`: Repository to sync to (default: `publicinformation/publicinformation-data`)

### Retry Behavior

- On 429 (Too Many Requests), respects `Retry-After` header (defaults to 5 seconds)
- Retries up to 3 times before failing
- On connection errors, uses exponential backoff (1s, 2s, 4s)

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CODEBERG_TOKEN` | Yes | - | Codeberg API token for authentication |
| `CODEBERG_REPO` | No | `publicinformation/publicinformation-data` | Target repository |
| `CODEBERG_SYNC_ENABLED` | No | `true` | Set to `false` to skip syncing |
| `CODEBERG_RATE_LIMIT_DELAY` | No | `0.5` | Minimum seconds between requests |
