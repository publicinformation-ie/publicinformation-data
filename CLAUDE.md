Refer to AGENTS.md for all context and instructions

## Cost rule: `extract_motions` needs explicit permission

The `extract_motions` step (minutes_pipeline) makes a paid model call per file, so it incurs a real cost. **Never run it without explicit permission from the user, given for that run.** This covers every way of triggering it:

- running the step directly (`steps/extract_motions/process.py`);
- running the full pipeline, or any run that includes it (`process.py` with no `--to`, or `--to` at or past `extract_motions`);
- running from an upstream step with `--from` (e.g. `--from transform_minutes_files`) when the window reaches `extract_motions`.

Before any such run, stop and ask. Otherwise bound the run so it ends before the step, e.g. `--to ocr_minutes_files`. Permission for one run does not carry over to later runs, and "run the pipeline" or "go through to export" does not by itself count as permission.
