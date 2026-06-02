> **NOTE**: This document refers to the old `publicinfo-prototype` subdirectory structure.
> The website has been moved to the separate `publicinformation-web` repository at
> /Users/gingertechie/dev/publicinformation/publicinformation-web/
> 
> References to `publicinfo-prototype` in this document should be read as `../publicinformation-web`.

# Design: export_status pipeline step

**Date:** 2026-05-04
**Status:** Approved

## Problem

The Astro `data-status` page displays a table of every public body's pipeline completion status. It reads `publicinfo-prototype/src/data/pipeline-status.json`, which is copied from the pipeline during `prebuild`. The copy currently points at `find_public_bodies/output.json` — the very first step — which contains only the initial skeleton with every status field set to `"not_attempted"`. The nine subsequent pipeline steps each write their own `output.json` but nothing ever merges those results into the consolidated format the Astro page expects. The page therefore always renders a table full of grey dashes regardless of how much of the pipeline has run.

## Decision

Replace the stub `import_disclosures` step with a new final step, `export_status`, that reads all preceding step outputs and merges them into a single consolidated JSON. The Astro `prebuild` hook copies this step's output instead of the first step's output. No changes to `data-status.astro`.

## Architecture

```
foi_pipeline/steps/export_status/process.py   ← replaces import_disclosures
foi_pipeline/pipeline.json                     ← last entry renamed
publicinfo-prototype/package.json              ← prebuild cp path updated
```

The export step honours the orchestrator's step contract (`--input`, `--output`, `--force` args) but is a fan-in step: it derives the `steps/` directory from its own `__file__` path, reads `pipeline.json` for step order, and loads each preceding step's `output.json` in sequence. Steps whose `output.json` is absent are silently skipped (field remains `"not_attempted"`).

## Field mapping

The base is `find_public_bodies/output.json`, which already contains the full `status` skeleton for every public body. Each subsequent step enriches it:

| Step | Field(s) updated | Logic |
|------|-----------------|-------|
| `validate_websites` | `website_url.status` | `is_reachable` → `"success"` / `"failed"` |
| `find_foi_pages` | `foi_page.url`, `foi_page.status` | `foi_page_url`; presence in results → `"success"` |
| `check_foi_pages` | `foi_page.status` | refines prior: `is_reachable` → `"success"` / `"failed"` |
| `get_foi_emails` | `foi_email.email`, `foi_email.status` | `foi_email`; `email_status == "found"` → `"success"`, else `"failed"` |
| `find_disclosure_pages` | `disclosures_page.url`, `disclosures_page.status` | `disclosure_page_url`; presence → `"success"` |
| `find_disclosure_files` | `disclosure_files.total`, `.valid`, `.failed`, `.status` | count results per body; `total > 0` → `"success"`, else `"failed"`; until `transform_disclosure_files` is implemented, `valid = total`, `failed = 0` |
| `extract_disclosures` | `foi_requests.valid`, `.errors`, `.status` | schema TBD — skipped until step is implemented |

**Merge rule:**
- Step `output.json` exists, body in results → apply field updates above
- Step `output.json` exists, body absent from results → mark that status field `"failed"` (step ran but produced nothing for this body)
- Step `output.json` absent → leave field as `"not_attempted"`

`find_foi_pages` and `check_foi_pages` both write to `foi_page.status`. Processing in `pipeline.json` order is correct: `find_foi_pages` sets `"success"` (URL found), then `check_foi_pages` refines to the reachability result.

## Output format

The export step writes the same structure as `find_public_bodies/output.json` — a `public_bodies` array with the nested `status` object per body — which `data-status.astro` already consumes without modification.

```json
{
  "metadata": { "step": "export_status", "completed_at": "<ISO-8601>" },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "...",
      "short_name": "...",
      "official_website_url": "...",
      "status": {
        "website_url":      { "url": "...", "status": "success|failed|not_attempted" },
        "foi_page":         { "url": "...", "status": "success|failed|not_attempted" },
        "foi_email":        { "email": "...", "status": "success|failed|not_attempted" },
        "disclosures_page": { "url": "...", "status": "success|failed|not_attempted" },
        "disclosure_files": { "total": 0, "valid": 0, "failed": 0, "status": "success|failed|not_attempted" },
        "foi_requests":     { "valid": 0, "errors": 0, "status": "success|failed|not_attempted" }
      }
    }
  ]
}
```

## Prebuild hook change

```bash
# Before
cp ../foi_pipeline/steps/find_public_bodies/output.json src/data/pipeline-status.json

# After
cp ../foi_pipeline/steps/export_status/output.json src/data/pipeline-status.json
```

The fallback on copy failure is unchanged.

## Files changed

| Action | Path |
|--------|------|
| Rename directory | `foi_pipeline/steps/import_disclosures/` → `foi_pipeline/steps/export_status/` |
| Rewrite | `foi_pipeline/steps/export_status/process.py` |
| Update | `foi_pipeline/pipeline.json` |
| Update | `publicinfo-prototype/package.json` |
