# sync_backlog

## What this step does

Collects pipeline evaluation issues from all step `eval/issues.json` files, scores and prioritises them, then writes the result to `backlog.yml` in this directory. The file is committed to git so the backlog is versioned alongside the code.

This step:
1. Reads `eval/issues.json` from each step directory
2. Scores issues by severity, affected count, and pipeline position
3. Assigns priority tiers (low / medium / high) relative to all current issues
4. Merges with the existing `backlog.yml`, tracking `first_seen` / `last_seen` / `resolved_at`
5. Writes updated `backlog.yml` and `output.json` stats

## Input

- `eval/issues.json` from each step directory in the pipeline
- `pipeline.json` for step order (used in scoring)
- `steps/sync_backlog/backlog.yml` (existing backlog; treated as empty if absent)

## Output

- `steps/sync_backlog/backlog.yml`: Full issue backlog with status, dates, priority
- `output.json`: Operation statistics (created, updated, resolved, unchanged counts)

## backlog.yml schema

Each entry in `backlog.yml` has these fields:

| Field | Description |
|-------|-------------|
| `key` | Unique identifier: `step_name:slug` |
| `step_name` | Pipeline step that produced the issue |
| `description` | Human-readable description from the eval |
| `severity` | `error`, `warning`, or `info` |
| `priority` | `high`, `medium`, or `low` (assigned relative to all open issues) |
| `affected_count` | Number of records affected |
| `suggestion_detail` | Recommended fix from the eval |
| `status` | `open` or `resolved` |
| `first_seen` | ISO timestamp when first detected |
| `last_seen` | ISO timestamp of most recent detection |
| `resolved_at` | ISO timestamp when resolved (only present on resolved issues) |

## Notable files

- `run.py`: Core logic — scoring, YAML load/save, reconcile
- `process.py`: CLI entry point

## Environment variables

None required. This step has no external dependencies.
