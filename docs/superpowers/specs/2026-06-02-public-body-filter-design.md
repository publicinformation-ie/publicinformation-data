# Public Body Filter Feature Design

**Date:** 2026-06-02  
**Status:** Draft  
**Author:** Mistral Vibe  
**Spec Location:** `docs/superpowers/specs/2026-06-02-public-body-filter-design.md`

---

## Overview

### Summary

Add a `--public-body <ID>` command-line flag to the FOI pipeline that filters all processing to a single specified public body. This allows developers to:

- Test and debug individual public body processing without running the full dataset
- Reprocess a single public body after fixes without affecting others
- Run individual steps against a specific public body for targeted investigation

### Goals

1. Add `--public-body <ID>` flag to `process.py` orchestration
2. Add `--public-body <ID>` flag to all individual step `process.py` scripts
3. Filter input data at each step to only process the specified public body
4. Maintain unchanged output file structure (array wrappers preserved)
5. Extract common CLI argument handling into a reusable library
6. Support incremental migration (steps updated one at a time)

### Non-Goals

1. Changing the output file structure or format
2. Modifying the pipeline step order or dependencies
3. Adding support for multiple public body IDs in a single run
4. Adding support for ranges or files of public body IDs
5. Changing the behavior of existing flags (`--force`, `--from`, `--verbose`, `--stop-on-error`)

---

## Background

### Current State

The FOI pipeline currently processes all public bodies through 16 sequential steps. Each step:

- Reads JSON input from the previous step's `output.json`
- Processes all records in that input
- Writes its own `output.json`

When running `python process.py --force`:
- All steps execute in order from `pipeline.json`
- Each step processes all public bodies
- No filtering capability exists

### Problem Statement

Debugging or testing a single public body requires:
- Running the full pipeline (time-consuming)
- Processing all ~500+ public bodies
- Manually extracting the single body of interest from output

This makes targeted development and troubleshooting inefficient.

### Motivation

A `--public-body` flag enables:

- **Faster iteration**: Test fixes against one body in seconds vs. minutes
- **Better debugging**: Isolate issues to specific public body processing
- **Targeted reprocessing**: Update one body after override changes
- **Step-level testing**: Run individual steps against specific bodies

---

## Proposed Design

### Architecture Overview

The filtering happens at **two levels**:

1. **Orchestration level** (`process.py`): Validates the public body exists and passes the flag to all steps
2. **Step level** (each `steps/*/process.py`): Each step reads its input, filters to the specified public body, processes only that record

```
┌─────────────────────────────────────────────────────────────────┐
│                    process.py (Orchestration)                       │
│  --public-body 1001                                                │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────┐                                              │
│  │ Validate body    │◄─────────────────────────────────────────────┤
│  │ 1001 exists in   │     No: exit with error                      │
│  │ find_public_     │                                              │
│  │ bodies/output    │                                              │
│  └────────┬────────┘                                              │
│           │                                                          │
│           ▼                                                          │
│  For each step:                                                      │
│    ┌─────────────────────┐                                          │
│    │ --public-body 1001  │◄── Passed to all steps                  │
│    │ --input (filtered)   │                                          │
│    │ --output output.json│                                          │
│    └──────────┬───────────┘                                          │
│                │                                                       │
│                ▼                                                       │
│    ┌─────────────────────┐                                          │
│    │ Step filters input  │                                          │
│    │ to body 1001        │                                          │
│    │ Processes only      │                                          │
│    │ that record        │                                          │
│    │ Writes output with  │                                          │
│    │ standard structure  │                                          │
│    └─────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Common CLI Library

A new module `foi_pipeline/scripts/cli_utils.py` centralizes common command-line argument handling and filtering logic.

#### Functions

```python
def add_common_args(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments common to most pipeline steps.
    
    Adds: --input, --output, --force, --verbose, --public-body
    """
```

```python
def filter_by_public_body(data: dict, public_body_id: int | None) -> dict:
    """
    Filter JSON data to only include records matching public_body_id.
    
    Handles both top-level 'public_bodies' and 'results' arrays.
    If public_body_id is None, returns data unchanged.
    
    Args:
        data: The input JSON data (dict with 'public_bodies' or 'results' key)
        public_body_id: The public body ID to filter for, or None
        
    Returns:
        Filtered data with same structure, containing only matching records
    """
```

```python
def validate_public_body(pipeline_dir: Path, public_body_id: int) -> bool:
    """
    Validate that public_body_id exists in find_public_bodies/output.json.
    
    Args:
        pipeline_dir: Path to the foi_pipeline directory
        public_body_id: The public body ID to validate
        
    Returns:
        True if the public body exists, False otherwise
    """
```

#### Usage in Steps

```python
from scripts.cli_utils import add_common_args, filter_by_public_body

def main():
    parser = argparse.ArgumentParser(description="Step description")
    add_common_args(parser)
    # Optionally add step-specific arguments
    args = parser.parse_args()
    
    input_data = read_json(args.input)
    
    if args.public_body is not None:
        input_data = filter_by_public_body(input_data, args.public_body)
        if not input_data.get("public_bodies", input_data.get("results", [])):
            print(f"No data for public_body_id={args.public_body} in input",
                  file=sys.stderr)
            sys.exit(0)
    
    # Process filtered data...
```

### Orchestration Changes (process.py)

#### New CLI Argument

```python
parser.add_argument("--public-body", type=int, default=None,
                    help="Filter all steps to only process this public body ID")
```

#### Validation Logic

Validation depends on whether we're starting from `find_public_bodies` or a later step:

```python
if args.public_body is not None:
    # If starting from find_public_bodies or before, no validation needed
    # (the step will handle it, possibly scraping all then filtering)
    first_step_index = 0
    try:
        current_step_index = config["steps"].index(args.from_step) if args.from_step else 0
    except ValueError:
        current_step_index = 0
    
    # Only validate if we're NOT starting from find_public_bodies
    if current_step_index > first_step_index:
        bodies_path = pipeline_dir / "steps" / "find_public_bodies" / "output.json"
        if not bodies_path.exists():
            print(f"Error: Cannot validate --public-body {args.public_body}: "
                  f"{bodies_path} does not exist. Run from find_public_bodies first.",
                  file=sys.stderr)
            sys.exit(1)
        
        bodies = read_json(bodies_path)
        if not any(b.get("public_body_id") == args.public_body 
                   for b in bodies.get("public_bodies", [])):
            print(f"Error: Public body {args.public_body} not found in "
                  f"find_public_bodies/output.json",
                  file=sys.stderr)
            sys.exit(1)
```

**Note**: When running from `find_public_bodies` (or with no `--from`), validation is skipped because `find_public_bodies` itself will handle the `--public-body` flag by either filtering existing output or scraping all bodies and then filtering.

#### Flag Passthrough

For each step command, append the flag:

```python
cmd = [
    sys.executable,
    str(step_dir / "process.py"),
    "--input", str(prev_out) if prev_out is not None else str(step_dir),
    "--output", str(step_out),
]
if args.force:
    cmd.append("--force")
if args.verbose:
    cmd.append("--verbose")
if args.public_body is not None:
    cmd.append("--public-body")
    cmd.append(str(args.public_body))
```

#### Special Handling for find_public_bodies

No special handling needed at the orchestration level. The `find_public_bodies` step itself handles the `--public-body` flag:

- If `--public-body` is specified: filters existing output or scrapes all and filters
- The step's own logic (see below) handles both cases

Simply pass the flag through to the step:

```python
# No special case needed - just pass --public-body through
# The find_public_bodies step handles it internally
```

### Step-Level Changes

#### Generic Step Pattern

```python
#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from scripts.cli_utils import add_common_args, filter_by_public_body
from scripts.file_utils import read_json, write_json

STEP_NAME = "step_name"
KEY_FIELD = "public_body_id"  # Override if step uses different key


def process(input_data, step_dir, verbose=False):
    # Step-specific processing logic
    # input_data is already filtered if --public-body was specified
    results = []
    for item in input_data.get("results", input_data.get("public_bodies", [])):
        # Process each item
        results.append(processed_item)
    return results


def main():
    parser = argparse.ArgumentParser(description="Step description")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    input_data = read_json(args.input)

    # Filter if public body specified
    if args.public_body is not None:
        if KEY_FIELD != "public_body_id":
            print(f"Info: --public-body flag ignored; this step uses '{KEY_FIELD}' not 'public_body_id'",
                  file=sys.stderr)
        else:
            input_data = filter_by_public_body(input_data, args.public_body)
            if not input_data.get("public_bodies", input_data.get("results", [])):
                print(f"No data for public_body_id={args.public_body} in input",
                      file=sys.stderr)
                sys.exit(0)

    # Process data
    results = process(input_data, step_dir, verbose=args.verbose)

    # Write output with standard structure
    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": results  # or "public_bodies" for find_public_bodies
    }
    write_json(args.output, output)


if __name__ == "__main__":
    main()
```

#### find_public_bodies Special Case

`find_public_bodies` has unique behavior since it's the source of public body data:

```python
def main():
    parser = argparse.ArgumentParser(description="Scrape Irish public bodies from gov.ie")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    # If --public-body specified, handle filtering
    if args.public_body is not None:
        # If output exists and --force is not set, filter existing
        if not args.force and output_path.exists():
            bodies = read_json(output_path)
            filtered = filter_by_public_body(bodies, args.public_body)

            if not filtered.get("public_bodies", []):
                print(f"Error: Public body {args.public_body} not found in existing data",
                      file=sys.stderr)
                sys.exit(1)

            write_json(output_path, filtered)
            write_status(step_dir, len(filtered["public_bodies"]))
            print(f"Filtered to 1 public body: {args.public_body}")
            sys.exit(0)

        # If output doesn't exist or --force is set, scrape all then filter
        if not args.force and output_path.exists():
            print(f"Output exists at {output_path}, skipping (use --force to re-run)")
            sys.exit(0)

        # Scrape all bodies
        bodies = scrape_public_bodies(step_dir, verbose=args.verbose)
        
        # Filter to specified public body
        filtered = filter_by_public_body(bodies, args.public_body)

        if not filtered.get("public_bodies", []):
            print(f"Error: Public body {args.public_body} not found in scraped data",
                  file=sys.stderr)
            sys.exit(1)

        write_json(output_path, filtered)
        write_status(step_dir, len(filtered["public_bodies"]))
        print(f"Scraped and filtered to 1 public body: {args.public_body}")
        sys.exit(0)

    # Normal scraping logic for non-filtered runs
    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    bodies = scrape_public_bodies(step_dir, verbose=args.verbose)
    # ... rest of existing logic
```

**Behavior summary:**
- `--public-body 1001` without `--force` and output exists: Filter existing output
- `--public-body 1001` with `--force` or no output: Scrape all, then filter to 1001
- `--public-body 1001` and body doesn't exist: Error

---

## Data Model

### Input/Output Structure (Unchanged)

The output file structure remains identical. Filtering only affects the **content** of arrays:

**Before (full data):**
```json
{
  "metadata": {"step": "get_foi_emails", "completed_at": "..."},
  "results": [
    {"public_body_id": 1001, "foi_email": "..."},
    {"public_body_id": 1002, "foi_email": "..."},
    {"public_body_id": 1003, "foi_email": "..."}
  ]
}
```

**After (filtered to body 1001):**
```json
{
  "metadata": {"step": "get_foi_emails", "completed_at": "..."},
  "results": [
    {"public_body_id": 1001, "foi_email": "..."}
  ]
}
```

### filter_by_public_body() Behavior

```python
# Input with 'public_bodies' key
{
  "metadata": {...},
  "public_bodies": [
    {"public_body_id": 1001, ...},
    {"public_body_id": 1002, ...}
  ]
}
# Output
{
  "metadata": {...},
  "public_bodies": [
    {"public_body_id": 1001, ...}
  ]
}

# Input with 'results' key
{
  "metadata": {...},
  "results": [
    {"public_body_id": 1001, ...},
    {"public_body_id": 1002, ...}
  ]
}
# Output
{
  "metadata": {...},
  "results": [
    {"public_body_id": 1001, ...}
  ]
}

# If no matching records
{
  "metadata": {...},
  "public_bodies": []  # or "results": []
}
```

---

## Error Handling

| Scenario | Behavior | Exit Code |
|----------|----------|-----------|
| `--public-body` with invalid integer | argparse error | 2 |
| Public body not found in `find_public_bodies/output.json` | Error message to stderr | 1 |
| `--public-body` but `find_public_bodies/output.json` doesn't exist | Error message to stderr | 1 |
| `--public-body` with `--from X` where X is after `find_public_bodies` | Error message (can't validate) | 1 |
| Filtered input has no records for specified body | Info message to stderr, clean exit | 0 |
| Step doesn't use `public_body_id` key (e.g., db_upload) | Info message to stderr, continue | 0 |
| `--public-body` with `find_public_bodies` standalone, no `--force`, output exists | Filter existing output | 0 |
| `--public-body` with `find_public_bodies` standalone, body not in scraped data | Error message to stderr | 1 |

---

## Testing Strategy

### Unit Tests

Location: `foi_pipeline/tests/test_cli_utils.py`

```python
# test_filter_by_public_body.py

def test_filter_by_public_body_with_public_bodies_key():
    data = {"public_bodies": [
        {"public_body_id": 1001, "name": "Body 1"},
        {"public_body_id": 1002, "name": "Body 2"}
    ], "metadata": {}}
    result = filter_by_public_body(data, 1001)
    assert len(result["public_bodies"]) == 1
    assert result["public_bodies"][0]["public_body_id"] == 1001


def test_filter_by_public_body_with_results_key():
    data = {"results": [
        {"public_body_id": 1001, "email": "a@b.com"},
        {"public_body_id": 1002, "email": "c@d.com"}
    ], "metadata": {}}
    result = filter_by_public_body(data, 1002)
    assert len(result["results"]) == 1
    assert result["results"][0]["public_body_id"] == 1002


def test_filter_by_public_body_none():
    data = {"public_bodies": [{"public_body_id": 1001}]}
    result = filter_by_public_body(data, None)
    assert result == data  # Unchanged


def test_filter_by_public_body_no_match():
    data = {"public_bodies": [{"public_body_id": 1001}]}
    result = filter_by_public_body(data, 9999)
    assert result["public_bodies"] == []


def test_validate_public_body():
    # Setup: create temp find_public_bodies/output.json
    # Test: validate existing and non-existing bodies
    pass
```

### Integration Tests

```python
# test_process_public_body.py

def test_full_pipeline_with_public_body(tmp_path, monkeypatch):
    """Test running full pipeline with --public-body flag."""
    # Setup: existing pipeline output files
    # Run: process.py --public-body 1001 --force
    # Assert: each step output contains only body 1001
    pass


def test_individual_step_with_public_body(tmp_path):
    """Test running a single step with --public-body flag."""
    # Setup: input.json with multiple bodies
    # Run: python steps/get_foi_emails/process.py --input input.json --output output.json --public-body 1001
    # Assert: output.json contains only body 1001
    pass


def test_public_body_with_from_flag(tmp_path):
    """Test --public-body with --from flag."""
    # Setup: existing step outputs
    # Run: process.py --from validate_websites --public-body 1001 --force
    # Assert: only validate_websites and subsequent steps run, only body 1001 processed
    pass


def test_public_body_validation_failure(capsys):
    """Test error when public body doesn't exist."""
    # Run: process.py --public-body 9999
    # Assert: exit code 1, error message in stderr
    pass
```

### Manual Testing Checklist

- [ ] Full pipeline with `--public-body 1001 --force`
- [ ] Individual step with `--public-body 1001`
- [ ] Combined with `--from export_status --public-body 1001 --force`
- [ ] Combined with `--verbose --public-body 1001`
- [ ] Error: non-existent public body
- [ ] Error: invalid public body ID (non-integer)
- [ ] Error: `find_public_bodies/output.json` doesn't exist
- [ ] `find_public_bodies --public-body 1001 --force` (standalone)
- [ ] Step without `public_body_id` key (info message)

---

## Migration Path

### Phase 1: Common Library (PR #1)

**Files changed:**
- `foi_pipeline/scripts/cli_utils.py` - New file

**Contents:**
- `add_common_args()`
- `filter_by_public_body()`
- `validate_public_body()`

**Tests:**
- `foi_pipeline/tests/test_cli_utils.py` - Unit tests for new functions

**Backward compatible:** Yes (new file, no existing code changed)

---

### Phase 2: Orchestration Updates (PR #2)

**Files changed:**
- `foi_pipeline/process.py`

**Changes:**
- Add `--public-body` argument
- Add validation logic
- Add flag passthrough to step commands
- Add special handling for `find_public_bodies`

**Tests:**
- Integration test for orchestration with `--public-body`

**Backward compatible:** Yes (new flag is optional)

---

### Phase 3: Step Updates (Multiple PRs)

Update steps **incrementally**, one per PR. Start with steps that are most frequently used for debugging.

**Recommended order:**

1. `find_public_bodies` (base step, needed for validation)
2. `validate_websites`
3. `find_foi_pages`
4. `check_foi_pages`
5. `get_foi_emails`
6. `find_disclosure_pages`
7. `find_disclosure_files`
8. `transform_disclosure_files`
9. `normalize_disclosure_cells`
10. `extract_disclosures_detect_header_row`
11. `extract_disclosures_canonicalize`
12. `extract_disclosures_deduplicate`
13. `export_status`
14. `generate_topics`
15. `db_upload`
16. `resolve_website_urls`

**Per-step changes:**
- Import `add_common_args` from `scripts.cli_utils`
- Replace duplicate argument definitions with `add_common_args(parser)`
- Add filtering after reading input
- Add handling for steps without `public_body_id` (info message)

**Per-step testing:**
- Test step standalone with `--public-body`
- Test step in pipeline with `--public-body`
- Test error cases

---

### Phase 4: Documentation (Final PR)

**Files changed:**
- `foi_pipeline/AGENTS.md` - Update running instructions
- `foi_pipeline/steps/README.md` - Note about `--public-body` flag
- Each step's `README.md` - Document flag support
- This spec document - Mark as implemented

---

## File Changes Summary

| File | Action | Lines Changed (est.) | Risk |
|------|--------|---------------------|------|
| `scripts/cli_utils.py` | Create | ~100 | Low |
| `process.py` | Modify | ~20 | Low |
| `steps/find_public_bodies/process.py` | Modify | ~15 | Low |
| `steps/validate_websites/process.py` | Modify | ~10 | Low |
| `steps/find_foi_pages/process.py` | Modify | ~10 | Low |
| `steps/check_foi_pages/process.py` | Modify | ~10 | Low |
| `steps/get_foi_emails/process.py` | Modify | ~10 | Low |
| `steps/find_disclosure_pages/process.py` | Modify | ~10 | Low |
| `steps/find_disclosure_files/process.py` | Modify | ~10 | Low |
| `steps/transform_disclosure_files/process.py` | Modify | ~10 | Low |
| `steps/normalize_disclosure_cells/process.py` | Modify | ~10 | Low |
| `steps/extract_disclosures_detect_header_row/process.py` | Modify | ~10 | Low |
| `steps/extract_disclosures_canonicalize/process.py` | Modify | ~10 | Low |
| `steps/extract_disclosures_deduplicate/process.py` | Modify | ~10 | Low |
| `steps/export_status/process.py` | Modify | ~10 | Low |
| `steps/generate_topics/process.py` | Modify | ~10 | Low |
| `steps/db_upload/process.py` | Modify | ~10 | Low |
| `steps/resolve_website_urls/process.py` | Modify | ~10 | Low |
| **Total** | | **~255** | **Low** |

---

## Commands Reference

### After Implementation

Run full pipeline for one public body:
```bash
cd foi_pipeline
python process.py --public-body 1001 --force
```

Run from a specific step for one public body:
```bash
cd foi_pipeline
python process.py --from validate_websites --public-body 1001 --force
```

Run a single step for one public body:
```bash
cd foi_pipeline
PYTHONPATH=. python steps/get_foi_emails/process.py \
  --input steps/find_foi_pages/output.json \
  --output /tmp/test_output.json \
  --public-body 1001 \
  --force
```

Filter find_public_bodies to a single body:
```bash
cd foi_pipeline
PYTHONPATH=. python steps/find_public_bodies/process.py \
  --input . \
  --output steps/find_public_bodies/output.json \
  --public-body 1001 \
  --force
```

---

## Appendix A: Current Step Analysis

Before implementation, audit all steps to identify:

1. Which steps use `public_bodies` vs `results` as their top-level key
2. Which steps use a different key field than `public_body_id`
3. Which steps have unique argument requirements beyond the common set

| Step | Top-Level Key | Key Field | Unique Args | Filterable? |
|------|---------------|-----------|-------------|------------|
| find_public_bodies | public_bodies | public_body_id | None | Yes |
| resolve_website_urls | results | public_body_id | None | Yes |
| validate_websites | results | public_body_id | None | Yes |
| find_foi_pages | results | public_body_id | None | Yes |
| check_foi_pages | results | public_body_id | None | Yes |
| get_foi_emails | results | public_body_id | None | Yes |
| find_disclosure_pages | results | public_body_id | None | Yes |
| find_disclosure_files | results | public_body_id | None | Yes |
| transform_disclosure_files | results | public_body_id | None | Yes |
| normalize_disclosure_cells | results | public_body_id | None | Yes |
| extract_disclosures_detect_header_row | results | public_body_id | None | Yes |
| extract_disclosures_canonicalize | results | public_body_id | None | Yes |
| extract_disclosures_deduplicate | results | public_body_id | None | Yes |
| export_status | public_bodies | public_body_id | None | Yes |
| generate_topics | results | public_body_id | None | Partial* |
| db_upload | N/A | public_body_id | None | No** |

*generate_topics: Uses disclosures from extract_disclosures_canonicalize which contain public_body_id. Can filter input but output structure is different (topics with matched disclosures).

**db_upload: Reads from multiple step outputs directly (not from --input). The --public-body flag would be ignored with an info message, as this step doesn't process input in the same way.

*Note: All steps except db_upload use public_body_id as their key field and can be filtered.*

---

## Appendix B: Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Filter at orchestration or step level? | Step level (Approach B) - allows individual step runs |
| Works with `--from` flag? | Yes - processes only that body through remaining steps |
| Works with `--force` flag? | Yes - forces reprocessing of just that body |
| Output structure changed? | No - array wrappers preserved |
| Public body ID format? | Single integer |
| Validation location? | At start, against `find_public_bodies/output.json` |
| Error if body doesn't exist? | Yes - exit with error |
| Multiple IDs supported? | No - single ID only |
| Common library for CLI? | Yes - `scripts/cli_utils.py` |
| Migration approach? | Incremental (one step at a time) |
| Steps without public_body_id? | Info message, flag ignored |
| find_public_bodies standalone? | Yes - filters existing output with `--force` |

---

## Approval

This design has been reviewed and discussed. Ready for implementation planning.

**Design approved by:** [User name]  
**Date:** [To be filled]  

---

*Generated by Mistral Vibe.  
Co-Authored-By: Mistral Vibe <vibe@mistral.ai>*
