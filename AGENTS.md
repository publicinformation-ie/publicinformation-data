# PublicInformation.ie - Agent Documentation

Top-level instruction file for agents working in this repository. It points to the docs that matter and flags the things most likely to trip up a new session. For human-facing context start at [README.md](README.md); for the end-to-end data flow see [DATA_FLOW.md](DATA_FLOW.md).

## Core Data-Handling Principle

**If a record cannot be reasonably and deterministically reconstructed, write an error and let a human reviewer handle it.** Forcing a manual review is always preferable to risking a false positive or silently losing information.

Concretely, in the transform and canonicalization steps (`transform_disclosure_files`, `normalize_*`, `extract_disclosures_*`):

- **Don't guess.** Don't reconstruct malformed values with elaborate or fragile heuristics/regexes. If you can't map a value confidently, classify the problem, write an error to the step's `errors.json`, and move on.
- **Never silently null or rewrite a field** to make it "fit". A confidently-wrong value (false positive) or a quietly-dropped field is worse than an explicit, reviewable error.
- **Confirmed contamination** (e.g. a date or a column header sitting in `decision_status`) may be dropped from output — but always with an error logged so a human can find it. It is fine to declare a record or file "too malformed to reconstruct".

## Running the Pipeline — Read This First

`process.py` in every pipeline uses the **shared runner** `src/lib/pipeline_runner.py`, and **its pipeline directory defaults to your current working directory, not the script's location.** Running `python pipelines/foi_pipeline/process.py --force` from the repo root fails with `FileNotFoundError: pipeline.json`.

Do this instead:

```bash
# From the repo root — pass the pipeline dir explicitly:
uv run python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force

# Or cd into the pipeline dir (runner then defaults to cwd):
cd pipelines/foi_pipeline && uv run python process.py --force --stop-on-error
```

- Always run through `process.py`, never a step's own `process.py` — it resolves dependencies, staleness, and `--from`. Invoke individual steps only for isolated debugging.
- `--force` bypasses the mtime-based staleness check; `--from <step>` resumes from that step on; `--stop-on-error` halts on the first failing step.
- Include `--stop-on-error` in normal and production runs. Without it, the runner continues after a failed step and may produce misleading downstream artifacts.
- `--public-body <id>` scopes a run to one body; `--doc <slug>` scopes the document pipeline to one document.
- **document_pipeline: `--doc` must be paired with `--force`** — the staleness check is mtime-based and doesn't know about per-document freshness, so a scoped run without `--force` may skip everything as "up to date".

## Step Sequences

<!-- BEGIN GENERATED: pipeline-overviews -->

### `actions_pipeline` (3 steps)

| # | Step |
|---:|---|
| 1 | `/pipelines/document_pipeline/steps/extract_actions` |
| 2 | `resolve_action_identity` |
| 3 | `extract_relationships` |

### `cso_pipeline` (6 steps)

| # | Step |
|---:|---|
| 1 | `parse_cso_bodies` |
| 2 | `normalize_cso_fields` |
| 3 | `match_gov_urls` |
| 4 | `search_websites_llm` |
| 5 | `search_websites_apify` |
| 6 | `resolve_website_urls` |

### `datagovie_pipeline` (3 steps)

| # | Step |
|---:|---|
| 1 | `fetch_datagovie_orgs` |
| 2 | `match_public_bodies` |
| 3 | `apply_overrides` |

### `document_pipeline` (10 steps)

| # | Step |
|---:|---|
| 1 | `find_plan_pdfs` |
| 2 | `fetch_pdfs` |
| 3 | `extract_pages` |
| 4 | `detect_structure` |
| 5 | `extract_figures` |
| 6 | `clean_text` |
| 7 | `extract_actions` |
| 8 | `extract_action_status` |
| 9 | `assemble_sections` |
| 10 | `publish_bundles` |

### `foi_pipeline` (27 steps)

| # | Step |
|---:|---|
| 1 | `/pipelines/cso_pipeline/steps/resolve_website_urls` |
| 2 | `find_public_bodies` |
| 3 | `find_public_bodies_subject_to_foi` |
| 4 | `validate_websites` |
| 5 | `find_foi_pages` |
| 6 | `find_foi_pages_search` |
| 7 | `check_foi_pages` |
| 8 | `get_foi_emails` |
| 9 | `find_foi_email_pages` |
| 10 | `find_disclosure_pages` |
| 11 | `fingerprint_disclosure_pages` |
| 12 | `find_disclosure_files` |
| 13 | `verify_disclosure_files` |
| 14 | `transform_disclosure_files` |
| 15 | `normalize_disclosure_cells` |
| 16 | `filter_phantom_rows` |
| 17 | `extract_disclosures_detect_header_row` |
| 18 | `extract_disclosures_normalize_header` |
| 19 | `extract_disclosures_split_combined_columns` |
| 20 | `extract_disclosures_normalize_rows` |
| 21 | `extract_disclosures_canonicalize` |
| 22 | `extract_disclosures_canonicalize_rows` |
| 23 | `extract_disclosures_deduplicate` |
| 24 | `export_status` |
| 25 | `generate_topics` |
| 26 | `db_upload` |
| 27 | `sync_backlog` |

Always-run steps: `fingerprint_disclosure_pages`.

### `foigovie_pipeline` (3 steps)

| # | Step |
|---:|---|
| 1 | `fetch_foigovie_bodies` |
| 2 | `match_public_bodies` |
| 3 | `apply_overrides` |

### `lobbying_pipeline` (3 steps)

| # | Step |
|---:|---|
| 1 | `fetch_lobbying_bodies` |
| 2 | `match_public_bodies` |
| 3 | `apply_overrides` |

### `minutes_pipeline` (7 steps)

| # | Step |
|---:|---|
| 1 | `find_local_authorities` |
| 2 | `find_meeting_minutes_pages` |
| 3 | `find_minutes_files` |
| 4 | `transform_minutes_files` |
| 5 | `extract_motions` |
| 6 | `canonicalize_motions` |
| 7 | `export_motions` |

### `statespend_pipeline` (3 steps)

| # | Step |
|---:|---|
| 1 | `fetch_statespend_bodies` |
| 2 | `match_public_bodies` |
| 3 | `apply_overrides` |

### `wdw_pipeline` (3 steps)

| # | Step |
|---:|---|
| 1 | `parse_wdw_bodies` |
| 2 | `match_public_bodies` |
| 3 | `apply_overrides` |

<!-- END GENERATED: pipeline-overviews -->

## Tests

Three separate suites, all via `uv run pytest`:

| Suite | Command |
|---|---|
| FOI pipeline steps + eval | `cd pipelines/foi_pipeline && uv run pytest tests/ -q` |
| Document pipeline | `uv run pytest pipelines/document_pipeline/tests -q` |
| Scripts / transforms (repo root) | `uv run pytest tests/ -q` |
| Type checking | `uv run pyright` (shared `src/` library) |

CI currently enforces the three test suites, `pyright`, and generated-document consistency. No formatter or linter is enforced.

## Instruction Scope

Instructions apply from the repository root downward. A nested `AGENTS.md` adds or narrows guidance for its directory; follow the deepest applicable file when instructions conflict. `CLAUDE.md` delegates to this file. Configuration files such as `pipeline.json` and `pyrightconfig.json` are authoritative over explanatory prose.

## Safe Operations

Before running a live pipeline:

1. Inspect `git status --short` and preserve unrelated user changes.
2. Confirm required upstream outputs and environment variables.
3. Check whether the run uses network services, Apify/LLM calls, database writes, or publishing.
4. Prefer a scoped run and include `--stop-on-error`.
5. Review generated diffs and error counts before committing or publishing.

Full pipeline runs can modify many generated artifacts. They may also consume API quota and update the local or remote database. Do not run `scripts/publish_pages.sh` until the generated public-data diff has been reviewed.

## Subagent Dispatch (cost control)

Dispatch the cheapest agent tier that can do the job and escalate deliberately — a rule that is cheap for one call gets expensive across an N-way fan-out. As a default: search/locate/triage → `explorer` (haiku/low); implementation and per-round review → `general` (sonnet/medium); one final review per branch → top tier.

Claude Code sessions additionally have named agents in `.claude/agents/` (`explorer`, `implementer`, `reviewer`, `final-reviewer`) and a `PreToolUse` hook that auto-downgrades non-compliant `model: opus` dispatches — keep passing explicit `model` + `subagent_type` when dispatching from Claude Code.

## Repository Structure

```
pipelines/
  foi_pipeline/        # Main FOI pipeline (27 steps) — deep-dive in pipelines/foi_pipeline/AGENTS.md
  document_pipeline/   # PDF → per-section markdown + figures → public/documents/
  actions_pipeline/    # Cross-document action identity + relationships → public-body-actions
  cso_pipeline/        # CSO Register ingestion; resolve_website_urls reused by foi_pipeline
  wdw_pipeline/        # "Who Does What" plain-English descriptions
  datagovie_pipeline/  # data.gov.ie organisation links
  foigovie_pipeline/   # foi.gov.ie body matching
  lobbying_pipeline/   # Lobbying Register body matching
scripts/               # Helper/admin tools — which script for which question: scripts/AGENTS.md
src/lib/               # Shared library: pipeline_runner.py, dataset_publish.py, apify_search.py, ...
tests/                 # Root tests for scripts/ transform_*.py
public/                # Published output, served from the `pages` branch
```

Each step lives in `<pipeline>/steps/<step>/` with `README.md` and `process.py`; generated outputs such as `output.json`, `errors.json`, and status files are usually gitignored. Some steps define `output_schema.json`; where present, it is the validation contract. Outputs are human-readable JSON and should be reviewed rather than hand-edited.

## Override System

A step's `override.json` holds manually-curated records marked `"source_method": "manual"` and `"overridden": true`. They are **never overwritten** by automated re-runs, bypass normal processing (no HTTP calls), and are committed to git as source of truth. `document_pipeline` uses a different, node-level override in `steps/detect_structure/override.json` keyed by `doc_slug` — see [`pipelines/document_pipeline/README.md`](pipelines/document_pipeline/README.md).

## Codeberg Pages Publishing

`data.publicinformation.ie` is served from the `pages` branch, rebuilt from scratch from `public/` by `scripts/publish_pages.sh` every time a commit on `main` touches `public/` (via `.githooks/post-commit`). The hook is not auto-installed — run once per clone:

```bash
git config core.hooksPath .githooks
```

Without it, `scripts/publish_pages.sh` must be run manually after `public/` changes. The script never force-pushes; if the push is rejected, resolve the conflict on `pages` and re-run.

## Dataset Version Bumps

Each catalogued dataset (one `public/catalog/dataset-*.ttl` per dataset) carries two independent signals: `owl:versionInfo` (SemVer schema contract, bumped by hand) and `dct:modified` (content freshness, stamped automatically by `src/lib/dataset_publish.py`'s `stamp_if_changed`).

Bump `owl:versionInfo` by hand only for a breaking (MAJOR) or additive (MINOR) change to field names/types/vocabularies: edit the `OUTPUT_DIR` constant in the dataset's `transform_*.py` (`foi-disclosures` is the exception — `latest/`-only, bump `DATASET_VERSION` instead; `public-bodies` lives in `src/lib/publish_public_bodies.py`, not a `scripts/transform_*.py`, and is regenerated by the FOI pipeline's `export_status` step), edit the `.ttl` to match, add a `public/CHANGELOG.md` entry, then run the script once. Fixing bad data in an existing field is just a content refresh — run the transform and let `stamp_if_changed` update `dct:modified`.

## Common Commands

| Task | Command |
|---|---|
| Run foi_pipeline (full) | `uv run python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --force --stop-on-error` |
| Resume from a step | `uv run python pipelines/foi_pipeline/process.py pipelines/foi_pipeline --from export_status --force --stop-on-error` |
| Run document_pipeline (full) | `cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error` |
| Run document_pipeline (one doc) | `cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error --doc <doc_slug>` |
| FOI pipeline tests | `cd pipelines/foi_pipeline && uv run pytest tests/ -q` |
| Document pipeline tests | `uv run pytest pipelines/document_pipeline/tests -q` |
| Root (transform) tests | `uv run pytest tests/ -q` |
| Manually publish `pages` branch | `scripts/publish_pages.sh` |
| One-time hook setup | `git config core.hooksPath .githooks` |
| Inspect consolidated output | `python3 -c "import json; d=json.load(open('pipelines/foi_pipeline/steps/export_status/output.json')); print(f'Bodies: {len(d[\"public_bodies\"])}')"` |

## Environment / Secrets

- `.env.admin` (copied from `.env.admin.example`, never committed) holds libSQL DB credentials used by `db_upload`: `DATABASE_URL` + `DATABASE_AUTH_TOKEN`. Without it, database steps fall back to the local `local.db` (SQLite).
- Optional LLM-judge backends for evaluation steps: `EVAL_JUDGE_PROVIDER` (`anthropic` / `openai` / `mistral`), `EVAL_JUDGE_MODEL`, `EVAL_JUDGE_BASE_URL` — see the README.
- `document_pipeline`/`documents.yml` is the pipeline's only hand-authored input; a malformed entry is process-fatal. `doc_slug` is a permanent public identifier — never change it once published, and never guess `title`/`public_body_id` (read the PDF / look the id up).

### Environment and Side Effects

| Pipeline/step | Requirement or side effect |
|---|---|
| FOI discovery/search | Network access; `APIFY_TOKEN` for Apify-backed search steps |
| FOI database upload | `.env.admin` for remote libSQL; otherwise local `local.db` fallback |
| FOI evaluation | Optional provider credentials and model settings; may incur LLM cost |
| Document discovery/fetch | Network access and Apify for PDF discovery; cached PDFs are reused where possible |
| Pages publishing | Pushes a rebuilt `pages` branch; run only after reviewing `public/` changes |

## Data Quality and Artifacts

Transform and canonicalization steps must fail closed: preserve source values when they map confidently, log an explicit error when they do not, and never guess, silently null, or silently drop a value. Confirmed contamination may be excluded only when the exclusion is recorded in `errors.json`.

Every review should check source provenance, duplicate counts, missing required fields, unexpected record-count changes, and error types. A run with unresolved reconstruction errors requires human review before publication.

Hand-authored inputs and overrides are the source of truth. `pipeline.json`, `documents.yml`, override files, schemas, and configuration are committed inputs. Step outputs, status files, downloaded assets, local databases, and `public/documents/` are generated or local artifacts unless a dataset workflow explicitly says otherwise. Never overwrite unrelated worktree changes.

## Maintenance

Documentation owner: repository maintainers. Last reviewed: 2026-08-14. Re-run `uv run python scripts/generate_pipeline_docs.py` after changing any `pipeline.json`; CI rejects stale generated sections. Revisit this file when runner flags, pipeline steps, schemas, publishing, credentials, or artifact policy change.

## When to Use Which Documentation

| Scenario | Start Here |
|---|---|
| New to the project | This file → DATA_FLOW.md |
| Deep-dive on FOI pipeline architecture | [pipelines/foi_pipeline/AGENTS.md](pipelines/foi_pipeline/AGENTS.md) |
| Adding a new step | [pipelines/foi_pipeline/steps/AGENTS.md](pipelines/foi_pipeline/steps/AGENTS.md) |
| Running / triaging document_pipeline | [pipelines/document_pipeline/README.md](pipelines/document_pipeline/README.md) |
| Which script answers a data-quality question | [scripts/AGENTS.md](scripts/AGENTS.md) — check before writing a new one-off script |
| Data model evolution | [pipelines/foi_pipeline/AGENTS.md#key-concepts](pipelines/foi_pipeline/AGENTS.md#key-concepts) |
| Troubleshooting data issues | [DATA_FLOW.md](DATA_FLOW.md) |
