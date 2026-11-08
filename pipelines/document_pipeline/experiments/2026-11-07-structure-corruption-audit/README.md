# Document structure corruption audit — 2026-11-07

Why published document bundles carry corrupt tables of contents, which other
documents share the problem, and the proposed fix. Read-only investigation:
it ran over cached `extract_pages` + `detect_structure` output in the main
checkout (step outputs are gitignored and therefore absent from worktrees) and
over the committed `public/documents/**/meta.json` artifacts.

## Symptom

`sustainable-mobility-policy` publishes a chapter list of bare numerals:

```
Front Matter → 1 → Foreword → Summary → 2 → 3 → 4 → 5 → 6
```

(see committed `public/documents/sustainable-mobility-policy/llms.txt`,
`## Chapters`). Section titles inside chapter 3+ include `"` and section
titles like `approach` / `engagement` / `and transport planning` are line
fragments of wrapped headings.

## Finding 1 — the published bundles are stale, not the current best output

`public/documents/**` and every step `output.json` were last built
**2026-10-13** (meta `built_at`, file mtimes, commit `c72de41e`). The
TOC-name strategy landed **2026-10-17** (`342f926d`), so everything published
predates it and was produced by the legacy `numbering`/`font` cascade.

Running the **current** `detect_structure` on the cached page sidecars changes
9 `font` documents to `toc` with materially better trees (year reports × 3,
action-plan 2026-2030, gda-cycle-network-plan, all-island-rail, nta-statement,
moving-together …). **Re-running the pipeline from `detect_structure` onward is
necessary regardless of any code change** — but it is not sufficient, see
Finding 2.

## Finding 2 — the old cascade itself is defective

`from_font_hierarchy()` (`steps/detect_structure/process.py:329`) accepts
**every** line whose size maps to a heading level, with no
`is_heading_candidate` guard, no wrapped-line joining, no context. On
`sustainable-mobility-policy`, `heading_levels` maps `{119.4: 1 (giant
chapter numerals), 70.0: 2 (pull-quote glyph `””), 40.0: 3 (real titles at
16pt are *not* in this mapping …)}`. Verified on the page sidecars:

| Page | Size | Font | Text | Becomes |
|---|---|---|---|---|
| 9,19,26,30,44,58 | 119.4pt | Lato-Black | `1`…`6` | level-1 chapters (⁼ the user's `1…6`) |
| 28,39,55 | 70.0pt | EuropaNr1SH-Bold | `”` | level-2 sections `"` |
| 9 | 37.0pt | Lato-Bold | `Introduction` | level 3 — demoted below its own chapter number |

Wrapped headings split per line: `Whole of journey` + `approach`,
`Integration of land use` + `and transport planning`, `Behavioural change
and` + `demand management`.

## Finding 3 — current HEAD still corrupts this document (and 9 others)

With current HEAD, `detect_structure` on the cached sidecars gives
`sustainable-mobility-policy` method `toc`, 77.3% match rate (above the 0.60
gate) — and a **tree with zero level-1 nodes**, i.e. every node is level 2.
The failure chain, all verifiable on `steps/extract_pages/pages/sustainable-
mobility-policy/004.json`:

1. `page_lines()` preserves raw span order instead of reading order, so the
   **footer page number `2` (y=791) is read before the header (y=21) and
   before every TOC line (y=173–700)**; the `Table of contents` title
   (y=120) arrives last.
2. `_parse_toc_page` sees bare `2` first: length ≤ 7 and alone on a line ⇒
   *separate-line number* ⇒ it swallows the following lines
   (`National Sustainable Mobility Policy | Table of Contents`, `Foreword`)
   until the next bare number, producing a bogus entry
   {number: `2`, title: `National Sustainable Mobility Policy | Table of
   Contents Foreword`, x0: 42.5}.
3. That bogus x0 (footer-side) plus the real entries' x0 (80.5) ⇒
   `_infer_levels` takes the *indent* signal with two buckets ⇒ the
   junk becomes the only level 1 and **all 21 real entries become level 2**.
4. The 0.60 gate passes (unrelated real matches), so the corrupt tree ships.

Downstream, `assemble_sections._chapter_node` turns parentless nodes into
their own chapters, so this tree would publish ~17 mis-titled chapters.

Wired-up-today `validate_split` would *not* catch this (no junk titles, no
boundary collisions, no coverage gaps) — the structural invariant "at least
one level-1 chapter with sane levels" is simply not checked anywhere.

## Similar cases — published artifacts (what users see now)

Junk bare tokens as chapter/section titles in committed `meta.json`:

| Document | Method | Junk titles |
|---|---|---|
| sustainable-mobility-policy | font | `1`–`6` (chapters + overview sections), `"` ×3 |
| …action-plan-2026-2030 | font | `”` ×4 (incl. a chapter `”` pages 7–42) |
| …year-two-progress-report | font | `”` ×6, plus `Policy` (cover fragment) |
| …year-three-progress-report | font | `”` ×4 |
| …action-plan-2022-2025 | font | `2040` (cover text), `Mobility Policy` |
| all-island-…rail-review | font | `21` (TOC page number); missing `Appendix C` (split into 2 chapters) |
| gda-cycle-network-plan-2022 | font | `l` (map glyph) |

Structural corruption beyond bare tokens in published meta.json:

| Document | Corruption |
|---|---|
| …action-plan-2022-2025 | chapters are split wrapped titles (`Safe and Green` / `Mobility` …) |
| cycleconnects-summary-report | `Network` ×2 split from `Interaction with … Network`; chapter order scrambled |
| nta-statement-of-strategy-2026-2030 | single chapter `Strategy` (split from `Statement of`) |
| emra-rses | 15 of 30 chapters are TOC lines with dot leaders; prose fragments (`1 in 8 people…`, `44 persons`, `65 + years`) |
| national-cycle-network-plan | chapters `1 way`, `73 blanket`, `70 [approximately 110kph]`, `Public Consultation.`; ranges spanning pages 900–1107 |
| connecting-ireland-rural-mobility-plan | duplicated `1 Introduction` ×2, truncated `2 NTA's Role…`, junk `15 min walk` |
| gda-transport-strategy-2022-2042 | junk chapters `Servicing`, `Assessment`; missing 15 & 18 |
| code-of-practice-recreational-craft | missing 1.1; `Emergency Procedures` spans pages 169–268 (100 pages) |
| ndp-sectoral-investment-plan | missing chapters; junk `3 and 5` |

## Similar cases — current HEAD (audit over cached sidecars)

Running `detect_structure` + manual `validate_split` + junk-title scan on all
24 documents, **10 remain problematic** after regeneration:

| Document | Method | Problem at HEAD |
|---|---|---|
| sustainable-mobility-policy | toc | **0 level-1 nodes** (Finding 3) |
| all-island-…rail-review | toc | all real chapters level 2; single level-1 node (document title) |
| sustainable-mobility-policy-action-plan-2022-2025 | font | junk `2040`, split titles `Safe and Green`/`Mobility` |
| tii-sustainability-implementation-plan-2026 | font | split titles (`Sustainability`/`Implementation Plan`), duplicate boundary |
| cycleconnects-summary-report | font | 6 bullet lines become titles (`• Major Cities…`) |
| code-of-practice-recreational-craft | numbering | dot-leader/fragment titles ×22 |
| code-of-practice-fishing-vessels-under-15m | numbering | survives, but clusters of clause titles |
| emra-rses | numbering | 304 issues (dot-leader TOC lines, fragments) |
| national-cycle-network-plan | numbering | dot-leader titles |
| gda-transport-strategy-2022-2042 | numbering | 11 duplicate boundaries |
| sustainable-mobility-policy-action-plan-2022-2025-final-progress-report | toc | `- Moving`, `- Road` … titles (pipe/fragment stripping) |
| national-investment-framework… | toc | titles with leading `\|` pipes; `Section 1: Overview` unmatched |
| ev-infrastructure-strategy | toc | control char `\x07` inside a title |

## Root causes

1. **Stale published artifacts** — pipeline not re-run since `342f926d`.
2. **`page_lines` trusts raw span order** (`process.py:127`) instead of
   reading order (y, then x) — header/footer/title lines interleave wrongly,
   which feeds every downstream parse.
3. **`from_font_hierarchy` has no heading-candidate guard** — bare numerals,
   glyphs, bullets, cover text at heading size all become nodes; wrapped
   headings split.
4. **`from_numbering` skips only size, not candidate/leader checks** — dot
   leaders, TOC lines with trailing numbers (emra), and prose with numeric
   prefixes become chapters.
5. **TOC parse is fragile at the edges**:
   - does not exclude running headers/footers *inside `_parse_toc_page`*
     (the `right_page_number` x-guard misses footer-page numbers at x<50%);
   - `_infer_levels` has no `Chapter N –`/`Section N:` prefix rule, so
     documents whose TOC entries share one x0 get flat or mis-bucketed levels
     (SMP: all-L2; all-island: all-L2);
   - `_strip_toc_suffix`/`_split_number` leave leading `|` pipes (nifti), a
     lone control char `\x07` (ev-infrastructure), and `- Moving` fragments
     (final-progress-report) as titles.
6. **`validate_split` is dead code in production** — defined and tested, but
   `process()` never calls it, and even it would not have caught SMP's
   all-level-2 tree. Nothing enforces "≥1 level-1 chapter, no
   non-heading titles".

## Proposed solution

Ship as one change on this worktree branch; each phase has its own tests.
Ordering matters: guardrails first so a bad tree can never silently publish.

**Phase 1 — guardrails (safety net).**
- Call `validate_split()` inside `process()` for every document; append its
  issues to `errors.json` as `InvalidStructure` per doc.
- Add the missing structural invariant: a detected tree must have ≥1
  level-1 node when ≥2 levels exist, and every title must pass
  `is_heading_candidate`. Violations ⇒ `InvalidStructure` (still published,
  never silently wrong — matching the repo's fail-closed rule).
- Where a `toc` tree would be all-level-2, that *is* a validation failure
  (add to the invariant list).

**Phase 2 — parser fixes for the demonstrated failures.**
- `page_lines`: deterministic reading order — sort by (page, y0, x0) with
  block/line as tiebreak; keep the largest-span sizing rule.
- `_parse_toc_page`: skip bare numbers at *any* x inside a flagged TOC page;
  skip running-header/footer lines (pass the already-computed
  `running_header_texts` set in, plus a y-band skip for header/footer);
  start entry collection at the `Table of contents` title line in reading
  order.
- `_infer_levels`: new deterministic rule — entry title matching
  `^(chapter|section|part)\s+\d+` forces level 1 (its following entries are
  level 2 until the next such marker); keep numbering/indent fallbacks.
- `_split_number` / `normalize_heading_text`: strip leading `|`/control
  chars/punctuation-only fragments; reject a title with no letters via the
  existing candidate guard everywhere an entry is accepted.
- `from_font_hierarchy` / `from_numbering`: apply `is_heading_candidate`
  + join up-to-2 consecutive same-style lines (like the TOC strategy's
  `_joined_runs`) so wrapped headings stop splitting.

**Phase 3 — fixtures + regeneration + review.**
- Add page-fixture tests: SMP page 4 (footer-pollution chain, asserting
  `Chapter 1 – Introduction` is level 1), the `”`-glyph page (assert no
  glyph-titled node), action-plan-2022-2025 cover, emra dot-leader page,
  national-roads duplicate-boundary case.
- Re-run document pipeline (stale since 10-13): full run, `--stop-on-error`,
  from a clean `--force`, review `detect_structure/errors.json`, re-audit all
  24 meta.json with the same script (`audit.py` in this directory; results
  are regenerable).
- Review the generated `public/` diff before merging to `main` (per AGENTS.md
  publishing rules); bundles re-publish from `public/**` on merge.
- Any document that still fails validation after Phases 1–2 gets a
  hand-curated `override.json` entry (existing escape hatch), not a heuristic.
