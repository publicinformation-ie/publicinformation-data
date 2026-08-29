# extract_relationships

Second step in `actions_pipeline`'s own step sequence, after `resolve_action_identity`. Builds the link table between actions — how a commitment relates to another action in the same corpus, or to an action in a plan the corpus doesn't (yet) ingest.

## Why three methods, deliberately unequal in trust

- **extracted** — parenthetical cross-references (`(RSS action 8)`, `(Complements CAP action 233)`) and section-level groupings (a `COMPLEMENTARY ACTIONS IN <plan>` heading in the document's structure tree). Both are mechanical and published directly, but only ever as `complements` or `references` — never as a lineage term. "Complements" does not mean "is the same commitment as"; an automated lineage guess from a cross-reference would splice two unrelated commitments into one history.
- **declared** — narrative continuity phrases in report prose ("carried forward", "superseded by", "which incorporated…"). These are only ever *detected and logged* as `RelationshipCandidate` for a human to review and promote into the curated file. Prose does not state a lineage edge precisely enough to publish one automatically — the same phrase could describe a genuine renumbering or a loose paraphrase.
- **curated** — `action_relationships.yml`, loaded and strictly validated by `relationships.py`. This is the *only* way a lineage edge (`renumbered_as`, `supersedes`, `split_into`, `merged_into`, `carried_forward_to`) can enter the dataset, because no document in the corpus states a renumbering machine-readably.

## The two families

Every edge's `relationship` term maps to a `family` (`relationships.VOCABULARY`): `lineage` or `reference`. `family` is published as data on every edge rather than left for each consumer to infer from the term, because that inference is exactly the failure mode this step exists to prevent — a consumer deciding on its own that "complements" implies continuity and silently splicing two unrelated commitments into one timeline. Only curated edges can carry `lineage`; every extracted edge is `reference`.

## Null `to_action_id` is a first-class state, not an error

"SMP action 19 complements Climate Action Plan action 233" is a real, useful fact even before CAP is ingested into this corpus. Rather than dropping the edge or refusing to publish it, `to_action_id` is published as `null` alongside `to_plan_hint`/`to_action_number`, which preserve the original citation. If the target plan is added to the corpus later, re-running this step resolves the edge for free — no schema change, no migration, no re-authoring of the curated file. `UnresolvedRelationshipTarget` is deliberately not an error type: an external target is not a fault, it's the expected shape of most cross-plan citations at this stage of the corpus.

## Why `PLAN_HINT_SLUGS` is empty at v1.0.0

The obvious candidate for resolution, `RSS` (Road Safety Strategy), is *not* safe to wire up yet: the corpus's Road Safety Strategy document is the *Phase 2 Action Plan 2025-2027*, whose action numbering is a different scheme from the *RSS 2021-2030* numbering the SMP actually cites in its parentheticals. Resolving `RSS` against that document today would silently attach every SMP cross-reference to the wrong row. The resolution path (`hint_slugs` in `build_edges`) is fully implemented and tested — adding a hint once a correctly-numbered plan is ingested is a one-line data change, not new code.

## Inputs

- `--input`: `resolve_action_identity/output.json` (wired via `pipeline.json`) — `actions` and `observations`.
- `document_pipeline/steps/detect_structure/output.json`, located by repo-root path — the structure tree used for section-level groupings. Missing or absent is not fatal; that plan simply contributes no section edges.
- `pipelines/actions_pipeline/action_relationships.yml`, via `relationships.load_relationships()` — the curated file. A missing file is valid (no curated edges); a malformed one is process-fatal (`InvalidRelationshipFile`), uncaught here on purpose, exactly like `documents.yml`.

## Output

`output.json` — `{ metadata, relationships: [...] }`.

| field | Description |
|---|---|
| `from_action_id` | The action asserting the relationship |
| `to_action_id` | The resolved target action, or `null` if the target plan isn't in the corpus |
| `to_plan_hint` | The plan name/abbreviation as cited in the source text |
| `to_action_number` | The cited action number, or `null` for a plan-level (section grouping) edge |
| `relationship` | A term from `relationships.VOCABULARY` |
| `family` | `"lineage"` or `"reference"`, denormalised from `relationship` |
| `method` | `"extracted"`, `"declared"`, or `"curated"` |
| `asserted_in` | The plan slug, report slug, or curated-file name that made the claim |
| `evidence` | The source text (parenthetical or section heading), or the curated file's reviewed basis |

`metadata.by_method` gives the count of edges per method, so the mix (mostly `extracted` today, `curated` empty at v1.0.0) is visible without opening the file.

## Errors

| `error_type` | Scope | Cause |
|---|---|---|
| `RelationshipCandidate` | observation | Progress text contains a narrative continuity phrase; logged for a human to promote into `action_relationships.yml`, never auto-published |

`InvalidRelationshipFile` (from `relationships.py`) is process-fatal, not logged here — a malformed curated file halts the run, matching `documents.yml`.

## Running it

```bash
cd pipelines/actions_pipeline
uv run python process.py --force --stop-on-error --verbose
```

This step always rebuilds the whole table regardless of `--force` — like `resolve_action_identity`, it's a whole-corpus join, not an incrementally-resumable per-record step.
