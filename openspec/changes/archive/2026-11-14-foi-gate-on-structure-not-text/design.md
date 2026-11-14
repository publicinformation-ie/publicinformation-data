# Design

## Context

- `score_table` (`src/lib/table_structure.py`) produces one `split_word_rate` from two signals. `_count_split_words` adds run-together tokens inside cells (`_RUN_TOGETHER_RE`, minus `_BRAND_RE`) to "split pairs" (a cell ending in a letter next to a cell starting lowercase). The same rate feeds both the gate (`failed_checks`) and the composite score that `transform_disclosure_files` uses to choose among candidate extractors (pdfplumber, camelot_lattice, pymupdf, mistral_cache, camelot_stream).
- `repeated_header_share` counts rows whose trimmed, normalised cells equal the detected header. Those rows stay in `data`, so they also count toward the width, fragment and purity checks.
- `extract_disclosures_canonicalize._is_repeated_header_row` already drops repeated header rows before mapping.
- Files listed in `extract_disclosures_canonicalize/column_mappings.json` are exempt from the gate.
- The working-tree step outputs (`transform_disclosure_files` to `extract_disclosures_canonicalize_rows`) are the post-PR #26 "after" state. The only baseline is `/Volumes/ext/dev/publicinformation/foi-before-snapshot-2026-11-12/`.

## Goals / Non-Goals

**Goals:**
- Separate the in-cell text signal from the structural split signal, and gate only on the structural one.
- Remove repeated header rows before computing the structural checks.
- Measure the selection blast radius over all bodies before calling the change done.

**Non-Goals:**
- Repairing cell text: ligatures, glyph splits, missing spaces at line joins. That belongs in `normalize_disclosure_cells` (one concern per step), as a follow-up.
- Changing any threshold value.
- Rescuing files gated on width or fragments.
- Fixing column mis-mapping (bodies 1295, 1207, 1122) or fragment junk in files that pass.

## Decisions

### D1. Split `split_word_rate` into two recorded fields
`StructureScore` gains `run_together_rate` (in-cell tokens, text) and `cross_cell_split_rate` (structural). `split_word_rate` is kept as a deprecated alias equal to `cross_cell_split_rate`, so existing consumers and experiment scripts keep working, and the `failed_checks` name `split_word_rate` keeps its meaning of "structural split". *Alternative:* delete `split_word_rate` outright. Rejected because `bakeoff.py`/`report.py` and stored `table_structure` scores read it.

### D2. Stub rule for cross-cell pairs
A pair (left, right) counts when the left cell ends in a letter, the right cell starts lowercase, **and** either the left cell's final alphabetic run or the right cell's first lowercase run is 3 letters or fewer and not in a small common-word list (`a, an, the, of, to, for, and, or, in, on, re, by, at, is, it, as, be, no, mr, ms, dr, ltd, na, sec, all, any, its`). The offline simulation (`experiments/2026-11-14-pdf-extractor-bakeoff/gate_structure_not_text_sim.py`) applied D1, D2 and D4 together to every PDF that has no override. 54 of the 67 split-word files and all 17 repeated-header files passed (3,193 rows), and no currently passing PDF failed. *Alternatives:*
- A dictionary check that the joined string is a word. Rejected: it needs a word list and mishandles Irish-language text and names.
- Requiring the joined token to appear elsewhere in the table. Rejected: weak on small tables.

The stub rule is crude but conservative. It only stops counting pairs, so it cannot reject a file that passes today.

### D3. Composite keeps its form; only the cross-cell rule changes
Composite = width × purity × (1 − fragment) × (1 − min(1, 10 × (cross_cell_split_rate + run_together_rate))) × (1 − repeated_header_share).

This is today's formula. The only input that changes is the corrected cross-cell count (D2). Text quality still steers selection: given pymupdf `informaQon` against pdfplumber `information`, the cleaner candidate wins.

Selection changes only where the old pair rule over-counted, which keeps the blast radius to one evidenced change. The all-bodies run (task 4) lists every file whose `pdf_extractor` changed.

*Alternatives:*
- A separate, lighter weight for the text term. Rejected: it adds a second unmeasured parameter that moves selection for every PDF.
- A gate-only change that keeps the old pair rule in the composite. Rejected: it would leave a measurement shown to be wrong in the path that decides between candidates.

### D4. Remove repeated header rows in `_data_rows`
Rows equal to the normalised header are dropped alongside blank rows and year dividers. `repeated_header_share` is computed on the pre-removal row count and recorded, and `failed_checks` no longer includes it. This matches what canonicalize already does, so the gate scores the table that will actually be published. Removing rows shrinks the denominators of the width and fragment shares, and that could push a file across a threshold. The simulation tested both denominators, with and without the removed rows, and gave identical outcomes: no new failures. So the shares use the post-removal count. `Thresholds.max_repeated_header_share` is kept but unused by `failed_checks`, and documented as such, so stored threshold reports still parse.

### D5. Errors list structural checks only
`TableStructureUnreliable` context keeps the full `score` and the list of `failed_checks`, which by construction now contains only structural checks. No new error type is added. An accepted file with a high `run_together_rate` is not an error, and it is discoverable from the step output.

## Risks / Trade-offs

- [Selection shift moves a good file to a worse extractor] → The all-bodies run lists per-file extractor changes and per-body record deltas against the post-PR #26 snapshot. Any body that drops more than 5% is investigated before acceptance.
- [Un-gated files publish defective text (`informaQon`, `J ournalist`)] → These were published in the baseline release, so this restores, not introduces. Cell repair is the first text follow-up, and the recorded `run_together_rate` finds the files.
- [Repeated-header rows leak into records] → Acceptance check: zero records from the 17 un-gated files have a field value equal to a canonical header alias (checked with `canonicalize_headers`).
- [Gold-set precision falls further (currently 0.65 on a provisional 10-file set)] → Re-measure and report. The gold set is in-sample and small, so it is reported, not used as a pass bar.

## Migration Plan

1. Before any re-run, snapshot the current post-PR #26 outputs (`transform_disclosure_files` to `extract_disclosures_canonicalize_rows`, including `errors.json`) to `/Volumes/ext/dev/publicinformation/foi-after-pr26-snapshot-2026-11-14/`. This is the "before" for this change. The Nov-12 snapshot stays the release baseline.
2. Re-run with `--processes 8` directly, reset `errors.json` in range, and run the runner from `assess_table_structure` to `extract_disclosures_canonicalize_rows` (see `foi-all-bodies-run-gotchas`).
3. Rollback: revert the commit and re-run the same range. Step outputs are regenerated, not committed.
