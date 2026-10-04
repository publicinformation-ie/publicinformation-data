## Context

See proposal.md — Why. The runner (`src/lib/pipeline_runner.py`) is a single shared module used by every pipeline's `process.py`. Its step loop already tracks a `skip_until` sentinel for `--from` and resolves each step's output path (relative or absolute/upstream) before deciding to skip, run, or validate. `--to` must slot into that same loop without disturbing the existing skip/staleness/absolute-path branches, which are covered by tests in `pipelines/foi_pipeline/tests/test_pipeline_runner.py`.

## Goals / Non-Goals

**Goals:**

- Add `--to` as a first-class, documented runner option with inclusive stop semantics.
- Keep the change confined to the runner and its tests; no step or `pipeline.json` changes.
- Make invalid ranges loud instead of silent.

**Non-Goals:**

- Changing how steps are ordered, discovered, or staleness-checked.
- Adding step-by-name execution of a single step bypassing order (that remains `--from X --to X`).
- Any change to per-step CLIs or their arguments.

## Decisions

### D1: Resolve start/end indices up front; iterate from step 0 and stop after the end step

Resolve `--from`/`--to` against the ordered `steps` list once before the loop (start defaults to 0, end to the last step), making validation (D2) a natural pre-check. The loop still iterates from step 0: steps before the start index follow the existing `--from` skip path (print "Skipping … (before --from …)" and set `prev_out` to their resolved output), and the loop breaks after processing the step at the end index. Iterating from 0 preserves the `prev_out` input chain — the first windowed step receives the prior step's output as its `--input` and staleness baseline, exactly as `--from` behaves today. The per-step body (absolute-path handling, staleness, `always_run`, subprocess args) is unchanged.

**Alternatives considered:** (a) pure index slicing iterating only `[start, end]` — rejected: `prev_out` would be `None` for the first windowed step, silently changing its `--input` (falls back to the step directory) and staleness check, and it contradicts D4's skip messages for steps before `--from`. (b) a `stop_after` sentinel set to the `--to` step without pre-resolved indices — rejected: it still needs the same validation pass to catch an unknown `--to`, and index-based bounds make the window explicit.

### D2: Validate both `--from` and `--to` against the step list, exiting non-zero

If a named step is absent, or `--to` precedes `--from`, the runner exits non-zero with a message naming the value(s). This also fixes a latent `--from` bug: an unknown `--from` currently never matches, so every step is skipped and the run silently does nothing. Making invalid input loud is consistent with the repository's fail-closed principle. The behaviour change only affects invocations that were already broken (they produced no useful work), so it is treated as a fix rather than a breaking change.

**Alternative considered:** leave `--from` unvalidated to avoid any behaviour change, and validate only `--to`. Rejected: it preserves a silent no-op and leaves the two flags inconsistent.

### D3: `--to` is inclusive and composes by construction

`--to` includes the named step, matching `--from`'s inclusive start. Composition with `--force`, `--stop-on-error`, `--public-body`, `--doc`, absolute-path upstream steps, and `always_run` needs no special handling because the range only decides *which* steps are visited; each visited step follows the existing branches. Absolute-path upstream steps inside the window keep their existing "validate output, set prev_out, no subprocess" behaviour.

### D4: Out-of-window steps are skipped silently (not printed as "before --from")

Steps after `--to` are simply not visited, so they produce no "Skipping …" line. Steps before `--from` keep their existing "Skipping … (before --from …)" message. This keeps `--to` output clean: the run ends at the requested step.

## Risks / Trade-offs

- [Existing scripts rely on `--from <unknown>` being a silent no-op] → Unlikely and undesirable; the new error is explicit and names the value. Documented in the change's tasks as a deliberate fix.
- [Loop refactor for `--to` could regress existing skip/absolute-path behaviour or the `prev_out` input chain] → The existing runner test suite (including absolute-path and `always_run` cases) must pass unchanged; new tests cover the range edges, the first windowed step's input chain, and flag composition.
- [`--to` used without `--force` may still skip everything as "up to date"] → Expected and unchanged; `--to` bounds the run, it does not force it. Documented alongside `--from`.

## Migration Plan

Purely additive CLI option plus the D2 validation fix. No data migration. Rollback = revert the runner change. Update docs (`AGENTS.md`, `README.md`, `pipelines/foi_pipeline/AGENTS.md`) in the same change.

## Open Questions

None.
