# actions_pipeline

Turns `document_pipeline`'s per-document plan actions and report observations into one cross-document dataset tracking a public body's declared commitments and what was later reported against them — `public-body-actions`. Unlike `document_pipeline`, this pipeline is corpus-shaped: its steps read the *entire* upstream output at once, not one document at a time, because minting a stable identity and joining reports onto plans both require seeing every plan and every report together.

The authoritative step order is defined in [`pipeline.json`](pipeline.json). Steps run sequentially; each writes its output to `steps/<step>/output.json`.

## Upstream dependency

Step 1 is an absolute cross-pipeline reference — `/pipelines/document_pipeline/steps/extract_actions` — the same mechanism `foi_pipeline`'s first step uses to consume `cso_pipeline`. The runner asserts that step's `output.json` exists and is non-empty rather than running a subprocess for it; a missing or empty upstream output exits with *"run document_pipeline first"*. Satisfy it by running `document_pipeline` to completion first:

```bash
cd pipelines/document_pipeline
uv run python process.py --force --stop-on-error
```

## Steps

1. [`extract_actions`](../document_pipeline/steps/extract_actions/) *(document_pipeline)* — plan-declared actions, one record per plan document.
2. [`resolve_action_identity`](steps/resolve_action_identity/) — mints a stable `{plan_slug}#{action_number}` identity for every plan action, resolves each action's original deadline from the plan that declares it (never from a report), and joins every report observation (`document_pipeline/steps/extract_action_status`) onto its action via the report's explicit `reports_on`.
3. [`extract_relationships`](steps/extract_relationships/) — builds the link table between actions: mechanical `complements`/`references` edges extracted from parenthetical cross-references and section groupings, published directly; narrative continuity phrases logged as `RelationshipCandidate` for human review; and lineage edges (`renumbered_as`, `supersedes`, …) sourced only from the curated `action_relationships.yml`.

## Running it

Run these from inside `pipelines/actions_pipeline/` — the runner's pipeline directory defaults to the current working directory, not the script's location.

```bash
cd pipelines/actions_pipeline
uv run python process.py --force --stop-on-error --verbose
```

Run the test suite with `uv run pytest pipelines/actions_pipeline/tests -q`.

## `errors.json` triage

Every step writes `errors.json` (truncated to `[]` at the start of each run), tagged by `error_type`. `resolve_action_identity`'s error types (see [its README](steps/resolve_action_identity/README.md) for the full table):

| `error_type` | Cause |
|---|---|
| `UnresolvedActionNumber` | A plan action cell has no leading ordinal, or a report observation's action number matches no plan action |
| `DateParseError` | A plan action's timeline cell is non-empty but yields no confident deadline |
| `DeadlineDivergedAtFirstReport` | Informational — the earliest report's deadline for an action already differs from the plan's original deadline |
| `RelationshipCandidate` | Informational, any count — a narrative continuity phrase detected in report prose; logged for a human to review and promote into `action_relationships.yml`, never auto-published (see [`extract_relationships`'s README](steps/extract_relationships/README.md)) |

See the parent [`AGENTS.md`](../../AGENTS.md) for repository-wide conventions and where `actions_pipeline` fits alongside the other pipelines in this repo.
