> **Superseded 2026-11-26.** All 36 tasks are complete, the sweep is done, the
> dataset is published and the integration checks pass. This prompt is kept for
> history; use `review-2026-11-26.md` for the merge review and
> `handoff-publicinformation-web.md` for the website work.

# Handoff — continue `add-spc-minutes-pipeline` in a new session

Paste the prompt below into the new session. It assumes the same checkout and
branch, with this session's uncommitted work still in the working tree.

---

You are continuing an OpenSpec change in the repository
`/Volumes/ext/dev/publicinformation/publicinformation-data`, on branch
`claude/adoring-volta-9upm2e`. Read `AGENTS.md` and the change's
`proposal.md`, `design.md`, specs and `tasks.md` first.

Change: `add-spc-minutes-pipeline` (schema: spec-driven). 33 of 36 tasks are
complete; all work from the previous session is **uncommitted** in the working
tree. Start with `git status --short` and review the diff before changing
anything. Do not touch the unrelated untracked files:
`openspec/changes/improve-chapter-split-accuracy/`,
`pipelines/foi_pipeline/experiments/gating/populate_docling_cache.py`, and
`pipelines/foi_pipeline/steps/transform_disclosure_files/docling_cache/`.
There is also a `stash@{0}` from an earlier branch switch; leave it alone.

Use the OpenSpec apply workflow:

    openspec instructions apply --change "add-spc-minutes-pipeline" --json

It reports 3 remaining tasks: 8.3 (model sweep), 10.1 (web handoff), 11.1
(integration run). All three need the paid step `extract_spc_items`, which
makes one model call per meeting (6 meetings). **Do not run it, a full
pipeline, or any `--from`/`--to` window reaching it without the user's
explicit permission for that run.** `CLAUDE.md` has the cost rule.

## What is already implemented

New pipeline `pipelines/spc_pipeline/` with:
- `pipeline.json` — 8 steps, cross-pipeline `find_local_authorities` reference,
  `paid_steps: {"extract_spc_items": ["llm"]}`;
- steps: `find_spc_minutes_files`, `fetch_spc_minutes`,
  `parse_meeting_header`, `resolve_attendees`, `render_spc_minutes`,
  `extract_spc_items`, `export_spc_meetings`, each with README and tests;
- `reference/people.json`, `reference/cofog_1999.json`,
  `reference/transport_subdomains.json`;
- `scripts/build_cofog.py`, `scripts/build_vocabularies.py`;
- `experiments/2026-11-26-spc-model-sweep/gold.json` and `sweep.py`;
- `status.py`.

Shared code and publication:
- `src/lib/certs/` — committed DigiCert intermediate plus
  `build_ssl_context()` / `requests_verify()`;
- `scripts/transform_spc_meetings.py` — writes
  `public/v1.0.0/spc-meetings/`, mirrors to `public/latest/spc-meetings/`,
  stamps `dct:modified` only on change;
- `public/schemas/spc-meetings.schema.json`,
  `public/catalog/dataset-spc-meetings.ttl`, six vocabulary CSV/CSVW pairs;
- discovery links in `public/GET_THE_DATA.md`, `public/README.md`,
  `public/get-the-data.html`; changelog and `DATA_SOURCES.md` entries;
- `src/lib/pipeline_runner.py` now accepts a cross-pipeline step basename for
  `--from`/`--to` and resolves an absolute `body_list_step` (tested).

Deterministic state in this checkout: discovery found 6 PDFs, fetch cached
them, all 6 meetings parsed and resolved with zero errors, and rendering
passed the word check with 108 furniture lines removed. The cache lives in
`pipelines/spc_pipeline/cache/` (git-ignored) and is warm.

## Verified

- `cd pipelines/spc_pipeline && uv run pytest tests/ -q` → 85 passed
- `uv run pytest tests/ -q` → 557 passed
- `uv run pytest pipelines/document_pipeline/tests -q` → 600 passed, 4 skipped
- `uv run pyright` → 0 errors
- FOI suite: 1,857 passed; 6 failures + 5 collection errors are pre-existing
  and environmental (`pymupdf` missing, untracked gating experiment). Runner
  tests pass (39).
- `uv run python scripts/generate_pipeline_docs.py --check` → clean.

## Remaining work

1. **8.3 — model sweep.** Before running a live sweep, note that
   `sweep.py`'s `live_runner()` ignores its `model` argument and calls
   `extract_meeting`, which reads `SPC_LLM_MODEL`. Either set `SPC_LLM_MODEL`
   per model for each run, or add a model override to `extract_meeting`. Ask
   the user for the candidate models and any price list; write
   `--prices` as `{model: {input, output}}` in USD per 1M tokens. Then write
   `REPORT.md`, agree a production model and thresholds with the user, and
   record them in `steps/extract_spc_items/README.md`.
2. **With permission: run extraction and publish.**

       uv run python pipelines/spc_pipeline/process.py pipelines/spc_pipeline \
         --from extract_spc_items --force --stop-on-error
       uv run python scripts/transform_spc_meetings.py
       uv run python pipelines/spc_pipeline/status.py

   The extraction cache is keyed by source sha256 + model + prompt version, so
   a re-run with unchanged inputs makes no model call.
3. **9.x/11.1 verification on real output.** The transform tests already cover
   the invariants on synthetic data; now check the real files:
   - `public/latest/spc-meetings` and `public/v1.0.0/spc-meetings` are
     byte-identical (a skipped test runs once published);
   - every record validates against the schema (skipped test runs once the
     export exists);
   - every `public_body` resolves in Public Bodies;
   - run `uv run pytest tests/ -q`, `uv run pytest pipelines/spc_pipeline/tests -q`,
     `uv run pyright`, and review the error counts and `public/` diff before
     any merge (merging publishes).
4. **10.1 — finalise `handoff-publicinformation-web.md`** against the real
   exported files: URLs, field lists, one sample record of each kind, the
   Markdown front matter and rendering trust boundary, and the
   `attendance_published` counting rule. Every URL and field name must exist in
   `public/latest/spc-meetings/`.
5. Mark the remaining tasks `- [x]` in
   `openspec/changes/add-spc-minutes-pipeline/tasks.md` as each is verified,
   and archive/sync the change only after review.

## Gotchas

- May 2026 prints two items numbered `6.0`. Extraction and export key on the
  stable `item_key` (`item-6-0`, `item-6-0-2`), not the printed number. Keep
  that.
- `www.meath.ie` omits a DigiCert intermediate. Use `src/lib/certs`; never
  disable certificate verification.
- Withheld attendance/topics/decisions are designed, non-fatal outcomes
  recorded in each step's `errors.json` and counted in the export report. Do
  not turn them into pipeline failures without a reason.
- `status.py` exits 2 until `extract_spc_items/output.json` exists; that is
  expected before the paid run.
- `public/index.html` is a redirect stub, not the data hub; discovery links go
  in `GET_THE_DATA.md`, `README.md` and `get-the-data.html`.
- `--to render_spc_minutes` is the bounded, unpaid command. Anything reaching
  `extract_spc_items` is paid.
