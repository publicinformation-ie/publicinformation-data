# Design

## Context

All evidence and numbers below come from the read-only investigation in
`pipelines/document_pipeline/experiments/2026-11-07-structure-corruption-audit/README.md`
(run over cached `extract_pages` sidecars plus committed `public/documents/**`).
The pipeline has not been re-run since 2026-10-13, so all published bundles predate
the TOC-name strategy. Current HEAD still produces 10 invalid trees out of 24
documents. The step lives in `pipelines/document_pipeline/steps/detect_structure/process.py`
(1035 lines), which already carries the strategy cascade, `validate_split`
(defined and tested but called only from `eval/compare.py` and the tests, never
from `process()`), `override.json` merging, and `--doc` scoping via the shared runner.

Constraints that shape the design:
- Repo data-handling principle: fail closed, log to `errors.json`, never guess or silently alter a value; `override.json` is the hand-correction escape hatch.
- Slug-remains-published-URL rule: a retitle cannot rewrite a slug; overrides pin URLs.
- Detection strategies are already pure functions over page sidecars — tests must stay fixture-based and fast.
- CI runs the three pytest suites and `pyright`.

## Goals / Non-Goals

**Goals:**
1. No document publishes a structurally invalid tree unnoticed: validation runs in `process()`, and an unresolved failure blocks the merge that publishes.
2. The demonstrated parser defects are fixed deterministically and at their cause: reading order, TOC-page filtering (for both entry parsing and the legacy strategies), the level invariant, title normalization, and the legacy-cascade guard.
3. The corpus is re-detected, re-audited against the previous run's metrics, and regenerated; residual failures go to `override.json`.

**Non-Goals:**
- No new detection strategy (the TOC-name strategy stays; we harden it).
- No fuzzy matching or LLM inference anywhere in detection.
- No new level-inference signal (see D4 — deferred, with the reason).
- No change to node schema, `detection_method` enum, slug scheme, or the web repo contract.
- No fix for documents whose only honest structure is flat (e.g. the GDA cycle map atlas) beyond letting validation accept genuinely-flat trees.

## Decisions

### D1: Validation placement — inside `process()`, on every produced tree, after overrides

Validate once, after the strategy cascade and *after* `merge_overrides`, before `writer.append`. Alternative: validate inside each strategy — rejected, because it would need duplication in overrides merging, and a merged tree could still be invalid (an override can move a boundary). Failure appends `InvalidStructure` to `errors.json` (doc_slug, check name, offending value) and the record still publishes unaltered — matching how `flat` is handled (`LowConfidenceStructure`): not a step failure, but explicit and triageable.

The step therefore does **not** gate publication; the merge does. This change's acceptance criterion is that no document carries an unresolved `InvalidStructure` when `public/` merges to `main` — each one is cleared by a code fix or a committed `override.json` entry (D9, task 7.4). This is the only place the "nothing stops a corrupt tree from publishing" problem in the proposal's Why is actually closed; logging alone would not close it, and relaxing the check per-document is not an allowed resolution.

### D2: Level invariant — "at least one level-1 node", unconditionally

The audit records `sustainable-mobility-policy` as a `toc` tree with **zero level-1 nodes** (all 17–21 nodes level 2). An invariant conditioned on "the tree contains more than one level" would therefore *not* fire on it: all-level-2 is a single level. So the invariant is unconditional — a non-empty node set with no level-1 node is invalid, however many levels it has. A genuinely flat tree (all level 1, like the GDA cycle atlas') stays valid, since every node is level 1; inventing a synthetic level would violate the no-guessing rule.

This also covers the audit's second reading of the same document (a junk entry as the sole level-1 node, real chapters at level 2): once D5/D7 remove the junk node, the remainder is all level 2 and the invariant fires. The junk title is independently caught by the existing title guard.

The invariant goes into `validate_split` itself rather than alongside it, so `eval/compare.py` and the audit score trees the same way the production step does. Existing tests are unaffected: `test_validate_split_valid_tree_has_no_issues` and `test_validate_split_flags_junk_duplicate_and_gap` both use level-1 nodes.

### D3: Reading order re-implementation — sort in `page_lines()`, not at extraction

`page_lines()` sorts grouped lines by `(y0 rounded to READING_ORDER_Y_GRID, x0, block/line)`. The rounding constant is named and module-level because it decides outcomes: too coarse and a two-column page interleaves, too fine and sub-point baseline noise reorders a single visual line. Doing the sort in the extractor (`extract_pages`) instead was rejected: its output is a cached published artifact for 24 documents, and re-fetching/re-extracting all PDFs to change *reading order only* costs far more than a read-time sort; detect_structure is also the only step that needs line order.

Note `page_lines()`'s existing docstring already claims reading order — the docstring is correct about intent and wrong about the code; this makes it true.

Risk, and why it is more than cosmetic: the TOC-name strategy matches "one to three joined **consecutive** body lines" via `_joined_runs`, where consecutive means block/line order. Re-sorting redefines what that requirement means, so this change also modifies the `TOC-name occurrence-scoring strategy` requirement to pin consecutiveness to reading order. Mitigations: (a) fixtures include a two-column page from the corpus (SMP foreword page 6) to prove nothing degrades; (b) the audit reports each document's TOC match rate against the previously recorded value, and a document whose rate *falls* is reviewed rather than accepted — a silent drop in match rate is the failure mode a per-document fixture cannot catch. If a document regresses, `override.json` corrects it and the fixture documents the case.

### D4: `Chapter N` level anchoring — deferred, not implemented here

Rejected for this change. The SMP and all-island-rail level failures are caused by a polluted indentation bucket: a skipped-but-not-skipped footer line contributes an `x0` no real entry shares, `_infer_levels` sees two buckets, and all real entries land at level 2. D5 removes that line *and* its indentation contribution, after which SMP's entries share one left edge, `_infer_levels` returns the `none` signal, and every entry is level 1 — a valid flat tree. A textual `^(chapter|section|part)\s+\d` anchor would change level inference for every TOC document in the corpus in order to fix a symptom whose cause D3/D5 already remove, and it contradicts the existing spec scenario "missing level signal yields a flat tree".

Sequencing instead: land D3/D5/D6/D7, regenerate, then read the audit's level distributions (task 7.2). If a document's only honest level signal is genuinely a `Chapter N` prefix — i.e. it has real sections that *must* nest and nothing else distinguishes them — that is a separate, evidenced change with its own fixtures. The fallback alternative considered and also rejected for now: inferring levels of matched body occurrences by font size, which couples level inference to typography thresholds.

### D5: TOC-page filtering — skip lines, never reinterpret them

Inside `_parse_toc_page`: (a) any line that is a bare page number (`^\d{1,3}$`) is skipped regardless of x (the right-column guard stays too — both are page numbers); (b) lines whose normalized text is in the running-header set are skipped (the set is already computed in `from_toc` — pass it in); (c) entry collection starts after the `contents` title *in reading order*, which D3 makes possible. Critically, a skipped line must also contribute **no `x0` to `_infer_levels`** — the entries list is the only input to level inference, so skipping before entry construction achieves this, and the spec states it explicitly because it is the mechanism that fixes SMP's levels (D2/D4).

Skipping is a classification, not a rewrite — consistent with the confirmed-contamination rule (drop, but visibly, i.e. only on the TOC page itself and only for texts that could never be headings). Alternative: pre-strip header/footer by y-band from every page — rejected, too broad for this change and risks eating real short headings near page margins.

### D5b: TOC pages are excluded from the legacy strategies and the supplement

`build_occurrence_index` already excludes TOC pages so a TOC line can never be selected as a boundary, but `from_numbering`, `from_font_hierarchy`, and `_supplement_numbered_nodes` iterate every page with no such exclusion. `_supplement_numbered_nodes` calls `from_numbering(pages, body)` over the whole document, so a TOC line can enter even a `toc`-method tree. This is the actual cause of the emra, `code-of-practice-recreational-craft`, and `national-cycle-network-plan` dot-leader chapters, and it is unfixed by any amount of title cleaning.

Implementation: `parse_toc` already returns `toc_pages`; thread that set through `detect_structure` into `_legacy_cascade` and into `_supplement_numbered_nodes`, and have both strategies skip those page numbers. It must apply even when the TOC-name strategy did not fire (no usable TOC, or match rate below the gate) — the fallback path is exactly where these documents end up, so excluding only on the `toc` path would fix nothing for them. The `outline` path does not scan pages and is unaffected.

### D6: Title normalization — narrow, and never ahead of the dot-leader guard

One shared cleanup applied wherever a title is accepted: strip a leading `|`/`-` fragment (nifti, final-progress-report), strip *trailing* dot leaders plus a glued page number (which `_strip_toc_suffix` already does for the TOC path), strip control characters (ev-infrastructure). Then `is_heading_candidate` makes the accept/reject call, unchanged in wording. One shared helper rather than per-strategy patches, because nifti's `|` and final-progress-report's `-` came from *different* strategies.

**Interior dot leaders are not stripped.** `is_heading_candidate` rejects a title matching `DOT_LEADER_RE` (`process.py:281`), and that rule is the signal that a line is a table-of-contents line rather than a heading. Stripping interior leaders before the guard would make the rule unreachable and convert `1.1 Landscape and Visual ......... 23` into a clean-looking `Landscape and Visual` node — a TOC line published as a chapter, now invisible to validation. That is worse than the visible junk it replaces and is precisely what the repo's "never silently rewrite a field to make it fit" rule forbids. The dot-leader documents are fixed by D5b instead.

### D7: Legacy-cascade guard + joining — mirror the TOC strategy's guard; the join cannot be shared

`from_font_hierarchy`/`from_numbering` call `is_heading_candidate`, which is the whole fix for the bare-numeral and glyph kills (`1`–`6`, `2040`, `21`, `l`, `”`) via its letters rule and `len(t)==1`, unchanged.

The line join is a separate mechanism from the TOC strategy's `_joined_runs`, and deliberately so. `_joined_runs` joins speculatively (k=1,2,3) and lets an exact match against a known TOC title decide which run was right; the legacy cascade has no target string, so it must *decide* the join from style and geometry alone. Unifying them would mean giving `_joined_runs` a decision rule it does not need and should not have. What is shared is the predicate: same rounded size, same bold class, vertical adjacency within `HEADING_JOIN_MAX_GAP` (a module constant, expressed as a multiple of the heading's own line height), first line not sentence-ending, capped at two lines. Thresholds are named constants pinned by fixtures in both directions — SMP page 6 has two same-size pull-quote columns that must *not* join; action-plan-2022-2025 page 3 has the `Safe and Green` + `Mobility` pair that must. The cap at two keeps a mis-join bounded to one sanded-together heading.

### D8: Overrides for residual cases — decision table, not instructions

Documents expected to still fail after D1–D7 are enumerated from the audit, with an override shape per failure mode:
- `national-cycle-network-plan` (chapters built from page-number prefixes / dot-leader lines): D5b is expected to remove the dot-leader chapters; any residue gets hand-written node lists for the junk chapters → replace node, or `flat` if evaluation shows nothing salvageable.
- `gda-cycle-network-plan-2022` (a genuinely flat map atlas): no override needed — flat trees pass the invariant.
- emra, `code-of-practice-recreational-craft`: D5b is the expected fix; overrides only for stragglers found post-regeneration.
Overrides are committed to git as source of truth and never regenerated. An override is also the only sanctioned way to clear an `InvalidStructure` other than a code fix (D1).

### D9: Regeneration is part of this change, not a separate one

A full document-pipeline re-run from `detect_structure` (first since 2026-10-13) changes every bundle. Sequencing: code + tests first on this branch, then `cd pipelines/document_pipeline && uv run python process.py --from detect_structure --force --stop-on-error`, then re-run `audit.py` on the regenerated output and compare per-document metrics against the previous run, then review the `public/` diff per the AGENTS.md publishing rule before merge. The merge criterion from D1 applies: zero unresolved `InvalidStructure`. Rollback is git-native (`revert` the branch); nothing is published until `public/**` hits `main`.

### D10: Fixture strategy — real page sidecars, path-pinned by the failures they encode

Fixtures, each from a real page: (1) SMP page 4 (footer-number pollution, no indentation bucket from the skipped line, resulting level-1 tree), (2) SMP page 28 (quote-glyph reject), (3) SMP page 9 (oversized chapter numeral + real title), (4) action-plan-2022-2025 page 3 (`Safe and Green`/`Mobility` join), (5) nifti TOC page (pipe-stripping), (6) emra page 2 (dot-leader TOC lines — asserting the lines are excluded as TOC-page lines, *and* that an interior dot-leader line reaching a strategy is rejected rather than cleaned), (7) SMP page 6 two-column page (reading-order sort, and the must-not-join pair). Fixtures live in `tests/fixtures/pages_<name>.json` alongside the existing `pages_font.json` pattern, each asserting the *invariant*, not a node-for-node snapshot (snapshot-fragility would make corpus-sensitive tests churn).

## Risks / Trade-offs

- **Slug churn after regeneration** → bundled meta.json/llms.txt/full.md paths change where titles change; per the repo rule, slugs for already-published URLs must not change. Mitigation: check for orphans against `override.json`, then pin by hand-committed overrides for documents whose URLs already shipped.
- **Reading-order sort degrades a match rate silently** → a document still validates but matches fewer TOC entries. Mitigation: the audit's per-document match-rate comparison against the previous run is an acceptance criterion, not a diagnostic (D3, task 7.2).
- **Regeneration magnitude** — every bundle changes at once; the review step on the diff is a known manual cost (repo convention). Mitigation: `audit.py --published --head` before and after, so the review checks titles and metrics, not raw JSON.
- **TOC-page exclusion over-reach** — a document whose detected "TOC page" is actually a content page would lose that page's headings entirely. Mitigation: TOC-page detection is already gated by `_page_toc_signals`/`_page_kind` and is already trusted to exclude the page from occurrence candidates; the exclusion extends an existing trust rather than adding a new one, and a lost heading shows up as a coverage gap in `validate_split`.
- **Validation too strict** → a legitimately odd but correct tree is flagged. Mitigation: the only new check is "at least one level-1 node", which no correct tree can fail — `assign_hierarchy` makes the first node a root regardless of level, so a tree with no level-1 node is mis-levelled by construction.
- **Threshold drift for joining** — mis-joined headings would sand two headings into one; bounded by named constants, fixtures from both directions, and the cap at two lines.

## Migration Plan

1. Land code + tests (no data change); CI green (`uv run pytest pipelines/document_pipeline/tests -q`, plus `uv run pyright`).
2. Re-run the document pipeline from `detect_structure` on this branch: regenerates `output.json`/`errors.json`/`public/documents/**` end-to-end.
3. Re-run `audit.py`; compare per-document metrics against the previous run; documents still failing → write `override.json` entries, re-run scoped (`--doc <slug> --force`).
4. Review `public/` diff (AGENTS.md rule), confirm zero unresolved `InvalidStructure` (D1), then merge → Pages deploy publishes the fix.

## Open Questions

- Does any corpus document genuinely need the deferred `Chapter N` level anchor (D4)? Answered by task 7.2's level-distribution audit after regeneration, not before. If yes, it becomes its own change rather than being folded in here.
