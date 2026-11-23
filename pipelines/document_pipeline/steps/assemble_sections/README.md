# assemble_sections

The step cuts the cleaned blocks of each document into Markdown for each section. It places the extracted figures between them at their recorded positions, renders tables, and makes sure that no content vanished. It is the sixth step in `document_pipeline`. It reads only JSON and never opens a PDF. That is what lets every function above the step shim (the thin wrapper around the step) be pure and tested against hand-written fixtures in milliseconds.

The Markdown files and the `chapters` tree that this step writes are what `publish_bundles` packs. Their shape is fixed by `docs/superpowers/specs/2026-08-10-document-bundle-contract.md` §4, the producer and consumer contract with `publicinformation-web`. The web repo writes a strict content-collection schema against exactly the frontmatter keys below. To add, rename or drop one of those keys is a MAJOR contract change (contract §8), not a tweak.

## The ownership rule

Every text block and every figure belongs to the last section boundary at or before its `(page, y)`. The heading block of a boundary is excluded. It is the boundary, not content underneath it, and it lives in the frontmatter `title` of the section rather than being repeated as a body heading.

Because ownership is otherwise total and exclusive, the coverage test that follows is meaningful:

- A page that contributed to no section is content that went nowhere, which is what a structure-detection miss looks like from downstream.
- A page that two sections claim means that the boundary set or the reading order is wrong.

Content before the first boundary (a title page, a table of contents, which every real PDF has) has no boundary to own it. The step assembles it into a synthetic `front-matter` chapter and section (both slugged `front-matter`, `order: 0`) instead of surfacing it as a `coverage.gaps` entry. This is real content, attributed to its real pages, so it is a legitimate section under the slug rules of contract §5 rather than a paper-over (a cosmetic fix). It is also the only way that a real PDF, which always has a cover page, is ever publishable. A pre-boundary page can still end up in `gaps`. That means it had no extractable blocks or figures at all (a genuinely blank page), not that it precedes the first heading.

### Furniture pages: `override.json`

A gap page with zero raw blocks and zero figures has two very different possible causes, and this step cannot tell them apart. One cause is a structure-detection miss (real content that vanished). The other is a chapter-divider design page (a page number, a running header, a full-bleed background image that the pipeline already rejected as furniture upstream) that never had extractable content. Coverage cannot tell those apart automatically. For that reason the override needs a human decision and is not a heuristic.

`override.json` (`{doc_slug: [page, ...]}`, maintained by hand) names pages that a human marked as furniture-only for a given document. A page moves from `gaps` to `coverage.furniture_pages` only when it meets both conditions. It must be listed in the override, and it must still produce zero raw blocks and figures for this build. When it moves, it stops blocking `publishable`. If the override is stale and the page now has content, the step leaves the gap in place (fail-safe). It also writes a `StaleFurnitureOverride` error that names the page, so that a person can review the override again.

### Chapter-divider pages: `title_only_pages`

A different gap shape needs no override at all. A dedicated chapter-divider page has only one raw item. That item is the boundary heading of the chapter itself (`_is_own_heading`), with no preamble before it and no section content after it on that page. The step deliberately excludes that heading from the body content of the section, because the heading becomes the frontmatter `title` of the section. The page therefore has one raw block but zero content by the ownership rule, and without this handling it falls straight into `gaps` with nothing to explain why. `coverage()` recognizes this directly from ownership, with no list maintained by a human, and reports the page under `coverage.title_only_pages` instead. The condition is narrow on purpose: a page counts only when every raw item on it is an excluded own-heading. A page that also lost real content (a stray paragraph that is misattributed to the boundary, for example) still surfaces as a real `gaps` entry. The step reports this case separately from `furniture_pages`, because the two causes are different. One cause is a page that the override records as empty. The other cause is a structural divider.

## What it does

For each document in `clean_text/output.json`:

1. Flattens the blocks of every page and every figure with `kind: "figure"` into one list ordered by `(page, y)`. It holds back figures with `kind: "table"`: they are the demotion target (the replacement) for a complex table, not standalone illustrations, and the table block itself places them.
2. Assigns each item to its owning boundary. A level-1 node that owns content directly (a chapter preamble, before its first section heading) becomes the `overview` section of that chapter. Items before the first boundary have no owner and become the synthetic `front-matter` chapter and section with `order: 0`, which the step omits entirely when there is no such content.
3. Renders the items of each section, in order, into the Markdown subset of the contract. The subset is ATX `##`–`####` headings, paragraphs, `-` and `1.` lists, GFM pipe tables, and images that each have an italic caption line after them. No raw HTML, no blockquotes, no code fences, and no H1 that repeats the title of the section.
4. Sometimes the step cannot render a table honestly, because merged cells arrive here as ragged rows. It then demotes the table to the rasterized image with `kind: "table"` that `extract_figures` made of the same region. The step joins the two on `table_figure_id(page, index)` (`p004-t01`) and adds the caption.
5. Drops a paragraph that duplicates a caption already emitted under its image on the same page. `clean_text` has no knowledge of figures, so a caption line also reaches this step as ordinary prose. This is the first place where both facts are known, so the step removes the duplicate here.
6. Makes sure that every page is covered, sets `publishable`, and writes a `CoverageGap` or `CoverageOverlap` error that names every affected page.

The step supports incremental resumption (a later run continues from earlier work and does not redo it) via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`).

## Coverage is a gate, not an abort

A document that fails the coverage test still gets its Markdown and its output record, with `publishable: false`. Nothing here is process-fatal. `publish_bundles` is the step that withholds the document, and it lists the document under `failed` in `index.json`. The guarantee of the contract (§7) is that a document is never half published, not that a bad document stops the batch.

| Field | Meaning |
|---|---|
| `covered` | Every page that contributed content to a section |
| `gaps` | Pages `1..page_count` that contributed to no section, which is content that vanished |
| `overlaps` | Pages that two or more sections claim. The contract requires exactly one |
| `empty_sections` | Section headings that own no text or figures. Informational: an empty section does not block publication by itself |
| `furniture_pages` | Gap pages that a person listed in `override.json` and that have zero raw blocks and figures, so the build treats them as design-only. Informational: removed from `gaps`, does not block publication |
| `title_only_pages` | Gap pages whose only raw item is the excluded own-heading of a boundary (a chapter-divider page). Informational: removed from `gaps`, does not block publication |

`publishable` is `false` if and only if `gaps` or `overlaps` is non-empty.

## Input

It is a three-way fan-in (several upstream outputs that feed one step), plus provenance:

| Source | Resolved via | Used for |
|---|---|---|
| `clean_text/output.json` | `--input` (required) | The blocks to cut |
| `detect_structure/output.json` | sibling: `Path(--input).parents[1] / "detect_structure"` | Section boundaries, `detection_method`, `page_count` |
| `extract_figures/output.json` | sibling | Figures to interleave, and the rasterized copies of complex tables |
| `fetch_pdfs/output.json` | sibling | `doc_title`, `source_url`, `public_body_id`: three frontmatter keys of the contract that exist nowhere else upstream |

The shared runner passes exactly one `--input`, so the step resolves further upstreams by path, the way `export_status` does in `foi_pipeline`.

## Output

`output.json` has the shape `{ metadata, results: [...] }` and mirrors the `meta.json` shape of the contract. Each record has these fields:

| Field | Description |
|---|---|
| `doc_slug` | Natural key |
| `doc_title`, `source_url`, `public_body_id` | Provenance, carried from `fetch_pdfs` |
| `page_count`, `detection_method` | Carried from `detect_structure` |
| `sections_dir` | `sections/<doc_slug>`, relative to this step directory |
| `chapters` | `[{slug, title, order, source_pages, sections: [{slug, title, order, file, source_pages, word_count, assets, ocr_pages?}]}]` |
| `coverage` | `{page_count, covered, gaps, overlaps, empty_sections, furniture_pages, title_only_pages}` |
| `publishable` | `false` when `gaps` or `overlaps` is non-empty |

`file` paths are relative to this step directory (`sections/<doc_slug>/<chapter-slug>/<section-slug>.md`), so they carry a `<doc_slug>` segment that the `meta.json` of the contract does not have. A bundle is per document, so `publish_bundles` strips the segment when it writes `meta.json`.

`ocr_pages` is present on a section only when part of its text came from OCR (the pages that carry `source: "ocr"` blocks). `publish_bundles` carries it into `meta.json`.

`order` is `chapter_number * 100 + section_number`, computed by `detect_structure`. Chapters use `* 100 + 0`. It gives a stable integer sort across the whole document without parsing slugs.

### `sections/<doc_slug>/<chapter-slug>/<section-slug>.md`

YAML frontmatter with exactly these eleven keys, in this order, then the body:

```yaml
title: "10.1 Introduction"
doc: gda-transport-strategy-2022-2042
doc_title: "Greater Dublin Area Transport Strategy 2022–2042"
chapter: 10-walking-accessibility-and-public-realm
chapter_title: "10 Walking, Accessibility and Public Realm"
section: 10-1-introduction
order: 1001
source_pages: [94, 96]
source_url: "https://…/gda-strategy.pdf"
public_body_id: 1486
assets: ["p094-f01.webp"]
```

`frontmatter()` raises on a missing or surplus key instead of shipping a payload that the schema of the web repo will reject without a message.

Image references in the body are bundle-relative `assets/<figure-id>.webp`, with no leading slash and no `..`. The consumer rewrites them to whatever public path it chooses. The `assets` frontmatter list (bare filenames) is the authoritative index of what a section references, so the rewrite never has to parse Markdown to find images.

`source_pages` is `[first, last]`, inclusive, over the pages where a section actually owns content.

The step deletes and rewrites the `sections/<doc_slug>/` directory of a document on every run of that document, so a renamed or removed section never leaves a stale `.md` behind.

## Notable files

- `errors.json` is truncated to `[]` at the start of every run. Nothing here is process-fatal.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `CoverageGap` | document, blocking | A page contributed no content to a section. Sets `publishable: false` |
  | `CoverageOverlap` | document, blocking | Two or more sections claim a page. Sets `publishable: false` |
  | `EmptySection` | section, informational | A section heading owns no text or figures. Does not block publication |
  | `TableDemoted` | table, informational | The cells are merged or ragged, so the step renders the rasterized image and the caption instead of a pipe table |
  | `TableDemotionFailed` | table | The table is too complex for a pipe table and no rasterized copy exists, so the step omits the table from the section |
  | `AssembleSectionsFailed` | document | Upstream records are missing or stale, or a document has a shape that the assembly does not expect. The step skips the document and the rest of the batch still runs |

  A document skipped by `AssembleSectionsFailed` is not marked processed, so a later run retries it without `--force`.

- `sections/` holds generated output that git ignores.

## Thresholds

| Constant | Default | Meaning |
|---|---|---|
| `MAX_TABLE_COLUMNS` | 12 | A table wider than this is a layout grid, not a table, so the step demotes it |
| `MIN_HEADING_LEVEL` / `MAX_HEADING_LEVEL` | 2 / 4 | Body headings are clamped to the contract's `##`–`####` |

## Flags

- `--doc SLUG`: scope processing to one document.
- `--force`: re-assemble every document instead of skipping already-processed ones.
- `--verbose`: print the section count of each document and whether it is publishable.
