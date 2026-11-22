# Follow-ups after `improve-chapter-split-accuracy`

Written for a new session. Everything here is something the change found but did not fix. Evidence for each is in [`RESULTS.md`](RESULTS.md); the design and decisions are in `openspec/changes/improve-chapter-split-accuracy/` (or its archive).

Run the report from `pipelines/document_pipeline`:

```bash
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py            # gold scores + diff vs baseline
PYTHONPATH=".:../../src" python steps/detect_structure/eval/production_view.py  # all 40 documents, production path
```

State at hand-over: tuning 10 documents, 5 fully correct, exact F1 0.81; held out 4 documents, 1 fully correct, exact F1 0.62 (unchanged by the change).

## 1. Fix before relying on the regenerated bundles

### 1.1 `assemble_sections`: slug collision duplicates a section — FIXED (2026-11-22)
Fixed on branch `fix/assemble-sections-slug-collision`. `build()` now de-duplicates the `chapter/slug` composite key per boundary: the chapter keeps the reserved `overview` slug for its preamble, a colliding node is suffixed `-2`, `-3`… (the `dedupe_slugs` convention), and a `SectionSlugCollision` error is logged. Regression test: `tests/test_assemble_sections.py::test_a_node_slugged_overview_gets_a_suffixed_slug_rather_than_sharing_the_preamble_file`. The national-cycle bundle regenerated accordingly: preamble `overview` pp. 63–64, the real node `overview-2` pp. 198–500 (129,534 words once), `full.md` −143 KB, and a re-scan of all 40 bundles finds no duplicate section file anywhere.

### 1.2 `national-cycle-network-plan`: one chapter spans pages 63 to 1107
The printed contents lists 8 chapters and no appendices, so under "the TOC defines the chapters" the last chapter contains about 1,000 appendix pages (`Appendix B: Corridor option assessment tables`, ...). The gold agrees with the TOC. A human should decide whether to publish it that way, or add the appendices to the gold and the detector.

## 2. Documents still held (`hold:` in `documents.yml`)
Lifting a hold is a hand decision. None was lifted.
- `climate-action-plan-2023`: now 18 chapters instead of 2, but 17 of 25 gold chapters match exactly and 8 are missing (for example `Carbon Pricing`, `Electricity`). Coverage gaps on pages 2 and 283. `Ensuring a Just Transition…` is placed on p. 68 against gold p. 67.
- `climate-action-plan-2025-annex-of-actions`: structure now valid (exact F1 0.94), but coverage gaps on pages 94 and 95 and a `FigureOutOfBounds`.
- `climate-action-plan-2023-annex-of-actions`: still `InvalidStructure` (no level-1 node). It is a held-out document at exact F1 0.00. Its contents page uses spaced dot leaders (`. . . .`) that `DOT_LEADER_RE` (`\.{4,}|…`) does not see, and the annotation helper found no entries on it either, so the TOC path is probably never reached. Start there.

## 3. Detector work not done

- **Held-out set did not move.** Two held-out documents were already right. `national-ports-policy` (method `outline`, exact F1 0.50) has an outline that disagrees with its printed contents; this is the same family as GDA's `PART A/B`, a stated non-goal of the change. The change gives no evidence yet that its rules generalise. Treat the held-out set as the acceptance test for the next change, and do not tune on it.
- **Reconcile the outline with the printed TOC** (GDA `PART A/B`, ports). Larger design question; deliberately left out.
- **`emra-regional-spatial-and-economic-strategy`** (exact F1 0.48): artwork chapter titles match at the wrong page (`People and Place` and `Economy and Employment` both match p. 243, against p. 42 and p. 120). This needs an anchor-consistency check on matched chapters (matches out of TOC order), which is a different rule from D8. Left-edge roman folios (`ii`, `iii`) also still become junk TOC entries.
- **D8, guarded placement by printed page, is not merged.** It is preserved on branch `experiment/d8-guarded-placement` (commit `61ed78b7`). It improved no gold document, so it was reverted under the results-log protocol. It made 21 plausible placements in five documents that have no gold. To evaluate it, annotate one of them (`national-investment-framework-for-transport-in-ireland` is the best candidate: numbered `Section N:` chapters), then re-run the branch. If it scores, merge it.
- **GDA** (`gda-transport-strategy-2022-2042`, exact F1 0.14): outline pages are one page off from gold throughout; `Enviromental` + `Assessment` do not merge because their bookmark names the page before the heading (task 3.3 of the change is open for this reason).
- **TOC with the page number on the first line of a wrapped entry** is the opposite of the layout the wrapped-entry rule handles. `sustainable-mobility-policy-year-two-progress-report` has one wrong join. It is logged as `TocEntryUnmatched`.
- **`connecting-ireland-rural-mobility-plan`**: garbled subset-font text layer (`%HQH´WV…`). Stated non-goal; needs OCR or a font fix upstream.

## 4. The D4 section-loss trade-off (decide)
`SupplementHeadingRejected` removes numbered sections from six published trees (CAP 2023 213 to 158 nodes, emra 83 to 53, national-cycle, ev-infrastructure, CAP 2025 annex, fishing). Most of the rejected headings in the first four are real sections, rejected because the chapter that owns them was not matched in the right place. The repo rule (an explicit error beats a confidently wrong value) was applied. The alternative is to keep any heading whose number matches some TOC chapter and accept that some sit under the wrong chapter. Revisit once the chapter-matching problems above are fixed, since that recovers most of the sections.

## 5. Housekeeping
- **Open tasks in the change:** 3.3 (the `Enviromental` half of its verify clause) and 9.2 (one unrelated pre-existing failure in the root suite). Archive the change once those are accepted.
- **Root test failure:** `tests/test_dataset_discovery.py::test_every_latest_dataset_csv_is_linked_from_get_the_data` fails on any fresh checkout, including the commit before this work, because the gitignored combined FOI files are not built. Run `python scripts/build_foi_combined.py` first.
- **Stale override:** `road-safety-strategy-phase-2-action-plan-2025-2027` in `override.json` targets a document that is not in `documents.yml` or the 40-document snapshot. Remove it or add the document.
- **`eval/input.json`** is an LFS snapshot of `extract_pages` output. Rebuild with `eval/make_input.py` after any change to extraction, and re-baseline with `score.py --refresh-baseline` only after writing a `RESULTS.md` entry (the protocol is at the top of that file).
- **Annotation setup** (not committed): `steps/fetch_pdfs/pdfs` and `output.json` in a worktree are symlinks to the main checkout's copies; the gold review page is `eval/review_server.py` (LAN, port 8765).
