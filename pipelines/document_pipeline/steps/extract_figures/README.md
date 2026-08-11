# extract_figures

Decides which regions of each page are figures, renders them to WebP, and gives each one a caption. Fourth step in `document_pipeline`. It reopens the source PDF, but only as a **rasteriser** — it asks a page to draw a rectangle and never to explain its content. All interpretation of the page happened in `extract_pages`.

Rendering the clipped *page* rather than extracting the embedded image is deliberate: a map is vectors, raster tiles and text labels layered together, and only the rendered page has all three.

## What it does

For each document in `extract_pages/output.json`, page by page:

1. Collects **candidate boxes** — every `drawings[].bbox` and `images[].bbox` on the page.
2. Discards **page furniture**: a box covering ≥ `FULL_PAGE_FRACTION` of the page (a background panel), a box thinner than `RULE_THICKNESS` in either dimension (a rule or a hairline border), and any box already contained in a detected table's bbox. Tables get their own record below; counting them twice would put the same region in the document as both a figure and a table.
3. **Clusters** the survivors: boxes that overlap or sit within `CLUSTER_GAP` of each other are unioned, and the pass repeats **to a fixpoint**. Merging changes the geometry, which can bring a third box into range — a chart's axes, plot area and legend arrive as dozens of separate drawings and have to come back out as one figure.
4. Drops clusters smaller than `MIN_AREA_FRACTION` of the page or thinner than `MIN_DIMENSION` in either dimension — icons, bullets, logos and stray marks.
5. Rejects clusters that are **prose**: at least `PROSE_MIN_LINES` lines fall inside the region and at least `PROSE_RATIO` of their characters are set at the document's body size. The discriminator is type size relative to the body style, *not* the presence of text — map labels, axis ticks and legend keys are text inside figures, and rejecting a region for containing words would delete every map and every chart in the document.
6. Rasterises each surviving cluster, plus **each detected table region**, to `assets/<doc_slug>/<figure-id>.webp` at `DPI`. The table copies are kept so `assemble_sections` can demote a table it cannot render as Markdown to an image.
7. **Matches a caption**: the nearest `Figure 1.1 …` / `Fig. 4.2: …` / `Table 2.1 …` / `Map 3 …` line within `CAPTION_BAND` below the region, else above it, and only where it overlaps the region horizontally (so a caption in the neighbouring column is not stolen by a figure in this one). The number in the pattern is required — it is what separates a caption from a sentence that starts with the word "Figures".
8. Writes one **contact sheet** per document.

Supports **incremental resumption** via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`); scoping is also available by calling `process(..., doc_slug=...)` directly. Re-running a document clears its `assets/<doc_slug>/` first, so a tightened threshold that stops producing `p003-f02` does not leave last run's WebP on disk for `publish_bundles` to ship.

## Thresholds

Every threshold is a module-level constant at the top of `process.py`, because they are empirical and are the thing most likely to need tuning against a real document. Tune them against a contact sheet, not against intuition — the sheet prints the values it was generated with in its header.

| Constant | Default | Meaning |
|---|---|---|
| `CLUSTER_GAP` | 8.0 pt | Boxes closer than this belong to one figure |
| `MIN_AREA_FRACTION` | 0.04 | Of page area; below this it is an icon or a bullet |
| `MIN_DIMENSION` | 40.0 pt | A figure is not 12 pt tall |
| `RULE_THICKNESS` | 3.0 pt | Thinner than this is a rule, not a graphic |
| `FULL_PAGE_FRACTION` | 0.9 | Of page area; above this it is a background panel |
| `PROSE_RATIO` | 0.6 | Share of characters at body size that makes a region text |
| `PROSE_MIN_LINES` | 4 | Fewer lines than this is a label, not a paragraph |
| `CAPTION_BAND` | 90.0 pt | Distance above or below the region to search for a caption |
| `DPI` / `WEBP_QUALITY` | 144 / 85 | Render resolution (2× nominal, for retina) and WebP quality |

## Input

`extract_pages/output.json`, always resolved by a fixed sibling path (`steps/extract_pages/output.json`), **not** from `--input`. The shared runner only ever chains `--input` to the *immediately preceding* step in `pipeline.json`, and `detect_structure` sits between `extract_pages` and `extract_figures` there (it too consumes `extract_pages` directly) — so trusting `--input`'s literal target would silently read `detect_structure`'s structure-node records instead, which carry no page geometry, producing a cascading zero-figure result with no error. `--input` is still a required flag (the shared runner's CLI contract, and its path still drives the runner's staleness check), it just is not read here. One consequence: an unrelated change to `detect_structure/output.json` still triggers a rerun of this step (a false positive), while a change to the real dependency, `extract_pages/output.json`, doesn't drive staleness at all — this is a known, accepted quirk of the fan-in, not a bug to "fix" back to reading `--input` directly. Page sidecars are resolved relative to `extract_pages/`'s own directory, using each record's `pages[].file`.

This step is also a **fan-in** on a second upstream: the source PDFs come from the sibling `fetch_pdfs` step, resolved the same way as `steps/fetch_pdfs/output.json` (`extract_pages` deliberately records no PDF path, because nothing downstream of it is supposed to need one) — the same technique `foi_pipeline`'s `export_status` uses. Called as a function, `process()` takes an explicit `pdf_paths` mapping instead.

## Output

`output.json` — `{ metadata, results: [...] }`. One record per document:

| Field | Description |
|---|---|
| `doc_slug` | Natural key, carried through from `extract_pages` |
| `figures` | Every rendered region of the document, pages in order and top-to-bottom within a page |

Each figure:

| Field | Description |
|---|---|
| `id` | `p{page:03d}-{f\|t}{index:02d}` — `p003-f01`, `p004-t01`. Matches the contract's `^p\d{3,4}-[ft]\d{2}$` |
| `kind` | `figure` for a clustered graphic, `table` for the rasterised copy of a detected table region |
| `page` | 1-indexed page the region is on |
| `bbox` | `[x0, y0, x1, y1]` in PDF points, y increasing downward, rounded to 2 places |
| `y` | `bbox[1]`, lifted out so `assemble_sections` can interleave figures into the text by reading position without re-deriving it |
| `asset` | `assets/<doc_slug>/<id>.webp`, relative to this step's directory |
| `caption` | Matched caption, or `Figure from page N` |
| `alt` | Alt text; defaults to the caption |
| `width`, `height` | Rendered pixel dimensions |

## Notable files

- `assets/<doc_slug>/<figure-id>.webp` — the rendered regions. Namespaced per document so `publish_bundles` can copy one directory per bundle. Generated, gitignored, and cleared per document on every re-run.

- `contact-sheets/<doc_slug>.html` — every rendered region of one document with its id, kind, page, bbox and pixel size, and the threshold values the run used. This is the tuning affordance: threshold tuning is a visual task, and a number whose effect you can see is worth more than a number you can justify. Generated and gitignored; open it after any change to the constants above.

- `errors.json` — truncated to `[]` at the start of every run. Nothing here is process-fatal: failures are isolated per figure and per document, so one bad region cannot cost a document its other figures and one bad document cannot abort the batch.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `MissingCaption` | figure | No caption line near the region. The figure is still emitted, titled `Figure from page N` — a missing caption is a presentation problem, not a reason to drop a figure out of the document |
  | `FigureRenderFailed` | figure | The region would not rasterise. That one region is skipped; the document's other figures are unaffected |
  | `SourcePdfMissing` | document | No `fetch_pdfs` record (or no downloaded file) for this document. Run `fetch_pdfs` first |
  | `DocumentFigureExtractionFailed` | document | The PDF would not open, a page sidecar is missing, or `extract_pages` recorded a page the PDF does not have (cross-step staleness). The document is skipped and the rest of the batch still runs — the same isolation `extract_pages` applies with `PageExtractionFailed` |

  A document skipped by either document-level error is **not** marked processed, so a later run retries it without `--force`.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-extract every document instead of skipping already-processed ones.
- `--verbose` — print each document's rendered region count.
