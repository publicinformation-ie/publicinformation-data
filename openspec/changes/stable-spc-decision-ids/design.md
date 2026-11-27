# Design

## Context

`extraction.py` numbers decisions by position after extraction (`d{index:02d}`); `drop_decisions` in `override.json` names IDs, so it depends on that numbering. `design.md` D8 of the archived `add-spc-minutes-pipeline` change accepted this and relied on the cache for stability. The step 5 attempt showed the cache is not enough: a prompt version change is a normal event and renumbers decisions. Published identity elsewhere (public-body actions) is permanent; see the motions dataset for the same ordinal pattern, which is out of scope here.

## Goals / Non-Goals

**Goals:**
- A published decision URI points at the same decision forever, across prompt, model and extraction changes.
- No change to any currently published ID, field or file shape.
- Follow the repo's fail-closed rule: drift is an error for a human, never a guess.

**Non-Goals:**
- Changing the ID format, adding a field, or a version bump.
- Applying the same scheme to motions IDs.
- Deciding whether to adopt prompt `spc-items-v2`; that is a reviewed content change after this one.

## Decisions

**D1. A committed registry, not a hash.** `extract_spc_items/decision_ids.json` is a hand-reviewable input like `override.json`: per meeting, a list of entries `{id, item_key, quote_key, status: "active"|"retired", reason?}`. `quote_key` is the whitespace-normalised quote. Alternative considered: an ID hashed from item key and quote. It breaks exactly where the model's quote boundaries drift between runs (seen between v1 and v2), and it changes the `dNN` format. A registry keeps the spec's `d<NN>` form and every live URI.

**D2. Matching.** Exact `(item_key, quote_key)` reuses the ID. Otherwise, if the new quote and an unmatched active entry of the same item contain one another (token-sequence containment, as in the sweep scorer), raise `DecisionIdAmbiguous` for that decision and publish neither. Otherwise allocate `max(all numbers in the meeting, including retired) + 1`. Overlap of any kind is never resolved automatically.

**D3. Who writes the registry.** The step appends entries for brand-new decisions and never edits or removes an existing entry, so the git diff is a reviewable record. Mapping a drifted quote, changing a quote key or retiring an entry is a manual edit. This differs from `override.json`, which automation never writes, because new meetings must be able to register decisions without a hand step.

**D4. Missing and retired entries.** An active entry with no match in a run raises `RegisteredDecisionMissing`; it is not published and its number stays reserved. A retired entry that matches an extracted quote suppresses it silently, with a count in the step report. This replaces `drop_decisions`; the `d01` of 2025-11-20 becomes a retired entry and the `drop_decisions` mechanism, and its stale-target check, are removed.

**D5. Seeding.** A one-off script seeds the registry from the current `output.json` (17 decisions) and adds the retired 2025-11-20 `d01`, recorded with the quote from the v1 cache. A test asserts every published decision ID in `public/latest/spc-meetings/decisions.jsonld` is present and active in the registry with the same quote.

**D6. Dataset surface.** No field is added. The dataset README gains a short ID-stability statement; `public/CHANGELOG.md` records it under a Documentation heading without a version bump.

## Risks / Trade-offs

- A re-extraction that renders a decision differently now produces errors instead of silently changing data → this is intended; the cost is a manual registry edit per drifted decision.
- A hand edit that reuses a number would break identity → a test rejects duplicate numbers within a meeting and any reuse of a retired number.
- The registry is a new committed input to keep in step with `public/` → the seeding test ties it to the published decisions.
- Decisions of meetings not yet extracted get registered on first run, so an early prompt-quality problem is frozen into an ID → such an entry can be retired, never reused.

## Migration Plan

1. Seed the registry; confirm it reproduces the current `output.json` and the published IDs with no diff in `public/`.
2. Ship the code with the v1 prompt. The existing run must produce identical output.
3. Separately, adopt prompt v2 from `.scratch/spc-prompt-v2.patch` using the cached v2 responses (no paid calls) and review the resulting errors and content differences before any publish.
4. Rollback: revert the commit; registry and override are plain committed files.
