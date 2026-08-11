# publish_bundles

Packs each publishable document's sections and assets into a reproducible `.tar.gz` bundle, and (re)writes `public/documents/index.json` — the library manifest the web repo's seed fetches first. Ninth and final step in `document_pipeline`.

Shapes are fixed by **`docs/superpowers/specs/2026-08-10-document-bundle-contract.md`** §3 (`index.json`) and §4 (bundle interior). The web repo builds its content pipeline against this contract, not against this step's code.

## Reproducibility is the point

The web repo's skip-if-unchanged cache keys on `bundle_sha256` (contract §7: *"same PDF plus same overrides ⇒ same `bundle_sha256`"*). Two things would silently defeat that:

1. **A naive `tarfile.open(mode="w:gz")`** embeds the current wall-clock time in the gzip header on every run. `build_bundle_bytes()` avoids this by building the tar in memory, then wrapping it with `gzip.GzipFile(..., mtime=0, filename="")` by hand.
2. **A wall-clock timestamp inside the archive's own content.** Each document's `built_at` is therefore pinned to `fetch_pdfs`'s `fetched_at` rather than `datetime.now()` — `fetched_at` only changes when the PDF is actually re-fetched, so an unrelated rerun of `publish_bundles` alone reproduces byte-identical bundles. (`index.json`'s top-level `generated_at` is the one wall-clock timestamp in this step's output, and it is deliberately *not* inside any bundle.)

Every tar entry also gets fixed `mtime`, `uid`, `gid`, `uname`, `gname` and `mode`, and entries are written in sorted-path order.

## Input

A **three-way fan-in**, all resolved by path the way `assemble_sections` resolves its own upstreams — the shared runner passes exactly one `--input`:

| Source | Resolved via | Used for |
|---|---|---|
| `assemble_sections/output.json` | `--input` (required) | Chapters/sections tree, `publishable`, `coverage` |
| `extract_figures/output.json` | sibling: `Path(--input).parents[1] / "extract_figures"` | `figure_count`, and the WebP bytes copied into each bundle |
| `fetch_pdfs/output.json` | sibling | `publisher`, `published_date`, `source_sha256`, `built_at` — provenance the contract needs that `assemble_sections` does not carry (it only forwards `doc_title`, `source_url`, `public_body_id`, the frontmatter keys *it* needs) |

A document `assemble_sections` marked `publishable: false` is skipped here and listed under `index.json`'s `failed` — this is the point at which a coverage gap or overlap actually withholds a document. Nothing else here is process-fatal: a missing asset, a stale sibling record, or any other per-document build failure logs a `PublishBundlesFailed` error and skips just that document, the same isolation `assemble_sections` applies.

## Output

### `public/documents/index.json`

The library manifest, contract §3. Rewritten in full on every run from this step's *entire* accumulated `output.json` (not just documents touched this run), so a document evicted by `--doc` scoping or gone from `documents.yml` disappears from `index.json` too.

| Field | Source |
|---|---|
| `version` | `CONTRACT_VERSION` module constant |
| `generated_at` | Wall-clock time of this `index.json` write — not inside any bundle, so it is not part of the reproducibility guarantee |
| `documents[]` | One entry per publishable, successfully-bundled document, sorted by `doc_slug` |
| `failed[]` | `{doc_slug, reason, message}` for every non-publishable or build-failed document, sorted by `doc_slug` |

### `public/documents/<doc_slug>/`

| File | Also inside the bundle? |
|---|---|
| `bundle.tar.gz` | — |
| `meta.json` | yes |
| `llms.txt` | yes |
| `full.md` | yes |

### Bundle interior (contract §4)

```
meta.json
llms.txt
full.md
sections/<chapter-slug>/<section-slug>.md
assets/<figure-id>.webp
```

- `meta.json` is `assemble_sections`'s per-document record, with each section's `file` rewritten bundle-relative (`sections/<doc_slug>/<chapter>/<section>.md` → `sections/<chapter>/<section>.md` — a bundle is already scoped to one document) and `coverage` trimmed to `{page_count, gaps, overlaps}`.
- `llms.txt` is generated **per document**, not as a single library-wide file the way the source design's `emit_site` step produced it — each bundle now ships standalone (contract §4 lists it inside every bundle), so its own machine-readable index of chapters and sections travels with it.
- `full.md` concatenates every section's body, in chapter/section order, with each section's YAML frontmatter stripped — the concatenated headings carry that information instead. `sections/*.md` inside the bundle keep their frontmatter; `full.md` does not repeat it.
- Only assets actually referenced by some section's `assets` list are copied into the bundle — an unused figure `extract_figures` produced is not.
- Both the tar-entry names (`build_bundle_bytes`) and every computed output path (`doc_slug` in `_write_document`) are validated against `..` and leading `/` before use, even though the inputs are already contract-constrained slugs — defence in depth per the plan's delta 5.

## Notable files

- `errors.json` — truncated to `[]` at the start of every run.

  | `error_type` | Scope | Cause |
  |---|---|---|
  | `PublishBundlesFailed` | document | Missing `fetch_pdfs` record, missing referenced asset, or any other per-document build failure. The document is skipped and the rest of the batch still runs; not marked processed, so a later run retries it |

- `public/documents/` — generated, gitignored, published by `scripts/publish_pages.sh` on the next `public/` commit like every other dataset's `public/*.json`.

## Flags

- `--doc SLUG` — scope processing to one document.
- `--force` — re-publish every document instead of skipping already-processed ones.
- `--public-root PATH` — override `public/documents/` (defaults to the repo root's, resolved from this file's location). Mainly for local testing; the shared runner never passes it.
- `--verbose` — print each document's publish outcome.
