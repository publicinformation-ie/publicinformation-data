# detect_structure

Turns each document's extracted pages into a chapter/section tree. Third step in `document_pipeline`. Reads only `extract_pages`'s JSON — it never opens a PDF, which is what lets every heuristic here be a pure function tested against hand-written page fixtures in milliseconds.

## What it does

For each document in `extract_pages/output.json`:

1. Loads that document's `pages/<doc_slug>/NNN.json` sidecars and groups their spans into lines (one line per `(block, line)` pair, in reading order). A line's size and font come from its largest span, so a line that opens with a small bullet or footnote marker is still classified by the type it is mostly set in.
2. Computes the document's **body style** from a character-weighted `(size, font)` histogram. Character weighting matters: a document has few heading lines but they can be long, and weighting by line count would let a run of short headings outvote the prose they label. Every threshold below is expressed relative to this body size.
3. Runs a **strategy cascade**, best evidence first. A strategy has to find at least two nodes to be believed — a single heading is as likely to be a cover title as a chapter:

   | Strategy | Fires when | `confidence` |
   |---|---|---|
   | `outline` | The PDF has a **plausible** outline (`extract_pages`'s `outline`): after unusable bookmarks are filtered out, at least two entries at its shallowest level | 1.0 |
   | `toc` | No outline, but a parseable Table of Contents page whose entries match body headings at or above the match-rate gate | 0.95 |
   | `numbering` | Lines of the form `1 First Chapter` / `1.1 Introduction` (≤3 levels), set above body size **or** bold | 0.9 |
   | `font` | No numbering, but distinct styles larger than body+0.5pt exist; the largest three rank into levels 1–3 | 0.6 |
   | `flat` | Nothing above applied — one node per page (`page-001`, `page-002`, …) | 0.2 |

   Two guards keep prose out of the numbering strategy: a candidate is rejected if it is set at body size and not bold, or if its title is longer than 120 characters or reads as a sentence (ends in `.` and has more than four words). `2.4 million trips are made each day.` matches the heading pattern perfectly and is rejected only by the size guard.

   An outline with one entry at its shallowest level (a lone `Untitled`, a document-title wrapper, or one root over its own children) says nothing about where chapters start, so it is not used: the cascade continues as if there were no outline, `detection_method` names the strategy that actually produced the tree, and an informational `OutlineNotUsed` error records why.

   **Outline preparation** happens before the cascade, in `detect_document_structure` (the one entry point shared by `process()` and the accuracy eval, so both score the same tree): non-heading bookmarks are dropped, wrapped bookmarks are merged, and each entry is moved to the page where its heading is printed. Titles have whitespace collapsed (line breaks, thin spaces, control characters) before the heading number is split off, so `3 Long Term Strategic Issues⏎for National Roads` is number `3`. Two adjacent same-level, same-page entries are merged only when the second has no number, the first does not end in `.`, `!` or `?`, and the joined title is the exact text of a heading line on that page (`15. Freight, Delivery and` + `Servicing`); two real headings that share a page, such as `2.7` and `2.8`, stay apart because their join matches no line. An unverified pair is left as it is.

   The **TOC-name strategy** (`toc`) parses the document's own Table of Contents into canonical heading entries, locates each entry's body occurrence by exact normalized text match (with deterministic number-prefix stripping — never fuzzy similarity) across one to three joined body lines, scores occurrences by font rules (relative size, boldness, isolation), and builds a node per distinct entry. It activates only when the share of plausible body-heading entries matched above the score floor meets `MATCH_RATE_GATE` (0.60); furniture entries (abbreviations, glossary, list-of-figures) are excluded from that denominator. A **pipe-separated code** (two to five uppercase letters or digits, then `|`: `RE | Research and Innovation`) is the heading's number whatever whitespace surrounds the pipe, in the outline, the TOC and the body alike, so the TOC's `RE |Title` meets the body's `RE | Title`; the slug keeps the code (`re-research-and-innovation`). `Walking | Cycling` and `Chapter 1 | Purpose` are not codes. **Unpaged entries** are excluded from the gate as well: once a column of the contents list prints page numbers (three or more entries in a 10-point left-edge column, half or more with a page), an entry with no page number (side-panel prose, appendices published separately) is `unpaged`. It is still matched like any other and still logged `TocEntryUnmatched` when it is not, but it counts in neither the numerator nor the denominator. A contents list that prints no page numbers has no unpaged entries. Matched boundaries are supplemented with numbered headings not in the TOC, **as sections only**: the TOC defines the chapters, so a supplemented heading is kept only at level 2 or deeper, in the page span of a TOC chapter (the span after a matched chapter also belongs to the unmatched TOC chapters listed after it, up to the next matched one), and only when its leading number equals that chapter's number (printed in the TOC, or shared by its numbered child entries). Anything else (`30 [approximately 50kph]`, `65 + years 12%`, `0.3 Mt CO2eq.`) is dropped and logged `SupplementHeadingRejected`, and a below-gate match rate falls back to the legacy cascade, logging `LowTocMatchRate`. Only the first contiguous block of TOC pages is parsed (`list-of-*` pages and later part-TOCs are flagged, not parsed), so a multi-part document does not over-split. The block is extended by a **continuation page** that directly follows its last page, has no title or only repeats the contents title, shows at least three entries' page numbers (right-column numbers, or lines of spaced dot leaders ending in a number), does not open with a `List of …` title, and, when it shares a running header with the TOC page, that header names the contents (`… | Table of Contents`); a page after a gap is still a part-TOC and is not parsed.

   TOC parsing records each entry's **printed page** (`printed_page`: an int for arabic, the printed string for roman, none otherwise; matched to its row by position, since right-column numbers are read after the left column) and **joins a wrapped title** onto the entry before it. A line joins only in a TOC that prints page numbers (at least half its entries have one), when the entry before it has no page yet, the line sits directly below it in the same type size and is not indented less, and it has no heading number and does not open with its own label (`Goal 7:`). The page number of the joined entry is the one on its last line. A `Chapter N` label (`Chapter 1 – Introduction`, or `CHAPTER 2:` alone on the line above its title) is read as the heading number `N`; a body heading printed with the same label meets the entry by title alone. With at least two labels the level signal is `label` (after `numbering`, before `indent`): unnumbered non-furniture entries between labels are sections, a repeated chapter number is a section of that chapter, and furniture and division labels (`Appendix A`, `Annex 2`, `Part B`) stay level 1. Thresholds were pinned by the read-only experiment in `experiments/2026-10-17-toc-splitting-comparison/`.

4. Assigns `parent` (nearest preceding node of a lower level), `order` (from the heading number where there is one — `1.1` → 101 — otherwise from position), and `end_page`.
5. Applies `override.json`, if present, and records whether it did.

`detection_method` is recorded per document, so a weakly-detected tree is visible in the data — and badgeable in the web repo — rather than an invisible assumption baked into the published site.

**`end_page` is the page before the next *same-or-higher-level* node starts**, clamped to be at least `start_page`; the last such node ends on the document's last page. Same-or-higher-level rather than next-node-at-any-level is what stops a chapter ending where its own first section begins: in the test fixture, chapter `1-first-chapter` runs pages 2–3 while its section `1-1-introduction` also runs 2–3, and chapter 2 starting on page 4 is what closes both.

A document that falls all the way through to `flat` is **not** a failure — it is written to `output.json` with `detection_method: "flat"` and publishes normally. It does get an informational `LowConfidenceStructure` entry in `errors.json` so it surfaces in triage next to the real failures.

Supports **incremental resumption** via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`); scoping is also available by calling `process(..., doc_slug=...)` directly.

## Input

`extract_pages/output.json`, via `--input` (required). Page sidecars are resolved relative to that file's parent directory using each record's `pages[].file`.

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `extract_pages` |
| `detection_method` | `outline`, `toc`, `numbering`, `font` or `flat` — never suffixed, so it stays a fixed enum for the web repo |
| `overridden` | `true` when at least one `override.json` entry was applied to this document |
| `page_count` | Number of pages in the document |
| `toc_entry_count`, `toc_matched_count`, `toc_match_rate` | Present when a TOC was detected: the plausible-heading entry count, how many were matched above the score floor, and their ratio |
| `nodes` | The tree, in document order — see below |

Each node:

| Field | Description |
|---|---|
| `level` | 1 for a chapter, 2+ for a section |
| `number` | Heading number as printed (`"1.1"`), or `null` |
| `title` | Heading text with its number stripped |
| `slug` | URL segment; retains the heading number with `.` → `-` (`1.1 Introduction` → `1-1-introduction`). Always matches `documents.SLUG_RE` |
| `start_page`, `start_y` | Where the heading appears (1-indexed page, top-down y) |
| `end_page` | Page before the next same-or-higher-level node; last node gets the document's last page |
| `confidence` | Per the strategy table above |
| `parent` | Slug of the enclosing node, or `null` |
| `order` | Sort key: `1.1` → 101; unnumbered trees fall back to chapter/section position |

Repeated headings — `1.1 Introduction` continued onto the next page, or the same title used twice — get a `-2`, `-3` … suffix, because the slug is a published URL segment and collisions cannot be allowed to silently overwrite one another.

## Notable files

- `errors.json` — truncated to `[]` at the start of every run.

  | `error_type` | Cause |
  |---|---|
  | `LowConfidenceStructure` | The flat fallback fired. Informational: the document still publishes |
  | `LowTocMatchRate` | A TOC was detected but its match rate was below the gate, so the legacy cascade was used |
  | `TocEntryUnmatched` | A TOC entry had no body occurrence under the matching rule; no boundary created |
  | `TocEntryNoHeading` | A TOC entry matched a body line below the score floor (not above body size or bold); no boundary created |
  | `SupplementHeadingRejected` | A numbered body heading not listed in the TOC was not added as a section: it would be a chapter, it does not carry the number of the TOC chapter whose span it lies in, or that chapter has no number to match. Informational; the context gives the heading, page and reason |
  | `OutlineNotUsed` | The PDF outline had fewer than two entries at its shallowest level, so it was not used as chapter evidence and detection continued with the TOC, numbering, font or flat strategy. Informational |
  | `OutlineEntryDropped` | An outline bookmark had no usable title (empty, no letters such as `1.`, or a Word `_Hlk`/`_Toc` auto-bookmark) and was dropped from the tree |
  | `OutlineEntryUnresolved` | An outline bookmark names only a page and its exact title was not found, so its `y` stays at the page top (the validation gate will usually flag the resulting duplicate boundary). Resolution joins up to 4 wrapped lines (running headers of another size are skipped) and, only after an exact miss on the stated page, tries the previous page for a heading-sized line (InDesign `/Fit` bookmarks can point one page late); it never guesses or tries the next page |
  | `InvalidStructure` | The final tree (after overrides) failed `validate_split` (e.g. no level-1 node, orphaned or empty sections). The tree is not altered and the record is still written. Validation always runs in production; an unresolved entry blocks the merge — fix it with an `override.json` entry |
  | `UnknownOverrideSlug` | An `override.json` entry names a slug detection no longer produces — the heading was probably renamed, or the detection method changed |
  | `MalformedOverride` | An `override.json` entry is not an object, has no `slug`, or sets a field that is not a node field |

- `override.json` — the hand-correction escape hatch. Absent by default; committed when it holds corrections. Keyed by `doc_slug`, each value a list of partial node records matched by `slug`:

  ```json
  {"fixture-doc": [{"slug": "1-1-introduction", "title": "Introduction and context"}]}
  ```

  Any node field except `slug` may be set (`level`, `number`, `title`, `start_page`, `start_y`, `end_page`, `confidence`, `parent`, `order`). The slug is the node's identity and is never rewritten, so a retitle cannot break a published URL. Derived fields (`parent`, `order`, `end_page`) are recomputed after a merge and the override's explicit values are then re-applied on top, so a hand-set `parent` sticks while everything around it stays consistent. An entry of exactly `{"slug": "…", "drop": true}` removes that node instead, and the previous boundary absorbs its text. Use it where detection is right but the one-dimensional `(page, y)` boundary model cannot represent the layout: two section headings side by side on one baseline (two columns) are a duplicate boundary, so the second is dropped and the survivor is retitled to name both. `drop` combined with any other field, or with a value other than `true`, is a `MalformedOverride`. This is a *node-level* override and is unrelated to `IncrementalWriter`'s record-level `override_path`, which replaces whole output records.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-detect every document instead of skipping already-processed ones.
- `--verbose` — print each document's detection method and node count.

## Accuracy evaluation (gold chapters)

`validate_split` checks the tree's *shape* and `eval/compare.py` checks whether the output *changed*.
Neither answers "is this the right chapter split?". The accuracy report does: it scores each
document's detected chapters against a hand-authored gold list transcribed from the document's
printed table of contents, so a detector change can be shown to help or hurt.

```bash
cd pipelines/document_pipeline

# Score every reviewed gold document against the committed detection snapshot,
# diffing each metric against the committed baseline when one exists.
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py

# Score the current local extract_pages output instead of the snapshot.
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py --live

# Machine-readable result for a before/after comparison.
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py --json /tmp/structure-score.json

# After an intentional detector change, rewrite eval/baseline.json.
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py --refresh-baseline

# Gold repeatability: score one gold file against another (same metrics).
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py \
    --compare-gold eval/gold/national-cycle-network-plan.json /tmp/reannotated.json
```

What it reports per document: boundary precision, recall and F1 (exact page, and within ±1 page),
page attribution accuracy, title accuracy over exact-matched pairs, and whether the document is
fully correct — each both on the raw detector tree and after `override.json` is applied, because an
override must not be able to hide a regression. The corpus summary gives macro (per-document mean)
and micro (pooled counts) averages plus the count of fully correct documents. Excluded documents are
listed with their reason: malformed gold, not yet reviewed, in the `no_toc.json` register, a gold/PDF
sha256 mismatch, or a detection error.

Flags: `--live` (score local `extract_pages` output instead of the snapshot), `--json PATH` (also
write the machine-readable result), `--gold DIR` (a different gold directory), `--baseline PATH` and
`--refresh-baseline` (diff against, or rewrite, the baseline — the diff is printed automatically when
the file exists), `--compare-gold A B` (see above), and `--check-gold` (validate every gold file and
print its consistency warnings, drafts included — use this while annotating).

The report is read-only and offline: a plain run writes nothing, `--json` writes only the path you
name, and `--refresh-baseline` is the only write in the step's own directory. It makes no network or
paid calls. It is not a CI gate — run it by hand before and after a detector change.

A gold file may set `"held_out": true`. Held-out documents are scored and baselined like any other,
but the report prints separate `[tuning]`, `[held out]` and `[all]` summaries, and the held-out
documents are read only at acceptance — never used to design or tune a rule. Each measured
detector change is recorded in [`eval/RESULTS.md`](eval/RESULTS.md) before the baseline is refreshed.

`eval/score.py` (report and metrics), `eval/gold.py` (gold loading, validation and consistency
warnings) and `eval/annotate.py` (the annotation helper) sit beside `eval/compare.py`; the snapshot
fingerprint shared by `eval/make_input.py` and the report is in `eval/snapshot.py`.

### Adding a gold document

The rules are in [`eval/gold/GUIDELINE.md`](eval/gold/GUIDELINE.md) — read them first; they define
what counts as a chapter, how titles and pages are recorded, and what belongs in `notes`. In short:

1. Run the helper to render the contents pages and candidate chapter start pages to a gitignored
   scratch directory and write a draft with `reviewed: false`:

   ```bash
   PYTHONPATH=".:../../src" python steps/detect_structure/eval/annotate.py <doc_slug>
   ```

   The draft is transcribed from the contents pages' text layer only — never from detector output,
   so the gold cannot inherit the thing it measures.
2. Open the images in `.scratch/detect-structure-gold/<doc_slug>/`, correct every entry (titles,
   `pdf_page` read off the rendered start page, `printed_page`), and set `reviewed: true`. Record
   every judgement call in `notes`.
3. Move the finished file to `eval/gold/<doc_slug>.json` and run
   `PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py --check-gold`: a consistency
   warning must be fixed, or explained in `notes`. The report only scores files with
   `reviewed: true`, so a draft stays excluded until the check is done.

A document with no printed contents listing gets no gold file. Add it to `eval/gold/no_toc.json`
with a one-line reason instead, so the report shows it as unscorable rather than silently skipping it.

### Reviewing the gold files in a browser

`eval/review_server.py` serves a small LAN page for the review itself: each document's contents
pages and chapter start pages, an editable chapter list, live consistency warnings, and **Save draft**
/ **Approve** buttons that write straight back to `eval/gold/<doc_slug>.json`.

```bash
cd pipelines/document_pipeline
PYTHONPATH=".:../../src" python steps/detect_structure/eval/review_server.py
# → http://<your LAN address>:8765  (the address is printed on startup)
```

It has no authentication: bind it to your own network, not the public internet. It writes only inside
the gold directory and the gitignored `.scratch/structure-review/` cache (rendered pages and an
`audit.log` of saves). Use `--port`, `--gold DIR` or `--refresh-images` as needed. If another machine
cannot reach it, allow incoming connections for Python in the host firewall.

Gold files are ordinary git (they are small), not LFS. `eval/input.json` is LFS-backed; regenerate it
with `make_input.py` only when the corpus or `extract_pages` changes — the report warns when live
output has drifted from it.

