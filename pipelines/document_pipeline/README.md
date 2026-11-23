# document_pipeline

Turns a curated list of large public-interest PDFs (transport strategies, statutory reviews, policy reports) into per-section Markdown plus extracted figures. It packs each document as one reproducible bundle (a single archive of that document's output) and publishes the bundle to `public/documents/`. The full data contract that both this pipeline and the web repo build against is [`docs/superpowers/specs/2026-08-10-document-bundle-contract.md`](../../docs/superpowers/specs/2026-08-10-document-bundle-contract.md). Read that file first for the frontmatter keys, the slug rules, the `index.json` shape and the bundle layout. This file describes how to run and triage the pipeline, not the shape of its output.

The authoritative step order is defined in [`pipeline.json`](pipeline.json). The steps run in sequence. Each step writes its output to `steps/<step>/output.json`.

## Step sequence

| # | Step | What it does |
|---|---|---|
| 1 | [`fetch_pdfs`](steps/fetch_pdfs/) | Downloads each document's source PDF from `documents.yml`, or reuses a cached copy. `documents.yml` is the only source. The curator maintains `documents.yml` per policy, and the `input_plans_<domain>.md` files (transport, climate) define the policies. |
| 2 | [`extract_pages`](steps/extract_pages/) | Extracts text spans, drawings, images and tables for each page of each PDF. |
| 3 | [`ocr_pages`](steps/ocr_pages/) | OCRs (reads text from images) only the pages that the curator lists under `ocr_pages` in `documents.yml`. These are full-page images with little or no text layer. Every other page passes through unchanged. |
| 4 | [`detect_structure`](steps/detect_structure/) | Detects the chapter and section tree of each document. The methods are outline, numbering, font hierarchy, or a flat fallback. |
| 5 | [`extract_figures`](steps/extract_figures/) | Groups page geometry into figures (a figure is a graphic region on a page), renders each figure to WebP, and writes a contact sheet for each document. |
| 6 | [`clean_text`](steps/clean_text/) | Reflows raw positioned spans into headings, paragraphs, lists and tables. |
| 7 | [`extract_actions`](steps/extract_actions/) | Classifies the action tables of each document and extracts each action row plus its target date into metadata that a reviewer can read. |
| 8 | [`extract_action_status`](steps/extract_action_status/) | For each document with `role: report`, reads the annex tables and turns every action row into one status observation with a date (status, reported deadline, progress narrative). |
| 9 | [`fetch_status_annexes`](steps/fetch_status_annexes/) | Downloads the `status_annex` workbook (xlsx) that each report declares. It validates the payload (zip format, readable by openpyxl), not the content type. This step always runs. Annexes are a download cache that git ignores. `documents.yml` declares each annex by url and sha256, and the step makes sure that the file matches the declared sha256 before use. |
| 10 | [`extract_annex_status`](steps/extract_annex_status/) | Reads each annex workbook against a reviewed table of header layouts and fails closed (stops with an error instead of guessing). It emits one status observation per row, dated from the report's `published_date`. |
| 11 | [`assemble_sections`](steps/assemble_sections/) | Cuts the cleaned blocks into Markdown for each section, places the figures between them, and makes sure that every page has a section. |
| 12 | [`publish_bundles`](steps/publish_bundles/) | Packs each publishable document into a `bundle.tar.gz` and writes `public/documents/index.json`. |

`ocr_pages`, `detect_structure` and `extract_figures` consume `extract_pages/output.json`. `clean_text` consumes `ocr_pages/output.json`. `extract_action_status` and `assemble_sections` both consume `clean_text/output.json`. `fetch_pdfs` starts `fetch_status_annexes`, which reads only `documents.yml`, and `extract_annex_status` consumes `fetch_status_annexes/output.json`. An annex is an attachment of its report, so the PDF steps never see it. The explicit fan-in dependencies (several steps that feed one step) are recorded in `pipeline.json` under `input_steps`. The shared runner uses those paths for staleness tests and for the `--input` argument. Make sure that you keep that mapping in sync when you change the pipeline order.

## Running it

Run these from inside `pipelines/document_pipeline/`. The pipeline directory of the runner defaults to the current working directory, not the location of the script. If you invoke `process.py` by a path relative to the repo root while `cwd` is the repo root, it fails with `FileNotFoundError: pipeline.json`. If you must run from the repo root, pass the directory explicitly: `uv run python pipelines/document_pipeline/process.py pipelines/document_pipeline --force ...`.

```bash
cd pipelines/document_pipeline

# Full pipeline
uv run python process.py --force --stop-on-error

# One document only (documents.yml's doc_slug)
uv run python process.py --force --stop-on-error --doc gda-transport-strategy-2022-2042
```

`--doc` pairs with `--force` in practice. The shared runner decides staleness from file modification times and does not know about per-document freshness. A scoped run without `--force` can decide that the whole pipeline is already up to date and skip everything.

Run the test suite with `uv run pytest pipelines/document_pipeline/tests -q`.

`ocr_pages` needs the `tesseract` system binary on `PATH`. It also needs `pytesseract` and `pymupdf` from [`requirements.txt`](requirements.txt). If the binary is missing, only the documents that list `ocr_pages` fail. See [`steps/ocr_pages/README.md`](steps/ocr_pages/README.md).

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

`doc_slug` must match `^[a-z0-9]+(-[a-z0-9]+)*$`. It is a permanent public identifier. After a document is published, the web repo builds its URLs and any external links from the slug, so the slug is never changed. `documents.yml` is the only hand-authored input of the pipeline, and the pipeline validates it strictly. A malformed entry is the one condition in this pipeline that is process-fatal (see `documents.py`), because every downstream step uses `doc_slug` as its key.

If the source does not state `title` clearly, read the title from the actual PDF. Do not guess it from the URL filename. Filenames in the `assets.gov.ie` style (for example `20250716_RSS_Phase_2_Action_Plan.pdf`) are abbreviations, not titles. The date in the filename is an upload date, and it is not necessarily the `published_date`. `WebFetch` cannot read PDF text (it sees only the raw binary and reports failure), but it does save the fetched file locally. Extract the cover page directly:

```bash
uv run python3 -c "
import fitz
doc = fitz.open('<path to the WebFetch-saved .pdf>')
print(doc.metadata)          # creationDate is a decent published_date fallback
print(doc[0].get_text())     # cover page usually has the real title + publisher
"
```

If you set `public_body_id`, it must be a real id from the Public Bodies dataset. Look the id up. Do not type it from memory. Use `pipelines/foi_pipeline/steps/find_public_bodies/output.json` (the `public_bodies` array, 883 entries). That file has the small integer id (for example `1213`) that `documents.yml` requires:

```bash
python3 -c "
import json
bodies = json.load(open('pipelines/foi_pipeline/steps/find_public_bodies/output.json'))['public_bodies']
print([b for b in bodies if b['name'] == '<publisher name>'])
"
```

Do not use `public/latest/public-bodies/public-bodies.csv` for this lookup. Its `id` column is a slug URL (`https://data.publicinformation.ie/body/...`), not the integer that `documents.py` validates against, so a value copied from there will fail validation. A wrong id here has caused real data-integrity bugs elsewhere in this repo (`orphan` errors in `export_status`). The same care applies here, even though `document_pipeline` does not share that guard.

`role`, `reports_on`, `expected_action_count` and `expected_status_counts` distinguish a plan from a progress report. They fix what the extraction of the document will produce, so a regression in `extract_actions` or `extract_action_status` fails loudly instead of publishing a smaller number without a warning:

- `role` is `"plan"` (the default when omitted) or `"report"`. `extract_actions` only scopes to `plan` documents. `extract_action_status` only processes `report` documents.
- `reports_on` is required when `role: report` and forbidden otherwise (a violation either way is process-fatal, see `documents.py`). It is the `doc_slug` of the plan that this report reports progress against. It must resolve to a real entry in `documents.yml` with `role: plan`. A `reports_on` value that does not resolve is process-fatal too.
- `expected_action_count` is optional and applies to plan documents only. It is the number of action rows that `extract_actions` is expected to find. The step uses it as an assertion (a comparison against an expected value), not as a target to extract towards.
- `expected_status_counts` is optional and applies to report documents only. It is a `{status: count}` mapping (`Complete`, `OnSchedule`, `Delayed`, `Ongoing`, `Modified`). The tally from `extract_action_status` is expected to match it exactly.

- `status_source` is optional and applies to report documents only (it is rejected on a plan, and `"annex"` is the only valid value). It declares that the machine-readable status detail of the report is published in a companion spreadsheet, not in the PDF. `extract_action_status` then skips the report by declaration, with no status record and no `UnknownReportFormat` error, while the PDF still publishes as a normal document bundle. A report without the marker whose layout is unrecognized still produces an error. The Climate Action Plan progress reports use it.

- `hold` is optional and applies to any document. It is a non-empty string that gives the human reason why the document is deliberately withheld. `publish_bundles` lists a held document under `index.json` `failed` with `reason: "held"` and this string as `message`. It writes no bundle and removes any stale bundle. This happens whether or not `assemble_sections` says that the document is publishable, because hold wins over `not_publishable`. If other documents list this document in `reports_on`, keep the entry. Remove `hold` to publish.

The policy inventory is merged from every `input_plans_<domain>.md` file in this directory (`input_plans_transport.md`, `input_plans_climate.md`). `policies.py` parses those files into one namespace, and each record carries its `domain`. `policy_id` must resolve against that inventory. A `policy_id` that two files define is process-fatal. `number` is row order within its own file, and it is never an identifier across domains. Datasets built from the inventory filter to their own domain (for example, `scripts/transform_transport_policies.py` publishes only records with `domain == "transport"`). Adding a domain therefore does not change the published dataset of another domain. Annual plans are editions of one policy: the single `climate-action-plan` policy holds the CAP23–CAP25 plan PDFs and their progress reports.

A `primary` plan document is not a source of actions. `extract_actions` reads only documents with `policy_role: action-plan`. It bundles and publishes a `primary` plan (such as each Climate Action Plan PDF) as a document. It skips that plan with "not an action plan", so the plan contributes nothing to the actions dataset. To declare a document `action-plan` is a deliberate and separate curation decision.

Then run the pipeline scoped to the new document, from inside `pipelines/document_pipeline/` (see "Running it" above for why `cwd` matters here):

```bash
uv run python pipelines/document_pipeline/process.py pipelines/document_pipeline --force --stop-on-error --doc <the-new-slug>
```

After the run finishes, make sure that `steps/*/errors.json` has no entries tagged with the new `doc_slug`. Make sure that the document appears in `public/documents/index.json` with an empty `failed` list. The `errors.json` triage table below shows which error types are informational and which ones mean that the step skipped the document.

## Correcting a misread document

`detect_structure` sometimes gets the chapter and section tree of a document wrong. It can miss a heading, assign a wrong parent, or give a node a wrong title. Do not hand-edit the generated output. Add a correction to `steps/detect_structure/override.json` (absent by default, so create it when needed), keyed by `doc_slug`:

```json
{"gda-transport-strategy-2022-2042": [
  {"slug": "10-walking-accessibility-and-public-realm", "title": "10 Walking, Accessibility and Public Realm"}
]}
```

You can set any node field except `slug` (`level`, `number`, `title`, `start_page`, `start_y`, `end_page`, `confidence`, `parent`, `order`). The slug is the identity of the node, and an override never rewrites it, so a retitle cannot break a published URL. To apply the override, re-run `detect_structure` (and everything after it) with `--force --doc <slug>`. See [`steps/detect_structure/README.md`](steps/detect_structure/README.md) for the full override semantics, including how the step recomputes derived fields (`parent`, `order`, `end_page`) around a hand-set value.

This is a node-level override. It is not the record-level `override_path` mechanism of `IncrementalWriter` that other pipelines in this repo use (for example, `foi_pipeline`). That mechanism replaces whole output records instead of patching individual fields of one record.

## Reading a contact sheet to tune figure thresholds

Every threshold that `extract_figures` uses (cluster gap, minimum area, prose-rejection ratio, caption search band, and so on) is an empirical module-level constant in `steps/extract_figures/process.py`. See the README of that step for the full table. The constants come from the source design. They are expected to need tuning against the first real document that goes through this pipeline. A 4-page fixture and a 400-page transport strategy do not share a figure-density profile.

After a run, open `steps/extract_figures/contact-sheets/<doc_slug>.html` in a browser. It shows every rendered region (a figure or a rasterized table) with its id, kind, page, bbox and pixel size. It also shows the exact threshold values that the run used, printed in the header of the sheet, so you always know what produced what you look at. Look for:

- Missed figures: a chart or map that is visible in the source PDF but absent from the sheet. Usually `MIN_AREA_FRACTION` or `MIN_DIMENSION` is too aggressive, or the step rejected the region as prose (`PROSE_RATIO`/`PROSE_MIN_LINES`) because it has dense text labels.
- Merged figures: two unrelated graphics that are fused into one region. Usually `CLUSTER_GAP` is too generous.
- Furniture captured as a figure: a background panel or rule line in the sheet. Usually `FULL_PAGE_FRACTION` or `RULE_THICKNESS` needs tightening.
- Missing or wrong captions: make sure that `CAPTION_BAND` is right. The step will not match a caption that is farther than that distance from its figure. The figure then falls back to `Figure from page N`, which is logged as `MissingCaption` and is not fatal.

Tune the constant, re-run `extract_figures --force --doc <slug>`, and reload the contact sheet. A number whose effect you can see is worth more than a number you can justify from first principles.

## `errors.json` triage

Every step writes `errors.json` (truncated to `[]` at the start of each run). The entries are per figure, per page or per document, and each one is tagged by `error_type`. The README of each step has the full list. It also shows which entries are merely informational (for example, `SuspectReadingOrder`, `TableDemoted`) and which entries skip a document outright. The four types most likely to need a human decision are the document-acquisition failures of `fetch_pdfs`. Its own module docstring calls them out as "four failure conditions". Each one is non-fatal to the run but fatal to that one document until someone looks:

| `error_type` | Cause | Typical fix |
|---|---|---|
| `FetchFailed` | The URL in `documents.yml` returned an error, timed out, or is unreachable | Make sure that the URL still resolves. The publisher can move or remove the PDF |
| `NotAPdf` | The server responded, but the payload is not a PDF (wrong `Content-Type`, or a login or redirect page) | Update the URL to a direct download link if needed |
| `EncryptedPdf` | The PDF opens but is password-protected | Out of scope. This pipeline does not try to remove PDF passwords. Find an unprotected copy or drop the document |
| `UnreadablePdf` | PyMuPDF cannot open the downloaded file at all (corrupt download, malformed PDF) | Re-download the file manually and compare. If the source file is genuinely broken, this pipeline cannot process this document |

A document that any of the four skips is not marked processed, so the next run retries it automatically after you fix `documents.yml` or the source URL. That document needs no `--force`.

## Measuring chapter-split accuracy

The tree from `detect_structure` is checked by `validate_split` (shape only) and by `eval/compare.py` (change only). Neither one says whether the split is right. `steps/detect_structure/eval/score.py` scores the detected chapters against committed gold lists (hand-authored reference lists) that a person transcribed from the printed table of contents of each document. It then diffs the result against a committed baseline, so a change to the detector is a per-document diff instead of a guess.

```bash
cd pipelines/document_pipeline
PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py
```

Read [`steps/detect_structure/eval/gold/GUIDELINE.md`](steps/detect_structure/eval/gold/GUIDELINE.md)
before you add a gold document. The flags of the report and the annotation workflow are documented in
[`steps/detect_structure/README.md`](steps/detect_structure/README.md#accuracy-evaluation-gold-chapters).
The report is read-only and offline, and it is not part of CI. Run it before and after a change to detection.

## Common files in each step directory

| File | Purpose |
|---|---|
| `process.py` | Entry point for the step |
| `output.json` | Output of the step, read by downstream steps (gitignored) |
| `errors.json` | Errors per figure, page or document. They are informational or actionable. See the README of each step (gitignored) |
| `pipeline-status.json` | Execution metadata written by the process script (gitignored) |
| `override.json` | Corrections written by hand that automation never overwrites (only `detect_structure` uses this today) |

See the parent [`AGENTS.md`](../../AGENTS.md) for the conventions of the repository, the Dataset Version Bumps process, and where `document_pipeline` fits alongside the other pipelines in this repo.

## Learnings from adding a corpus (Climate Action Plan, 2026-11)

- Scoped publishes are destructive. A `--doc` run of `publish_bundles` deletes the bundle of every other document and rewrites `index.json`. Use scoped runs only to experiment, then run `git checkout -- public/documents && git clean -fdq public/documents`. For the real publish, run the full pipeline. Each run overwrites `steps/*/errors.json`, so snapshot that file between scoped runs.
- Published bundles can lag the code. Bundles are rebuilt only on a publish, so a full run after pipeline commits (for example, TOC-name detection or text repair) also changes existing documents. When you add documents, do not let that change ride along. Restore the existing bundle dirs from git and splice the old `index.json` entries (rebuild `index.html` with `publish_bundles.build_index_html`). Republish stale documents in their own reviewed commit.
- You can publish a few documents without a full run. Build each document with a scoped run and copy out its `public/documents/<slug>/` dir and its `index.json` entry. Revert `public/documents`, then copy the dirs back. Insert the entries into `index.json` from `HEAD` (sorted by slug, removed from `failed`) and rebuild `index.html`. Never keep the `index.json` of the scoped run. It lists only the documents in the accumulated `output.json` of the step, and it can drop entries such as `held` ones. Note that `index.json` and `bundle.tar.gz` are Git LFS files, so compare their content, not the pointer diff.
- Image-only pages (a coverage gap on a full-page raster) are fixed by listing them under `ocr_pages` in `documents.yml`, so that the `ocr_pages` step reads them. Never fix them by marking them furniture. Make sure that the gap list agrees with the PDF: a scanned page that carries a printed page number is not a gap page but still needs listing.
- Withholding a document is done with `hold: "<reason>"` in `documents.yml`, not with a coverage gap. A gap is fragile because a well-meaning furniture fix publishes the document without a warning. The document lands under `index.json` `failed` with `reason: "held"`. Keep the entry if other documents `reports_on` it.
- Furniture overrides are for blank pages or pages with only a running header. Before you add a gap page to `assemble_sections/override.json`, OCR it (tesseract is available). Do not mark full-page raster pages with real content as furniture. List such pages under `ocr_pages` in `documents.yml` instead, so that the `ocr_pages` step reads them (see `steps/ocr_pages/README.md`).
- Policies are multi-domain. Each `input_plans_<domain>.md` file defines a domain. `load_policies()` merges them, the records carry `domain`, and the transport dataset filters on `DOMAIN = "transport"`. A new corpus means a new `input_plans_*.md` file plus a policy for each plan family.
- `status_source: annex` on a report in `documents.yml` makes `extract_action_status` skip the report (status lives in companion spreadsheets). The report still bundles. Plans use `policy_role: primary`, so the pipeline extracts no action records.
- Dating: take `published_date` only from a source that agrees with the cover (the listing page, or a PDF creation date that matches the cover month). Otherwise omit it.
- Utilities: `orphans.py` needs `PYTHONPATH=../../src` and a command (`manifest`/`apply`). A `curl` request to gov.ie returns 403 (use a fetch tool), and `assets.gov.ie` PDFs download with a browser User-Agent.
- Worktrees do not carry the gitignored pipeline state or the untracked OpenSpec dirs. Copy the change dir in. A push of a fast-forward `HEAD:main` from a worktree publishes without touching a dirty main checkout.
