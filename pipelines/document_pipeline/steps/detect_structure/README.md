# detect_structure

Turns each document's extracted pages into a chapter/section tree. Third step in `document_pipeline`. Reads only `extract_pages`'s JSON — it never opens a PDF, which is what lets every heuristic here be a pure function tested against hand-written page fixtures in milliseconds.

## What it does

For each document in `extract_pages/output.json`:

1. Loads that document's `pages/<doc_slug>/NNN.json` sidecars and groups their spans into lines (one line per `(block, line)` pair, in reading order). A line's size and font come from its largest span, so a line that opens with a small bullet or footnote marker is still classified by the type it is mostly set in.
2. Computes the document's **body style** from a character-weighted `(size, font)` histogram. Character weighting matters: a document has few heading lines but they can be long, and weighting by line count would let a run of short headings outvote the prose they label. Every threshold below is expressed relative to this body size.
3. Runs a **strategy cascade**, best evidence first. A strategy has to find at least two nodes to be believed — a single heading is as likely to be a cover title as a chapter:

   | Strategy | Fires when | `confidence` |
   |---|---|---|
   | `outline` | The PDF has a table of contents (`extract_pages`'s `outline`) | 1.0 |
   | `numbering` | Lines of the form `1 First Chapter` / `1.1 Introduction` (≤3 levels), set above body size **or** bold | 0.9 |
   | `font` | No numbering, but distinct styles larger than body+0.5pt exist; the largest three rank into levels 1–3 | 0.6 |
   | `flat` | Nothing above applied — one node per page (`page-001`, `page-002`, …) | 0.2 |

   Two guards keep prose out of the numbering strategy: a candidate is rejected if it is set at body size and not bold, or if its title is longer than 120 characters or reads as a sentence (ends in `.` and has more than four words). `2.4 million trips are made each day.` matches the heading pattern perfectly and is rejected only by the size guard.

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
| `detection_method` | `outline`, `numbering`, `font` or `flat` — never suffixed, so it stays a fixed enum for the web repo |
| `overridden` | `true` when at least one `override.json` entry was applied to this document |
| `page_count` | Number of pages in the document |
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
  | `UnknownOverrideSlug` | An `override.json` entry names a slug detection no longer produces — the heading was probably renamed, or the detection method changed |
  | `MalformedOverride` | An `override.json` entry is not an object, has no `slug`, or sets a field that is not a node field |

- `override.json` — the hand-correction escape hatch. Absent by default; committed when it holds corrections. Keyed by `doc_slug`, each value a list of partial node records matched by `slug`:

  ```json
  {"fixture-doc": [{"slug": "1-1-introduction", "title": "Introduction and context"}]}
  ```

  Any node field except `slug` may be set (`level`, `number`, `title`, `start_page`, `start_y`, `end_page`, `confidence`, `parent`, `order`). The slug is the node's identity and is never rewritten, so a retitle cannot break a published URL. Derived fields (`parent`, `order`, `end_page`) are recomputed after a merge and the override's explicit values are then re-applied on top, so a hand-set `parent` sticks while everything around it stays consistent. This is a *node-level* override and is unrelated to `IncrementalWriter`'s record-level `override_path`, which replaces whole output records.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-detect every document instead of skipping already-processed ones.
- `--verbose` — print each document's detection method and node count.
