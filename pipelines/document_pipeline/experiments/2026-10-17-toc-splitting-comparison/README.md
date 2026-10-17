# TOC-name occurrence-scoring comparison — 2026-10-17

Determines whether a new `from_toc` detection strategy — parse the document's
Table of Contents into canonical heading entries, locate each entry's body
occurrence by exact text match, score occurrences by font rules, and build the
chapter/section tree from the best occurrence — can replace the legacy
`numbering`/`font` cascade on the documents where that cascade over-splits.
Read-only: it runs over cached `extract_pages` output and writes only
`results/results.json`.

## Hypothesis

The legacy cascade promotes non-headings (page numbers, currency figures,
bullets, glossary entries, running headers) via the `font` strategy, producing
over-split trees — the worst case is `gda-cycle-network-plan-2022` at 201
nodes. A TOC is a viable allow-list for most documents (21 of 24 have a
`Contents`/`Table of Contents` title line). Using TOC titles as canonical
headings and font rules only as a disambiguator should produce trees whose
node count tracks the plausible-heading TOC entry count instead of the
font-size noise.

Uncertain at the outset: which matching rule is needed (exact vs
number-tolerant), the match-rate gate value, how TOC pages are detected across
the corpus's entry shapes, how multi-TOC documents behave, and whether the
supplement rule reintroduces the over-split it is meant to remove.

## Method

`run.py` imports the real `detect_structure.process` helpers (`page_lines`,
`body_size`, `_split_number`, `slugify`, `from_numbering`,
`from_font_hierarchy`, `assign_hierarchy`, `assign_page_ranges`, …) so the
prototype's numbers transfer to production. Per document it:

1. **Detects TOC pages** — a page is a TOC page if it has a title line
   (`contents` / `table of contents`) at heading size (≥ body + 0.5), or ≥3
   dot-leader lines, or a title line plus ≥3 right-hand page-number lines.
   Only the **first contiguous block** of TOC pages is parsed; `list-of-*`
   pages and later part-TOCs are flagged but contribute no entries.
2. **Parses entries** — inline vs separate-line numbers, right-hand page
   numbers, ASCII vs Unicode (`…`) dot leaders, non-heading furniture
   (abbreviations / glossary / list-of-*).
3. **Matches** each distinct entry's normalized title against the body under
   two rules: (a) exact normalized equality, (b) exact with deterministic
   number-prefix stripping (`NUMBER_PREFIX_RE`) on the body side. Normalization
   strips control characters, collapses whitespace (incl. thin spaces), and
   trims trailing punctuation/dots/`…`.
4. **Scores** occurrences by relative size + bold bonus, excluding the TOC page
   and running-header lines; selects `max` with earliest-document tie-break.
5. **Builds** the tree (`from_toc`), supplements with numbered headings not in
   the TOC set, and runs `validate_split` + the legacy cascade side by side.

Run it (from `pipelines/document_pipeline/`):

```bash
PYTHONPATH=".:../../src" python experiments/2026-10-17-toc-splitting-comparison/run.py \
  --rule number-tolerant            # or: --rule exact
```

## Results

Two matching rules were run. Exact-normalized alone fails the 60% gate on
several documents because body headings carry number prefixes or control
characters. **Number-tolerant is required** (highlights: `national-investment-
framework` 12% → 81%; `ev-infrastructure-strategy` 40% → 76%; `final-progress-
report` 53% → 82%).

The table below is the number-tolerant rule with the refinements the run
motivated applied (control-character stripping, numbering-only supplement,
first-contiguous-TOC-block). "Nodes" is legacy → prototype (combined); "issues"
is `validate_split` count for each.

| Document | method | TOC | rate (plausible) | nodes legacy→toc | issues legacy→toc |
|---|---|---|---|---|---|
| gda-transport-strategy-2022-2042 | outline | — | — | 21→270 | 2→0 |
| sustainable-mobility-policy-action-plan-2026-2030 | font | ✓ | 63% | 9→13 | 2→0 |
| sustainable-mobility-policy-action-plan-2022-2025 | font | — | — | 9→0 | 1→0 |
| sustainable-mobility-policy-year-one-progress-report | outline | ✓ | 88% | 24→22 | 5→0 |
| sustainable-mobility-policy-year-two-progress-report | font | ✓ | 77% | 28→19 | 3→0 |
| sustainable-mobility-policy-year-three-progress-report | font | ✓ | 96% | 23→21 | 2→0 |
| sustainable-mobility-policy-action-plan-2022-2025-final-progress-report | numbering | ✓ | 82% | 10→16 | 5→5 |
| national-investment-framework-for-transport-in-ireland | numbering | ✓ | 81% | 61→53 | 3→0 |
| sustainable-mobility-policy | font | ✓ | 82% | 32→17 | 9→0 |
| ndp-sectoral-investment-plan-for-transport | numbering | — | — | 7→7 | 0→0 |
| moving-together-strategy | outline | ✓ | 97% | 115→34 | 60→0 |
| all-island-strategic-rail-review-final-report | font | ✓ | 67% | 80→12 | 46→0 |
| national-roads-2040-final-report | outline | ✓ | 88% | 52→60 | 13→0 |
| national-cycle-network-plan | numbering | ✓ | 51% | 59→75 | 4→4 |
| ev-infrastructure-strategy | numbering | ✓ | 76% | 49→62 | 0→0 |
| nta-statement-of-strategy-2026-2030 | font | ✓ | 100% | 25→32 | 6→0 |
| tii-sustainability-implementation-plan-2026 | outline | ✓ | 35% | 8→16 | 0→0 |
| connecting-ireland-rural-mobility-plan | numbering | ✓ | 25% | 8→8 | 0→0 |
| cycleconnects-summary-report | font | ✓ | 55% | 24→6 | 8→0 |
| gda-cycle-network-plan-2022 | font | ✓ | 75% | 201→21 | 3→0 |
| emra-regional-spatial-and-economic-strategy | numbering | ✓ | 54% | 196→173 | 112→84 |
| national-ports-policy | outline | ✓ | 100% | 45→39 | 18→0 |
| code-of-practice-fishing-vessels-under-15m | numbering | ✓ | 5% | 5→11 | 0→0 |
| code-of-practice-recreational-craft | outline | ✓ | 41% | 164→195 | 70→5 |

(TOC "—" means no TOC page was detected, so the strategy cannot fire. Outline
documents never reach the strategy — the prototype still computes them for the
side-by-side, but production keeps `outline`.)

### Entry shapes and TOC-page signals observed

- **Right-hand page-number columns** (no dot leaders) are the most common shape
  (`right_pg=True` on 18 of 21 TOC documents) — e.g. `nta-statement`,
  `sustainable-mobility-policy`, where the page number is a separate far-right
  line. The right-column signal is what detects `sustainable-mobility-policy`,
  whose `Table of Contents` title is a running header at body size.
- **Separate-line numbers** (`1.` on its own line, title on the next) appear in
  `cycleconnects-summary-report`, `gda-cycle-network-plan`, `nta-statement`,
  `sustainable-mobility-policy`, `national-cycle-network-plan`.
- **Unicode `…` dot leaders** appear in `gda-cycle-network-plan-2022` (mixed
  ASCII/Unicode), `national-cycle-network-plan`, `cycleconnects`,
  `code-of-practice-fishing-vessels`, `emra`. ASCII `......` is the rest.
- **Multi-TOC** is common among long documents: `national-roads` (3 TOCs),
  `national-cycle-network-plan` (8), `emra` (main + List of Tables + List of
  Figures), `code-of-practice-recreational-craft` (2). `code-of-practice-
  fishing-vessels` is a *single* TOC spanning 6 pages (167 clause entries).
  Parsing all of them over-splits (`national-cycle-network-plan` 59→158 nodes);
  the **first-contiguous-block** rule fixes this.

### Match-rate and level-signal findings

- Number-tolerant matching clears the 60% gate on 9 documents; the clear wins
  (node count down AND issues down) are `gda-cycle-network-plan-2022`
  (201→21), `all-island-rail` (80→12), `sustainable-mobility-policy` (32→17),
  year-two (28→19), year-three (23→21), `national-investment-framework`
  (61→53), `nta-statement` (25→32, issues 6→0).
- Near-misses fall back safely: `emra` 54%, `cycleconnects` 55%,
  `national-cycle-network-plan` 51%. `code-of-practice-fishing-vessels` (5%)
  is a clause-level TOC whose entries are not body headings — correctly falls
  back to its 5-node `numbering` tree.
- **Level signal**: `numbering` depth on 10 docs, indentation on 11, none on 1
  (`gda-cycle-network-plan-2022`, whose 21 town sections genuinely are all
  level 1 — a flat tree is *correct* there, not a failure).
- **Running headers** interfere on several docs (up to 41 on
  `connecting-ireland`); excluding lines on ≥25% of pages is necessary.
- **Repeated titles** occur on 12 documents (up to 7 on `fishing-vessels`), so
  per-distinct-entry occurrence resolution is required.
- `validate_split` issue counts fall to 0 for every document whose match rate
  clears the gate and whose node count is close to the plausible entry count —
  the exact signal the change was designed to produce.

## Conclusion

The TOC-name strategy is viable. With number-tolerant matching,
control-character/whitespace normalization, a numbering-only supplement, and a
first-contiguous-TOC-block parse, it turns the motivating worst case
(`gda-cycle-network-plan-2022`) from 201 font nodes to 21 nodes with zero
issues, and clears the 60% gate on the documents that benefit most. The
refined thresholds and detection rules are recorded in the change's
`design.md`; the strategy is gated so any document that does not clear the
gate falls back to the legacy cascade unchanged.

Results files are regenerable and are not committed (see the experiments
gitignore rule).
