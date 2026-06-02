# PublicInformation.ie - Agent Documentation Index

This is the top-level entry point for agent documentation in the publicinformation.ie repository. Use this file to navigate to all agent-relevant documentation.

## Repository Structure

```
publicinformation-data/
├── AGENTS.md                          # This file - top-level index
├── DATA_FLOW.md                      # End-to-end data flow overview
├── foi_pipeline/
│   ├── AGENTS.md                     # FOI pipeline architecture and operations
│   ├── process.py                   # Pipeline execution engine
│   ├── pipeline.json                 # Authoritative step order configuration
│   └── steps/
│       ├── AGENTS.md                 # Steps directory management guidelines
│       ├── README.md                 # Complete step sequence and descriptions
│       └── <step_name>/
│           ├── README.md             # Step-specific documentation
│           ├── process.py            # Step entry point
│           └── AGENTS.md             # (Some steps may have their own)
├── scripts/
│   └── README.md                     # Helper scripts documentation
└── public/
    └── *.json                        # Public-facing output files
```

## Documentation Index

### Core Documentation Files

| File | Purpose | Audience |
|------|---------|----------|
| **[AGENTS.md](AGENTS.md)** | This top-level index | All agents |
| **[DATA_FLOW.md](DATA_FLOW.md)** | End-to-end data flow from pipeline to website | Pipeline & Website |
| **[foi_pipeline/AGENTS.md](foi_pipeline/AGENTS.md)** | Pipeline architecture, running steps, troubleshooting | Pipeline agents |
| **[foi_pipeline/steps/AGENTS.md](foi_pipeline/steps/AGENTS.md)** | Step directory management, adding new steps | Pipeline developers |
| **[foi_pipeline/steps/README.md](foi_pipeline/steps/README.md)** | Complete step sequence with descriptions | Pipeline users |
| **[scripts/README.md](scripts/README.md)** | Helper and admin scripts | Maintainers |

### Quick Start: Running the Pipeline

**To run the full pipeline:**
```bash
cd foi_pipeline
python process.py --force
```

**To run from a specific step:**
```bash
cd foi_pipeline
python process.py --from export_status --force
```

**To run a single step manually:**
```bash
cd foi_pipeline
PYTHONPATH=. python steps/export_status/process.py \
  --input steps/find_public_bodies/output.json \
  --output steps/export_status/output.json \
  --force
```

> **Note:** When Vibe CLI attempts to run pipeline scripts, it may try multiple times. To prevent redundant execution, ensure you're using the process script (`process.py`) rather than calling individual step scripts directly. The process script handles dependencies and staleness checks.

### Step Directories

Each pipeline step has its own directory under `foi_pipeline/steps/` with the following structure:

```
steps/<step_name>/
├── README.md         # Step documentation (what it does, input, output)
├── process.py        # Main processing script (entry point)
├── output.json       # Step output data
├── errors.json       # Per-record errors and warnings
├── override.json     # Manual overrides (never overwritten by automation)
├── dirty_ids.json    # IDs with changed upstream data
└── output_schema.json # JSON schema for output validation
```

**Step documentation:** Each step's README.md follows a consistent format:
- What the step does
- Input files and sources
- Output format and files
- Notable files in the directory

See [foi_pipeline/steps/README.md](foi_pipeline/steps/README.md) for the complete list of steps in order.

### Key Concepts

#### Pipeline Steps
The FOI pipeline consists of 15 sequential steps that process Irish public body data:

1. **find_public_bodies** - Scrapes gov.ie for the master list
2. **resolve_website_urls** - Resolves gov.ie stub URLs
3. **validate_websites** - Checks website reachability
4. **find_foi_pages** - Discovers FOI pages on each website
5. **check_foi_pages** - Validates FOI page accessibility
6. **get_foi_emails** - Extracts FOI email addresses
7. **find_disclosure_pages** - Locates disclosure log pages
8. **find_disclosure_files** - Collects disclosure document links
9. **transform_disclosure_files** - Processes files into structured data
10. **normalize_disclosure_cells** - Normalizes string cell values
11. **extract_disclosures_detect_header_row** - Detects header rows in spreadsheets
12. **extract_disclosures_canonicalize** - Maps columns to canonical fields
13. **export_status** - Fan-in merge of all step outputs (CRITICAL for website)
14. **generate_topics** - Groups FOI records into topics
15. **db_upload** - Populates the libSQL database

**Critical Step:** `export_status` is the final aggregator that merges all step outputs into a single file consumed by the website. If data is missing on the site, check if this step has been run.

#### Data Flow

```
find_public_bodies → validate_websites → find_foi_pages → check_foi_pages → ... 
    → export_status → public/pipeline-data.json → Website consumption
```

See [DATA_FLOW.md](DATA_FLOW.md) for the complete end-to-end flow including website integration.

#### Override System

Each step directory may contain an `override.json` file with manually-curated records. These records:
- Are **never overwritten** by automated re-runs
- Use `"source_method": "manual"` and `"overridden": true` markers
- Bypass normal processing (no HTTP calls made for overridden bodies)
- Are committed to git as the source of truth

See [foi_pipeline/AGENTS.md - Override System](foi_pipeline/AGENTS.md#override-system) for details.

### Troubleshooting Guide

**Problem: Scripts are being run multiple times by Vibe**

This happens when Vibe CLI tries to execute step scripts directly. To prevent this:

1. **Always use the process script** for pipeline execution:
   ```bash
   cd foi_pipeline
   python process.py --force
   ```

2. **The process script's staleness checks** prevent re-running steps that are up-to-date. Use `--force` to bypass.

3. **For individual step testing**, use the process script with `--from`:
   ```bash
   python process.py --from export_status --force
   ```

**Problem: Data missing on website**

Check the fallback chain:
1. Has `export_status` been run? (creates `steps/export_status/output.json`)
2. Has the website been rebuilt? (`cd ../publicinformation-web && npm run build`)
3. Check `../publicinformation-web/src/data/pipeline-status.json` source

See [DATA_FLOW.md - Troubleshooting](DATA_FLOW.md#troubleshooting-decision-tree) for the complete decision tree.

**Problem: All status show as "not_attempted"**

This means only `find_public_bodies` has been run. Run the full pipeline or at minimum through `export_status`.

### Common Commands Reference

| Task | Command |
|------|---------|
| Run full pipeline | `cd foi_pipeline && python process.py --force` |
| Run from export_status | `cd foi_pipeline && python process.py --from export_status --force` |
| Run single step | `cd foi_pipeline && PYTHONPATH=. python steps/<step>/process.py --input ... --output ... --force` |
| Run tests | `cd foi_pipeline && uv run pytest tests/ -q` |
| Build website | `cd ../publicinformation-web && npm run build` |
| Check export_status output | `ls -lh foi_pipeline/steps/export_status/output.json` |
| Validate output | `python3 -c "import json; d=json.load(open('foi_pipeline/steps/export_status/output.json')); print(f'Bodies: {len(d[\"public_bodies\"])}')"` |

### File Locations Reference

| File | Purpose | Generated |
|------|---------|-----------|
| `foi_pipeline/pipeline.json` | Step order configuration | No |
| `foi_pipeline/steps/*/output.json` | Individual step outputs | Yes |
| `foi_pipeline/steps/export_status/output.json` | **Consolidated output for website** | Yes |
| `public/pipeline-data.json` | Public-facing consolidated data | Yes |
| `public/disclosure-files.json` | All disclosure file URLs | Yes |
| `public/foi-disclosures.json` | All FOI request records | Yes |
| `public/topics.json` | Topic groupings | Yes |

### When to Use Which Documentation

| Scenario | Start Here |
|----------|------------|
| **New to the project** | This file (AGENTS.md) → DATA_FLOW.md |
| **Need to run the pipeline** | [foi_pipeline/AGENTS.md - Running the Pipeline](foi_pipeline/AGENTS.md#running-the-pipeline) |
| **Adding a new step** | [foi_pipeline/steps/AGENTS.md](foi_pipeline/steps/AGENTS.md) |
| **Troubleshooting data issues** | [DATA_FLOW.md - Troubleshooting](DATA_FLOW.md#common-issues--fixes) |
| **Understanding data model** | [foi_pipeline/AGENTS.md - Data Model](foi_pipeline/AGENTS.md#data-model-evolution) |
| **Using override system** | [foi_pipeline/AGENTS.md - Override System](foi_pipeline/AGENTS.md#override-system) |
| **Website data consumption** | [../publicinformation-web/DATA_CONSUMPTION.md](../publicinformation-web/DATA_CONSUMPTION.md) |

---

## Custom Agent for Pipeline Execution: Analysis

You mentioned that Vibe tries multiple times to run pipeline step scripts. Below is an analysis of creating a custom agent for running steps and analyzing results.

### Pros of a Custom Agent

1. **Prevents Redundant Execution**
   - The process script already handles this via staleness checks (`is_stale()` function)
   - A custom agent could cache results and skip already-completed steps
   - Could track which steps have been run in the current session

2. **Centralized Control**
   - Single entry point for all pipeline operations
   - Consistent environment setup (PYTHONPATH, virtualenv activation)
   - Standardized error handling and logging

3. **Better State Management**
   - Tracks progress across multiple step executions
   - Maintains context between related operations
   - Could provide rollback capabilities

4. **Improved Analysis**
   - Automated comparison of outputs between runs
   - Detection of regressions or data changes
   - Generation of execution reports and metrics

5. **Session Awareness**
   - Remembers what's been run in the current session
   - Prevents Vibe from re-executing the same commands
   - Could provide "resume from last successful step" functionality

6. **Simplified Interface**
   - Single command to "run and analyze" vs. separate steps
   - Encapsulates complexity of dependency management
   - Could provide high-level goals ("update all FOI data")

7. **Integration with Vibe**
   - Could be Vibe-aware: register itself to prevent re-invocation
   - Maintain a `.vibe/pipeline-state.json` to track session progress
   - Provide feedback to Vibe about what's been completed

### Cons of a Custom Agent

1. **Additional Complexity**
   - Another layer of abstraction to maintain
   - Potential for bugs in the agent itself
   - Learning curve for new contributors

2. **Duplicates Existing Functionality**
   - The process script already handles step dependencies and staleness
   - `export_status` already merges all outputs
   - Risk of reimplementing what already exists

3. **Maintenance Burden**
   - Must be kept in sync with pipeline changes
   - Additional code to test and document
   - Potential for divergence from the main process script

4. **State Management Complexity**
   - Session state files need to be managed carefully
   - Risk of stale state causing confusion
   - Cross-session coordination is tricky

5. **Debugging Difficulty**
   - Another layer to debug when things go wrong
   - Harder to understand what's actually being executed
   - May obscure the underlying pipeline behavior

6. **Vibe-Specific Logic**
   - Tight coupling to Vibe CLI's behavior
   - May not work well outside of Vibe context
   - Vibe's behavior may change, breaking the agent

### Recommendation

**Option A: Enhance the Existing Process Script (Recommended)**

Modify `process.py` to:
1. Add a session state file (e.g., `.vibe/pipeline-state.json`)
2. Track which steps have been run in the current session
3. Add a `--session-aware` flag that checks the state file
4. Return exit codes that Vibe can understand to prevent re-execution

```python
# In process.py
def main():
    # ... existing code ...
    
    # Check session state
    state_file = Path(".vibe/pipeline-state.json")
    if state_file.exists() and not args.force:
        state = json.loads(state_file.read_text())
        if state.get("last_completed") == steps[-1]:
            print("All steps already completed in this session")
            return 0
```

**Option B: Create a Lightweight Wrapper Script**

Create `run_pipeline.sh` or `vibe_orchestrator.py` that:
1. Checks if it's being called by Vibe
2. Maintains a simple session log
3. Delegates to the main process script
4. Sets up the environment correctly

```bash
#!/bin/bash
# run_pipeline.sh

SESSION_LOG=".vibe/pipeline-session.log"

if [ -f "$SESSION_LOG" ] && grep -q "process.py --force" "$SESSION_LOG"; then
    echo "Pipeline already run in this session"
    exit 0
fi

cd foi_pipeline
python process.py "$@"
echo "$(date): $0 $*" >> "$SESSION_LOG"
```

**Option C: Full Custom Agent**

Only recommended if you find yourself repeatedly:
- Running the same sequence of steps
- Analyzing the same types of outputs
- Needing to compare results across runs
- Wanting to automate the "run, check, fix, re-run" cycle

A custom agent could encapsulate common workflows like:
- "Run full pipeline and deploy to CDN"
- "Run from export_status and verify website data"
- "Compare current output with previous run"

### Immediate Solution for Vibe Multiple Execution

For now, the simplest solution is to:

1. **Use the process script with explicit flags:**
   ```bash
   cd foi_pipeline && python process.py --force 2>&1 | tee .vibe/pipeline-run.log
   ```

2. **Check before running:**
   ```bash
   if [ -f foi_pipeline/steps/export_status/output.json ]; then
       echo "export_status already complete"
   else
       cd foi_pipeline && python process.py --force
   fi
   ```

3. **Use environment variable guards:**
   ```bash
   export VIBE_PIPELINE_RUN=1
   cd foi_pipeline && python process.py --force
   ```
   And check for this at the start of scripts.

---

## Summary

- **Start here** for navigation to all agent documentation
- **Use the process script** (`process.py`) for running the pipeline
- **Check export_status** if website data is missing
- **Enhancing the process script** is likely better than a separate custom agent
- **Session awareness** can be added to prevent Vibe from re-running completed steps
