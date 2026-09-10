# Scripts — Agent Instructions

For the top-level overview, see the parent [AGENTS.md](../AGENTS.md). For full usage details of each script, see [README.md](README.md).

## When to use which script

Before writing a new one-off analysis snippet, check whether one of these already answers the question:

| Need | Script |
|---|---|
| Which pipeline files/bodies are contributing the most errors, and why? | `file_issues.py` — grouped by issue type (default), or `--by-file` to rank files/bodies by total issue count and find outliers. Reads step `output.json`/`errors.json` directly; no DB needed. |
| Is the **exported/deployed** `foi_disclosures` data still showing quality issues, ranked by source file? | `audit_disclosures.py` — SQL checks against the live DB, post `export_status`. Use this instead of `file_issues.py` when you need the actual exported state rather than intermediate pipeline artifacts. |
| Why did one specific file drop out of the pipeline, or at which step did it start failing? | `trace_file.py --url <file_url>` — walks one file through every step and reports SUCCESS/PARTIAL/FAILED per step. |
| One-time, idempotent bulk remapping of pipeline data (e.g. an ID namespace migration) | `migrate_foi_ids_to_cso.py` as a reference implementation — idempotent, dry-run first, aborts loudly on unresolved records rather than guessing. |
| Reviewing/accepting user-submitted corrections from the public API | `admin-corrections.mjs` |
| Publish the public-body-actions dataset (3 tables) from actions_pipeline output | `transform_public_body_actions.py` — asserts the §12 validation invariants before writing. |
| Publish the motions dataset (JSON-LD + CSV) from minutes_pipeline output | `transform_motions.py` — resolves `public_body_id` through the permanent slug machinery (never the motion's own slug) and raises on an unresolvable id. |

## Prefer extending over duplicating

`file_issues.py` and `audit_disclosures.py` both already support filters (`--step`, `--issue`, `--check`, `--min-errors`). If an existing script is close but missing a view you need (as with the `--by-file` flag), add a flag and a test rather than writing a new throwaway script that re-implements the same data loading.

## Keeping this in sync

When you add a new script to `scripts/`, add a full usage section to `README.md` and a one-row pointer to the table above.

`generate_pipeline_docs.py` maintains generated sections in the repository's `AGENTS.md` from each pipeline's `pipeline.json`. Run it after changing pipeline configuration, or use `--check` to verify that documentation is current.
