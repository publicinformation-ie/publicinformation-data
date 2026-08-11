# assemble_sections

Cuts each document's cleaned blocks into per-section Markdown, interleaves the extracted figures at their recorded positions, renders tables, and asserts that no content vanished on the way. Sixth step in `document_pipeline`. Reads only JSON — it never opens a PDF — which is what lets every function above the step shim be pure and tested against hand-written fixtures in milliseconds.

The Markdown files and the `chapters` tree this step writes are what `publish_bundles` packs, and their shape is fixed by **`docs/superpowers/specs/2026-08-10-document-bundle-contract.md` §4**, the producer/consumer contract with `publicinformation-web`. The web repo writes a strict content-collection schema against exactly the frontmatter keys below: adding, renaming or dropping one is a MAJOR contract change (contract §8), not a tweak.

## The ownership rule

Every text block and every figure belongs to the **last section boundary at or before its `(page, y)`**. A boundary's own heading block is excluded — it *is* the boundary, not content underneath it, and it lives in the section's frontmatter `title` rather than being repeated as a body heading.

Because ownership is otherwise total and exclusive, the coverage check that follows is meaningful:

- a page that contributed to **no** section is content that went nowhere — what a structure-detection miss looks like from downstream;
- a page claimed by **two** sections means the boundary set or the reading order is wrong.

Content sitting **before the first boundary** (a title page, a table of contents) is owned by nothing. It is deliberately **not** absorbed into a synthetic `front-matter` section: the pages it sits on surface as a `coverage.gaps` entry instead, because inventing a section to swallow them is exactly the papering-over the coverage assertion exists to prevent.

## What it does

For each document in `clean_text/output.json`:

1. Flattens every page's blocks and every `kind: "figure"` figure into one list ordered by `(page, y)`. `kind: "table"` figures are held back — they are the demotion target for a complex table, not standalone illustrations, and are placed by the table block itself.
2. Assigns each item to its owning boundary. A level-1 node that owns content directly (a chapter preamble, before its first section heading) becomes that chapter's `overview` section.
3. Renders each section's items, in order, into the contract's Markdown subset: ATX `##`–`####` headings, paragraphs, `-` and `1.` lists, GFM pipe tables, and images each followed by an italic caption line. No raw HTML, no blockquotes, no code fences, and **no H1 repeating the section's own title**.
4. Demotes a table it cannot honestly render — merged cells arrive here as ragged rows — to the rasterised `kind: "table"` image `extract_figures` made of the same region, joined on `table_figure_id(page, index)` (`p004-t01`), plus its caption.
5. Drops a paragraph that duplicates a caption already emitted under its image on the same page. `clean_text` has no knowledge of figures, so a caption line reaches this step as ordinary prose as well; this is the first place both facts are known, so it is where the duplicate is removed.
6. Asserts coverage, sets `publishable`, and writes a `CoverageGap` / `CoverageOverlap` error naming every affected page.

Supports **incremental resumption** via `IncrementalWriter` (`key_field="doc_slug"`) and `--doc` scoping (`add_doc_arg`).

## Coverage is a gate, not an abort

A document that fails the check still gets its Markdown and its output record — marked `publishable: false`. Nothing here is process-fatal. `publish_bundles` is what actually withholds it, listing it under `index.json`'s `failed`. The contract's guarantee (§7) is that a document is never *half* published, not that a bad document stops the batch.

| Field | Meaning |
|---|---|
| `covered` | Every page that contributed content to some section |
| `gaps` | Pages `1..page_count` that contributed to none — content that vanished |
| `overlaps` | Pages claimed by two or more sections; the contract requires exactly one |
| `empty_sections` | Section headings that own no text or figures. **Informational** — an empty section does not by itself block publication |

`publishable` is `false` iff `gaps` or `overlaps` is non-empty.

## Input

A **three-way fan-in**, plus provenance:

| Source | Resolved via | Used for |
|---|---|---|
| `clean_text/output.json` | `--input` (required) | The blocks to cut |
| `detect_structure/output.json` | sibling: `Path(--input).parents[1] / "detect_structure"` | Section boundaries, `detection_method`, `page_count` |
| `extract_figures/output.json` | sibling | Figures to interleave, and the rasterised copies of complex tables |
| `fetch_pdfs/output.json` | sibling | `doc_title`, `source_url`, `public_body_id` — three contract frontmatter keys that exist nowhere else upstream |

The shared runner passes exactly one `--input`, so further upstreams are resolved by path, the way `export_status` does in `foi_pipeline`.

## Output

`output.json` — `{ metadata, results: [...] }`, mirroring the contract's `meta.json` shape. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Natural key |
| `doc_title`, `source_url`, `public_body_id` | Provenance, carried from `fetch_pdfs` |
| `page_count`, `detection_method` | Carried from `detect_structure` |
| `sections_dir` | `sections/<doc_slug>`, relative to this step directory |
| `chapters` | `[{slug, title, order, source_pages, sections: [{slug, title, order, file, source_pages, word_count, assets}]}]` |
| `coverage` | `{page_count, covered, gaps, overlaps, empty_sections}` |
| `publishable` | `false` when `gaps` or `overlaps` is non-empty |

`file` paths are relative to **this step directory** (`sections/<doc_slug>/<chapter-slug>/<section-slug>.md`) and so carry a `<doc_slug>` segment the contract's `meta.json` does not — a bundle is per-document, so `publish_bundles` strips it when it writes `meta.json`.

`order` is `chapter_number * 100 + section_number`, computed by `detect_structure`; chapters use `* 100 + 0`. It gives a stable integer sort across the whole document without parsing slugs.

### `sections/<doc_slug>/<chapter-slug>/<section-slug>.md`

YAML frontmatter carrying **exactly** these eleven keys, in this order, then the body:

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

`frontmatter()` raises on a missing or surplus key rather than silently shipping a payload the web repo's schema will reject.

Image references in the body are **bundle-relative** `assets/<figure-id>.webp` — no leading slash, no `..`. The consumer rewrites them to whatever public path it chooses, and the `assets` frontmatter list (bare filenames) is the authoritative index of what a section references, so the rewrite never has to parse Markdown to find images.

`source_pages` is `[first, last]`, inclusive, over the pages a section actually owns content on.

A document's `sections/<doc_slug>/` directory is deleted and rewritten on every run of that document, so a renamed or removed section never leaves a stale `.md` behind.

## Notable files

- `errors.json` — truncated to `[]` at the start of every run. Nothing here is process-fatal.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `CoverageGap` | document, blocking | A page contributed no content to any section. Sets `publishable: false` |
  | `CoverageOverlap` | document, blocking | A page is claimed by two or more sections. Sets `publishable: false` |
  | `EmptySection` | section, informational | A section heading owns no text or figures. Does not block publication |
  | `TableDemoted` | table, informational | Merged or ragged cells; rendered as its rasterised image plus caption instead of a pipe table |
  | `TableDemotionFailed` | table | Too complex for a pipe table *and* no rasterised copy exists, so the table is omitted from the section |
  | `AssembleSectionsFailed` | document | Missing or stale upstream records, or a document shaped in a way the assembly does not expect. The document is skipped and the rest of the batch still runs |

  A document skipped by `AssembleSectionsFailed` is **not** marked processed, so a later run retries it without `--force`.

- `sections/` — generated, gitignored.

## Thresholds

| Constant | Default | Meaning |
|---|---|---|
| `MAX_TABLE_COLUMNS` | 12 | Wider than this is a layout grid, not a table — demote it |
| `MIN_HEADING_LEVEL` / `MAX_HEADING_LEVEL` | 2 / 4 | Body headings are clamped to the contract's `##`–`####` |

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-assemble every document instead of skipping already-processed ones.
- `--verbose` — print each document's section count and whether it is publishable.
