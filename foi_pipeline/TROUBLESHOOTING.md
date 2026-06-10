# Troubleshooting Guide

This document contains troubleshooting information for common FOI pipeline issues. See also [DATA_FLOW.md](../DATA_FLOW.md) for the end-to-end data flow overview.

## export_status/output.json not generated

If the website's data-status page is empty:

1. Check if export_status/output.json exists:
   ```bash
   ls -la foi_pipeline/steps/export_status/output.json
   ```

2. If missing, run the export_status step manually:
   ```bash
   cd foi_pipeline
   PYTHONPATH=. python steps/export_status/process.py \
     --input steps/find_public_bodies/output.json \
     --output steps/export_status/output.json \
     --force
   ```

3. If that fails, check:
   - Does find_public_bodies/output.json exist?
   - Does pipeline.json exist in the foi_pipeline directory?
   - Are there any Python errors?

## Data not appearing on website

The website uses a prebuild script that copies export_status/output.json. If data is missing:

1. The prebuild script has a fallback chain:
   - First tries: `../foi_pipeline/steps/export_status/output.json`
   - Falls back to: `../foi_pipeline/steps/find_public_bodies/output.json`
   - Final fallback: Creates empty JSON `{metadata: {}, public_bodies: []}`

2. Check which file is being used:
   ```bash
   python3 -c "import json; data=json.load(open('../publicinformation-web/src/data/pipeline-status.json')); print('Source step:', data['metadata'].get('step'))"
   ```

3. If showing "find_public_bodies", the export_status step hasn't been run yet.

## short_name missing

If public bodies show without short names (e.g., "Department of Health ()"):

1. The export_status step generates short_name automatically if missing
2. If using find_public_bodies directly (fallback), short_name won't be present
3. The website handles missing short_name gracefully by omitting the span

To ensure short_name is present, run the export_status step.

## Pipeline Output Locations

Each step writes its output to:
- `<step_directory>/output.json` - Main output data
- `<step_directory>/status.json` - Step execution status
- `<step_directory>/errors.json` - Any errors encountered
- `<step_directory>/pipeline-status.json` - Copy of output (for debugging)

## Common Issues

### Codeberg 429 Rate Limit Errors in sync_backlog

If you see `429 Too Many Requests` errors from Codeberg API:

1. **Check the rate limit configuration:**
   - Default delay is 1.0 second between requests (60 requests/minute)
   - Codeberg's limit is 2000 requests per 5 minutes
   - The default should be well within limits

2. **Enable detailed logging:**
   The sync_backlog step now logs every request with timestamps:
   ```
   2026-06-10 12:34:56.789 [sync_backlog.rate_limit] INFO: [1] Attempt 1/4 - GET https://codeberg.org/api/v1/repos/.../labels (delay_before=1.000s)
   2026-06-10 12:34:57.890 [sync_backlog.rate_limit] INFO: [1] Response - GET https://codeberg.org/api/v1/repos/.../labels | Status=200 | Time=1.101s | RateLimit=2000 | Remaining=1999
   ```
   
   To see these logs, run with Python logging enabled:
   ```bash
   cd foi_pipeline
   PYTHONPATH=. python steps/sync_backlog/process.py --output steps/sync_backlog/output.json --force
   ```

3. **Adjust the rate limit delay:**
   Increase `CODEBERG_RATE_LIMIT_DELAY` if needed:
   ```bash
   export CODEBERG_RATE_LIMIT_DELAY=2.0  # 2 seconds between requests
   ```

4. **Check for burst requests:**
   The most common cause is multiple sync_backlog processes running concurrently, or a bug causing requests to burst. The logging will reveal this.

5. **Verify Retry-After header handling:**
   When a 429 is received, the code respects the `Retry-After` header. The logs will show:
   ```
   WARNING: [N] Rate limited! Retry-After=5s, attempt=1/4
   INFO: [N] Sleeping for 5s before retry...
   ```

### All status show as "not_attempted"

This means only `find_public_bodies` has been run. Run the full pipeline or at minimum through `export_status`.

### Scripts being run multiple times by Vibe CLI

Use the process script (`process.py`) rather than calling individual step scripts directly. The process script handles staleness checks.

```bash
# Correct: Use process script
cd foi_pipeline && python process.py --force

# Avoid: Direct step execution (triggers Vibe re-runs)
cd foi_pipeline && python steps/export_status/process.py --force
```

## camelot-py: ghostscript not found

camelot-py requires the `ghostscript` system package. If you see errors like
`ghostscript not installed` or `FileNotFoundError: gs`, install it:

```bash
brew install ghostscript   # macOS
apt-get install ghostscript python3-tk  # Debian/Ubuntu
```

The pipeline degrades gracefully if ghostscript is absent — `_extract_with_camelot_stream`
returns `None` and pdfplumber output is used as-is.
