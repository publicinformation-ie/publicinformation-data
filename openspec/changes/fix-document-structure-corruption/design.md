# Design

## Context

All evidence and numbers below come from the read-only investigation in
`pipelines/document_pipeline/experiments/2026-11-07-structure-corruption-audit/README.md`
(run over cached `extract_pages` sidecars plus committed `public/documents/**`).
The pipeline has not been re-run since 2026-10-13, so all published bundles predate
the TOC-name strategy. Current HEAD still produces 10 invalid trees out of 24
documents. The step lives in `pipelines/document_pipeline/steps/detect_structure/process.py`
(1035 lines), which already carries the strategy cascade, `validate_split`
(defined + tested but never invoked from `process()`), `override.json` merging,
and `--doc` scoping via the shared runner.

Constraints that shape the design:
- Repo data-handling principle: fail closed, log to `errors.json`, never guess or silently alter a value; `override.json` is the hand-correction escape hatch.
- Slug-remains-published-URL rule: a retitle cannot rewrite a slug; overrides pin URLs.
- Detection strategies are already pure functions over page sidecars — tests must stay fixture-based and fast.
- CI runs the three pytest suites and `pyright`.

## Goals / Non-Goals

**Goals:**
1. No document publishes a structurally invalid tree unnoticed (guardrail wired into `process()`).
2. The five demonstrated parser defects are fixed deterministically (reading order, TOC-page filtering, level anchoring, title normalization, legacy-cascade guard).
3. The corpus is re-detected, re-audited, and regenerated; residual failures go to `override.json`.

**Non-Goals:**
- No new detection strategy (the TOC-name strategy stays; we harden it).
- No fuzzy matching or LLM inference anywhere in detection.
- No change to node schema, `detection_method` enum, slug scheme, or the web repo contract.
- No fix for documents whose only honest structure is flat (e.g. the GDA cycle map atlas) beyond letting validation accept genuinely-flat trees.

## Decisions

### D1: Guardrail placement — inside `process()`, on every produced tree, not per-strategy

Validate once, after the strategy cascade and *after* `merge_overrides`, before `writer.append`. Alternative: validate inside each strategy — rejected, because it would need duplication in overrides merging, and a merged tree could still be invalid (an override can move a boundary). Validation failure appends `InvalidStructure` to `errors.json` (doc_slug, check name, offending value) and the record still publishes — matching how `flat` is handled (`LowConfidenceStructure`): not a failure state, but explicit and triageable. The tree itself is never silently rewritten.

### D2: Level invariant scope — "at least one level-1 node when >1 level exists"

Exactly the SMP failure (`toc`, 17 nodes, all level 2). A genuinely flat tree (all level 1, like the GDA cycle atlas') stays valid — inventing a synthetic level would violate the no-guessing rule. Alternative: require ≥1 level-1 *or* flat; folding the flat case into "only one level exists" keeps it one check. Fixture-tested with the SMP page-4 chain.

### D3: Reading order re-implementation — sort in `page_lines()`, not at extraction

`page_lines()` sorts grouped lines by `(y0 rounded to ~pt grid, x0, block/line)`. Doing it in the extractor (`extract_pages`) instead was rejected: extract_pages output is a cached published artifact for 24 documents, and re-fetching/re-extracting all PDFs to change *reading order only* is much more expensive than a read-time sort; also detect_structure is the only step that needs line order. Risk: two-column pages where interleaving left/right columns mid-page would scramble entries that are currently in order. Mitigation: sort is stable and only affects lines that raw order had out of place (header/footer/title blocks); fixtures include a two-column page from the corpus (SMP foreword page 6) to prove nothing degrades. If a document regresses, `override.json` corrects it and the fixture documents the case.

### D4: `Chapter N` anchoring — a new signal ahead of the indent heuristic, not a replacement for the cascade

_infer_levels gains: if ≥2 entries match `^(chapter|section|part)\s+\d`, level = 1 for anchored entries, greater than 1 for entries until the next anchor. Numbering depth (explicit `1.1`) still wins when present. Rationale: SMP and all-island rail both carry un-indented TOCs where the *only* level signal in the text is the `Chapter N` prefix; indentation produced both documents' failure (one x0 bucket → all L2). Alternative: infer levels of *matched body occurrences* by font size — rejected for this change: the occurrence scores exist but mapping them to levels couples the anchor to typography thresholds; the textual prefix is deterministic and matches the documents' own semantics. SMP the fix path for its footer/indent bug separately (already D3/D5).

### D5: TOC-page filtering — skip lines, never reinterpret them

Inside `_parse_toc_page`: (a) any line that is a bare page number (`^\d{1,3}$`) is skipped regardless of x (the right-column guard stays too — both are page numbers); (b) lines whose normalized text is in the running-header set are skipped (the set is already computed in `from_toc` — pass it in); (c) entry collection starts after the `contents` title *in reading order*, which D3 makes possible. Skipping is a classification, not a rewrite — consistent with the confirmed-contamination rule (drop, but visibly, i.e. only on the TOC page itself and only for texts that could never be headings). Alternative: pre-strip header/footer by y-band from every page — rejected, too broad for this change and risks eating real short headings near page margins.

### D6: Title normalization — one shared cleanup, applied wherever a title is accepted

`normalize_heading_text` already strips control chars and trailing punctuation — extend the *title-producing* paths with: strip a leading `|`/`-` fragment (nifti, final-progress-report), strip dot leaders + trailing numbers (emra, national-cycle-network), strip control chars (ev-infrastructure), then `is_heading_candidate` (letters-required) makes the final accept/reject call, unchanged in wording. One shared helper rather than per-strategy patches because commands nifti's `|` and final-progress-report's `-` came from *different* strategies.

### D7: Legacy-cascade guard + joining — mirror the guards the TOC strategy already has, no new heuristics

`from_font_hierarchy`/`from_numbering` call `is_heading_candidate` and join consecutive same-size/same-font-class lines up to two, breaking on sentence-ending or style change. Getting the *exact* join rule right matters: text spanning two lines mid-paragraph at heading size would otherwise over-join, so the join requires (a) same rounded size, (b) same bold-font class, (c) adjacency (block/line sequence across blocks, then y-gap ≤ 1.5× the heading's own line height), (d) first line not sentence-ending. These thresholds are pinned by the fixtures (SMP page 6 has two same-size pull-quote columns *not* to join; action-plan-2022-2025 page 3 has the pair to join). The bare-numeral kills (`1`–`6`, `2040`, `21`, `l`, `”`) come from `is_heading_candidate`'s letters rule + `len(t)==1`, which is unchanged.

### D8: Overrides for residual cases — decision table, not instructions

Documents expected to still fail after D1–D7 are enumerated from the audit, with an override shape per failure mode:
- national-cycle-network-plan (0-level chapters from page-number prefixes / dot-leader lines): hand-full node lists for the 4 junk chapters → replace node, or `flat` if evaluation shows nothing salvageable.
- extra-fragile maps (`gda-cycle-network-plan-2022`, genuinely flat): no override needed — flat trees pass the invariant.
- emra, code-of-practice-recreational-craft (dot-leader TOC lines feeding `numbering`): D6 title-cleanup + D7 guard are expected to resolve these; overrides only for stragglers found post-regeneration.
Overrides are committed to git as source of truth and never regenerated.

### D9: Regeneration is part of this change, not a separate one

A full document-pipeline re-run from `detect_structure` (first run since 2026-10-13) changes every bundle. Sequencing within the run: code + tests first on this branch, then `cd pipelines/document_pipeline && uv run python process.py --force --stop-on-error`, then re-run `audit.py` on the regenerated meta.json, then review the `public/` diff per the AGENTS.md publishing rule before merge. Rollback is git-native (`revert` the branch); nothing is published until `public/**` hits `main`.

### D10: Fixture strategy — real page sidecars, path-pinned by the failures they encode

Six new fixtures, each from a real page: (1) SMP page 4 (footer-number pollution, `Chapter N` anchoring, all-L2 invalidation), (2) SMP page 28 (quote-glyph reject), (3) SMP page 9 (oversized chapter numeral + real title), (4) action-plan-2022-2025 page 3 ("Safe and Green"/"Mobility" join), (5) nifti TOC page (pipe-stripping), (6) emra page 2 (dot-leader TOC lines) + a two-column page (SMP page 6) for the reading-order sort. Fixtures live in `tests/fixtures/pages_<name>.json` alongside the existing `pages_font.json` pattern, each asserting the *invariant*, not a node-for-node snapshot (snapshot-fragility would make corpus-sensitive tests churn).

## Risks / Trade-offs

- **Slug churn after regeneration** → bundled meta.json/llms.txt/full.md paths change where titles change; per the repo rule, slugs-published-URLs must not change for URLs that already shipped. Mitigation: check for orphans in `override.json`, then fix by hand-committing overrides for documents whose URLs exist.
- **Validation gating too strict** → a legitimately odd but correct tree (flat, or one level-3 chapter) is flagged without a level-1. Mitigation: the invariant only fires when >1 level exists AND no level-1; a flat tree (one level) is valid, so the map-atlas case stays clean.
- **Regeneration magnitude** — every bundle changes at once; the review step on the diff is a known manual cost (repo convention). Mitigation: `audit.py --published --head` before and after, so the review checks titles, not raw JSON.
- **TOC-page filtering over-reach** — skipping "any bare-number line" could theoretically eat a lone-numbered heading on a TOC *page* whose body heading is a bare number. Tolearance: no numbered-heading-only documents are expected in the corpus; `TocEntryUnmatched`-style error logging keeps any real loss visible in triage.
- **Threshold drift for joining** — mis-joined headings would sand two headings into one; bounded by fixtures from both directions and by keeping the join capped at two lines.

## Migration Plan

1. Land code + tests (no data change); CI green (`uv run pytest pipelines/document_pipeline/tests -q`, plus `uv run pyright`).
2. Full document-pipeline re-run on this branch: regenerates `output.json`/`errors.json`/`public/documents/**` end-to-end.
3. Re-run `audit.py`; documents still failing → write `override.json` entries, re-run scoped (`--doc <slug> --force`).
4. Review `public/` diff (AGENTS.md rule), then merge → Pages deploy publishes the fix.

## Open Questions

(None — every ambiguity found during investigation has a decision above; the audit's per-document numbers are already in the experiment README and don't gate any decision.)
