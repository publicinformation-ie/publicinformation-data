# document_pipeline

Turns a curated list of large public-interest PDFs (transport strategies, statutory reviews, policy reports) into per-section Markdown plus extracted figures, packaged as one reproducible bundle per document and published to `public/documents/`. The full data contract both this pipeline and the web repo build against is [`docs/superpowers/specs/2026-08-10-document-bundle-contract.md`](../../docs/superpowers/specs/2026-08-10-document-bundle-contract.md) — read that first for the frontmatter keys, slug rules, `index.json` shape and bundle layout; this file is about running and triaging the pipeline, not the shape of its output.

The authoritative step order is defined in [`pipeline.json`](pipeline.json). Steps run sequentially; each writes its output to `steps/<step>/output.json`.

## Step sequence

| # | Step | What it does |
|---|---|---|
| 1 | [`fetch_pdfs`](steps/fetch_pdfs/) | Downloads (or reuses a cached copy of) each document's source PDF from `documents.yml`. |
| 2 | [`extract_pages`](steps/extract_pages/) | Extracts page-level text spans, drawings, images and tables from each PDF. |
| 3 | [`detect_structure`](steps/detect_structure/) | Detects each document's chapter/section tree — outline, numbering, font-hierarchy or flat fallback. |
| 4 | [`extract_figures`](steps/extract_figures/) | Clusters page geometry into figures, renders them to WebP, writes a contact sheet per document. |
| 5 | [`clean_text`](steps/clean_text/) | Reflows raw positioned spans into headings, paragraphs, lists and tables. |
| 6 | [`assemble_sections`](steps/assemble_sections/) | Cuts cleaned blocks into per-section Markdown, interleaves figures, asserts page coverage. |
| 7 | [`publish_bundles`](steps/publish_bundles/) | Packs each publishable document into a `bundle.tar.gz` and writes `public/documents/index.json`. |

Three of these steps — `detect_structure`, `extract_figures` and `clean_text` — all consume `extract_pages/output.json` directly, not whichever step immediately precedes them in the table above. The shared runner (`src/lib/pipeline_runner.py`) only ever chains `--input` to the *immediately preceding* step's own output, so `extract_figures` and `clean_text` resolve `extract_pages/output.json` by a fixed sibling path instead of trusting `--input` (see the "Fan-in" comment in each `process.py`). `detect_structure` happens to sit directly after `extract_pages` in the table, so it does not need the same treatment — but that is a property of the current step order, not a guarantee; if the order in `pipeline.json` ever changes, check this first.

## Running it

Run these from inside `pipelines/document_pipeline/` — the runner's pipeline directory defaults to the current working directory, not the script's location, so invoking `process.py` by its repo-root-relative path while `cwd` is the repo root fails with `FileNotFoundError: pipeline.json`. (If you must run from the repo root, pass the directory explicitly: `uv run python pipelines/document_pipeline/process.py pipelines/document_pipeline --force ...`.)

```bash
cd pipelines/document_pipeline

# Full pipeline
uv run python process.py --force

# One document only (documents.yml's doc_slug)
uv run python process.py --force --doc gda-transport-strategy-2022-2042
```

`--doc` pairs with `--force` in practice: the shared runner's mtime-based staleness check does not know about per-document freshness, so a scoped run without `--force` may decide the whole pipeline is already up to date and skip everything.

Run the test suite with `uv run pytest pipelines/document_pipeline/tests -q`.

## Adding a document

Add an entry to [`documents.yml`](documents.yml):

```yaml
documents:
  - doc_slug: gda-transport-strategy-2022-2042   # permanent — never change once published, see below
    title: "Greater Dublin Area Transport Strategy 2022–2042"
    url: "https://www.nationaltransport.ie/wp-content/uploads/2022/01/GDA-Transport-Strategy-2022-2042.pdf"
    publisher: "National Transport Authority"     # optional
    public_body_id: 1570                          # optional — verify by lookup, never type from memory
    published_date: "2023-01-19"                  # optional, YYYY-MM-DD
```

`doc_slug` must match `^[a-z0-9]+(-[a-z0-9]+)*$` and is a permanent public identifier — once a document is published, the web repo's URLs and any external links are built from it, so it is never changed. `documents.yml` is the pipeline's only hand-authored input and is validated strictly: a malformed entry is the one condition in this pipeline that is process-fatal (see `documents.py`), because every downstream step is keyed on `doc_slug`.

**`title`, if not confirmed from the source, must be read off the actual PDF — not guessed from the URL filename.** `assets.gov.ie`-style filenames (e.g. `20250716_RSS_Phase_2_Action_Plan.pdf`) are abbreviations, not titles, and the filename date is an upload date, not necessarily the `published_date`. `WebFetch` cannot read PDF text (it only sees the raw binary and reports failure) but it does save the fetched file locally, so extract the cover page directly:

```bash
uv run python3 -c "
import fitz
doc = fitz.open('<path to the WebFetch-saved .pdf>')
print(doc.metadata)          # creationDate is a decent published_date fallback
print(doc[0].get_text())     # cover page usually has the real title + publisher
"
```

**`public_body_id`, if set, must be a real id from the Public Bodies dataset.** Look it up — don't type it from memory. Use `pipelines/foi_pipeline/steps/find_public_bodies/output.json` (`public_bodies` array, 883 entries) — it has the small integer id (e.g. `1213`) that `documents.yml` requires:

```bash
python3 -c "
import json
bodies = json.load(open('pipelines/foi_pipeline/steps/find_public_bodies/output.json'))['public_bodies']
print([b for b in bodies if b['name'] == '<publisher name>'])
"
```

Don't use `public/latest/public-bodies/public-bodies.csv` for this lookup — its `id` column is a slug URL (`https://data.publicinformation.ie/body/...`), not the integer `documents.py` validates against, so a value copied from there will fail validation. A wrong id here has caused real data-integrity bugs elsewhere in this repo (`orphan` errors in `export_status`) — the same care applies here even though `document_pipeline` doesn't share that guard.

Then run the pipeline scoped to the new doc, from inside `pipelines/document_pipeline/` (see "Running it" above for why cwd matters here):

```bash
uv run python pipelines/document_pipeline/process.py pipelines/document_pipeline --force --doc <the-new-slug>
```

After it finishes, check `steps/*/errors.json` for entries tagged with the new `doc_slug` and confirm the doc appears in `public/documents/index.json` with an empty `failed` list — see the `errors.json` triage table below for which error types are informational versus which mean the document was skipped.

## Correcting a misread document

`detect_structure` sometimes gets a document's chapter/section tree wrong — a heading missed, a wrong parent, a mistitled node. Rather than hand-editing generated output, add a correction to `steps/detect_structure/override.json` (absent by default; create it when needed), keyed by `doc_slug`:

```json
{"gda-transport-strategy-2022-2042": [
  {"slug": "10-walking-accessibility-and-public-realm", "title": "10 Walking, Accessibility and Public Realm"}
]}
```

Any node field except `slug` may be set (`level`, `number`, `title`, `start_page`, `start_y`, `end_page`, `confidence`, `parent`, `order`) — the slug is the node's identity and is never itself rewritten by an override, so a retitle cannot break a published URL. Re-run `detect_structure` (and everything after it) with `--force --doc <slug>` to apply it. See [`steps/detect_structure/README.md`](steps/detect_structure/README.md) for the full override semantics, including how derived fields (`parent`, `order`, `end_page`) are recomputed around a hand-set value.

This is a *node-level* override, distinct from `IncrementalWriter`'s record-level `override_path` mechanism used elsewhere in this repo (e.g. `foi_pipeline`), which replaces whole output records rather than patching individual fields of one.

## Reading a contact sheet to tune figure thresholds

Every threshold `extract_figures` uses (cluster gap, minimum area, prose-rejection ratio, caption search band, and so on) is an empirical module-level constant in `steps/extract_figures/process.py` — see that step's README for the full table. They are carried over from the source design and are expected to need tuning against the first real document a document goes through: a 4-page fixture and a 400-page transport strategy do not share a figure-density profile.

After a run, open `steps/extract_figures/contact-sheets/<doc_slug>.html` in a browser. It shows every rendered region — figure and rasterised table — with its id, kind, page, bbox and pixel size, plus the exact threshold values the run used (printed in the sheet's header, so you always know what produced what you're looking at). Look for:

- **Missed figures** — a chart or map visible in the source PDF but absent from the sheet. Usually `MIN_AREA_FRACTION` or `MIN_DIMENSION` is too aggressive, or the region was rejected as prose (`PROSE_RATIO`/`PROSE_MIN_LINES`) because it has dense text labels.
- **Merged figures** — two unrelated graphics fused into one region. Usually `CLUSTER_GAP` is too generous.
- **Furniture captured as a figure** — a background panel or rule line in the sheet. Usually `FULL_PAGE_FRACTION` or `RULE_THICKNESS` needs tightening.
- **Missing or wrong captions** — check `CAPTION_BAND`; a caption more than that distance from its figure will not be matched, and the figure falls back to `Figure from page N` (logged as `MissingCaption`, not fatal).

Tune the constant, re-run `extract_figures --force --doc <slug>`, and reload the contact sheet — a number whose effect you can see is worth more than a number you can justify from first principles.

## `errors.json` triage

Every step writes `errors.json` (truncated to `[]` at the start of each run) with per-figure, per-page or per-document entries tagged by `error_type`; see each step's own README for its full list and which entries are merely informational (e.g. `SuspectReadingOrder`, `TableDemoted`) versus which skip a document outright. The four types most likely to need a human decision are `fetch_pdfs`'s document-acquisition failures — its own module docstring calls them out as "four failure conditions", each non-fatal to the run but fatal to that one document until someone looks:

| `error_type` | Cause | Typical fix |
|---|---|---|
| `FetchFailed` | The URL in `documents.yml` returned an error, timed out, or is unreachable | Check the URL still resolves; the publisher may have moved or removed the PDF |
| `NotAPdf` | The server responded, but the payload is not a PDF (wrong `Content-Type`, or a login/redirect page) | The URL may need updating to a direct download link |
| `EncryptedPdf` | The PDF opens but is password-protected | Out of scope — this pipeline does not attempt to remove PDF passwords; find an unprotected copy or drop the document |
| `UnreadablePdf` | PyMuPDF cannot open the downloaded file at all (corrupt download, malformed PDF) | Re-download manually and compare; if the source file is genuinely broken, this document cannot be processed |

A document skipped by any of the four is **not** marked processed, so the next run retries it automatically once `documents.yml` or the source URL is fixed — no `--force` needed for that one document.

## Common files in each step directory

| File | Purpose |
|---|---|
| `process.py` | Entry point for the step |
| `output.json` | Step output, consumed downstream (gitignored) |
| `errors.json` | Per-figure/page/document errors — informational or actionable, see each step's README (gitignored) |
| `pipeline-status.json` | Execution metadata written by the process script (gitignored) |
| `override.json` | Hand-authored corrections that are never overwritten by automation (only `detect_structure` uses this today) |

See the parent [`AGENTS.md`](../../AGENTS.md) for repository-wide conventions, the Dataset Version Bumps process, and where `document_pipeline` fits alongside the other pipelines in this repo.
