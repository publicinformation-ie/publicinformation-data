# Code Review: sync_backlog Rate Limiting Issues

**Date:** 2026-06-10  
**Reviewer:** Mistral Vibe  
**Issue:** Persistent 429 rate-limit errors from Codeberg API

---

## Executive Summary

The `sync_backlog` step was experiencing 429 (Too Many Requests) errors from Codeberg API despite having rate limiting in place. After careful code review, I've identified that while the rate limiting logic was fundamentally sound, **there was no visibility into what was happening** - no logging of individual requests, response statuses, or rate limit headers.

### Key Changes Made

1. **Added comprehensive timestamped logging** for every HTTP request and response
2. **Increased default rate limit delay** from 0.5s to 1.0s (60 requests/minute instead of 120)
3. **Added logging of Codeberg rate limit headers** (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`)
4. **Added global request counter** for tracking total API calls
5. **Added summary logging** at the end of each run
6. **Updated documentation** with new default values and troubleshooting info

---

## Code Review Findings

### What Was Working Correctly

1. **Rate limiting infrastructure was in place:** The `RateLimitedSession` class properly used:
   - Per-domain rate limiting via `lib/http_utils.get_rate_limit_delay()`
   - Codeberg-specific override with `CODEBERG_RATE_LIMIT_DELAY` env var
   - Automatic retry on 429 with `Retry-After` header support
   - Exponential backoff on connection errors

2. **The math was correct:** `max(self.base_delay, get_rate_limit_delay(domain))` ensured Codeberg always had at least the configured delay

3. **Retry logic was functional:** On 429, it would sleep for `Retry-After` (default 5s) and retry up to 3 times

### What Was Missing

1. **No logging at all** - Impossible to debug what was happening
2. **No visibility into rate limit headers** - Couldn't see what Codeberg was telling us
3. **Default delay may have been too aggressive** - 0.5s (120 req/min) might be too close to Codeberg's limits in practice

### Could the Rate Limit Be Exceeded?

**Yes, in the following scenarios:**

1. **Multiple concurrent sync_backlog processes:** If two instances run simultaneously, each would apply its own 0.5s delay, resulting in requests every 0.25s (240 req/min), exceeding Codeberg's limits.

2. **Other code making Codeberg requests:** If other parts of the pipeline or system were also hitting Codeberg API, the shared rate limit could be exhausted.

3. **Clock skew or timing issues:** The `get_rate_limit_delay()` from `http_utils.py` uses system time, and the `time.sleep()` might not be perfectly precise.

4. **Codeberg's actual limits:** While Codeberg documents 2000 requests per 5 minutes, the actual enforced limit might be lower, or there might be per-endpoint limits.

### Why 429 Errors Persisted

Without logging, it was impossible to determine:
- How many requests were being made
- When each request was sent
- What the response status was
- What rate limit headers Codeberg was returning
- Whether retries were happening
- Whether multiple processes were running

The most likely cause is **scenario #1 above** - multiple processes or bursts of requests.

---

## Changes Implemented

### 1. Added Comprehensive Logging (`run.py`)

```python
# Configure logging for rate limit debugging
logger = logging.getLogger("sync_backlog.rate_limit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)
```

**Log format:**
```
2026-06-10 12:34:56.789 [sync_backlog.rate_limit] INFO: [1] Attempt 1/4 - GET https://codeberg.org/api/v1/repos/.../labels (delay_before=1.000s)
2026-06-10 12:34:57.890 [sync_backlog.rate_limit] INFO: [1] Response - GET https://codeberg.org/api/v1/repos/.../labels | Status=200 | Time=1.101s | RateLimit=2000 | Remaining=1999
```

### 2. New Logging Methods in `RateLimitedSession`

- `_log_request()`: Logs each request with sequence number, attempt number, method, URL, and delay applied
- `_log_response()`: Logs each response with status code, elapsed time, and all rate limit headers
- Special warning logs for 429 responses
- Error logs for connection errors and max retries exceeded

### 3. Global Request Counter

```python
_request_counter = 0  # Global across all RateLimitedSession instances
```

This allows tracking the total number of requests made during a run, even if multiple session instances exist.

### 4. Increased Default Delay

Changed from:
```python
self.base_delay = base_delay or float(os.getenv("CODEBERG_RATE_LIMIT_DELAY", "0.5"))
```

To:
```python
self.base_delay = base_delay or float(os.getenv("CODEBERG_RATE_LIMIT_DELAY", "1.0"))
```

This ensures ~60 requests/minute maximum, providing more headroom below Codeberg's 2000/5min limit.

### 5. Rate Limit Summary Function

Added `get_rate_limit_summary()` to provide a summary at the end of each run:
```python
def get_rate_limit_summary():
    return {
        "total_requests": _request_counter,
        "note": "Check logs for detailed request/response timing and rate limit headers"
    }
```

### 6. Documentation Updates

- Updated `README.md` with new default delay value (1.0s)
- Added note about the increase from 0.5s to 1.0s
- Updated environment variables table
- Added troubleshooting section to `TROUBLESHOOTING.md`

---

## How to Use the New Logging

### Running with Logging

Simply run the step normally - logging is now enabled by default:

```bash
cd foi_pipeline
PYTHONPATH=. python steps/sync_backlog/process.py \
  --output steps/sync_backlog/output.json \
  --force
```

### Sample Output

```
2026-06-10 12:34:56.123 [sync_backlog.rate_limit] INFO: RateLimitedSession initialized with base_delay=1.0s, max_retries=3
2026-06-10 12:34:56.124 [sync_backlog.rate_limit] INFO: [1] Attempt 1/4 - GET https://codeberg.org/api/v1/repos/publicinformation/publicinformation-data/labels (delay_before=1.000s)
2026-06-10 12:34:57.234 [sync_backlog.rate_limit] INFO: [1] Response - GET https://codeberg.org/api/v1/repos/publicinformation/publicinformation-data/labels | Status=200 | Time=1.110s | RateLimit=2000 | Remaining=1999 | Reset=300
2026-06-10 12:34:57.235 [sync_backlog.rate_limit] INFO: [2] Attempt 1/4 - POST https://codeberg.org/api/v1/repos/publicinformation/publicinformation-data/labels (delay_before=1.000s)
2026-06-10 12:34:58.345 [sync_backlog.rate_limit] INFO: [2] Response - POST https://codeberg.org/api/v1/repos/publicinformation/publicinformation-data/labels | Status=201 | Time=1.110s | RateLimit=2000 | Remaining=1998 | Reset=300
2026-06-10 12:34:58.346 [sync_backlog.rate_limit] INFO: Rate limit summary: {'total_requests': 42, 'note': 'Check logs for detailed request/response timing and rate limit headers'}
Collecting issues from eval outputs...
Found 15 issues across 5 evaluated steps
Ensuring labels exist on Codeberg...
Fetching open Codeberg issues...
Found 20 open pipeline issues on Codeberg
Reconciling...
Done: created=2 updated=5 closed=1 skipped=12
Total API requests made: 42
```

### What to Look For

1. **Request frequency:** Check the timestamps between requests. They should be at least 1.0s apart.
2. **Rate limit headers:** Look at `RateLimit`, `Remaining`, and `Reset` values from Codeberg.
3. **429 responses:** If you see `Status=429`, check the `RetryAfter` header and the warning messages.
4. **Multiple processes:** If request numbers jump (e.g., [1], [2], [100]), multiple instances might be running.

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEBERG_RATE_LIMIT_DELAY` | `1.0` | Minimum seconds between Codeberg API requests |
| `CODEBERG_SYNC_ENABLED` | `true` | Set to `false` to disable syncing |
| `CODEBERG_TOKEN` | - | Required: Codeberg API token |
| `CODEBERG_REPO` | `publicinformation/publicinformation-data` | Target repository |

### Recommended Settings

For conservative rate limiting:
```bash
export CODEBERG_RATE_LIMIT_DELAY=2.0  # 30 requests/minute
```

For debugging:
```bash
export CODEBERG_RATE_LIMIT_DELAY=0.1  # Only for testing, will likely hit 429
```

---

## Verification Checklist

- [x] Code compiles without syntax errors
- [x] Logging is configured with timestamps and millisecond precision
- [x] Every request is logged with sequence number
- [x] Every response is logged with status and rate limit headers
- [x] 429 responses trigger warning logs
- [x] Default delay increased to 1.0s
- [x] Documentation updated
- [x] Troubleshooting guide updated
- [ ] User to test with actual Codeberg API calls

---

## Files Modified

1. `foi_pipeline/steps/sync_backlog/run.py` - Added comprehensive logging and increased default delay
2. `foi_pipeline/steps/sync_backlog/process.py` - Added summary logging
3. `foi_pipeline/steps/sync_backlog/README.md` - Updated documentation
4. `foi_pipeline/TROUBLESHOOTING.md` - Added Codeberg 429 troubleshooting section

---

## Next Steps

1. **Run the step with the new logging** and observe the output
2. **Check for 429 errors** in the logs
3. **If 429 errors persist**, check:
   - Are multiple processes running? (look for overlapping request numbers)
   - What does Codeberg's `Remaining` header show? (is it going to 0?)
   - Is the delay between requests actually 1.0s? (check timestamps)
4. **Increase `CODEBERG_RATE_LIMIT_DELAY`** if needed (try 2.0 or higher)
5. **Check for concurrent execution** - ensure only one sync_backlog is running at a time

---

## Technical Details

### Rate Limit Calculation

The actual delay before each request is:
```
delay = max(base_delay, DEFAULT_RATE_LIMIT_DELAY - elapsed_since_last_request)
```

For Codeberg:
- `base_delay` = `CODEBERG_RATE_LIMIT_DELAY` or 1.0 (default)
- `DEFAULT_RATE_LIMIT_DELAY` = 0.2s (from `lib/http_utils.py`)
- So effective delay = `max(1.0, 0.2 - elapsed)` = 1.0s minimum

### Retry Logic on 429

When a 429 is received:
1. Parse `Retry-After` header (default: 5 seconds)
2. Sleep for `Retry-After` seconds
3. Reset the timer
4. Retry the request (up to `max_retries` times)
5. On success, return the response
6. On final failure, raise the exception

The retry delay is **in addition to** the normal rate limit delay, so after a 429, the next attempt will wait `Retry-After + base_delay` before making the request.

---

**Generated by Mistral Vibe.**
