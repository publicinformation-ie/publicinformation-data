# minutes_pipeline

Ingests Irish local-authority council meeting minutes (MVP: Meath County Council) and extracts the motions from each minutes document. A motion is a formal proposal put to a vote. Discovery mirrors the FOI pipeline's shape (authorities → minutes pages → minutes PDFs → text), but motion extraction is prose: an LLM reads each document and returns structured JSON. The pipeline then canonicalizes that JSON into stable, deduplicated motion records exported under `public/motions/`.

The authoritative step order is defined in [`pipeline.json`](pipeline.json). Steps run sequentially. Each step writes its output to `steps/<step>/output.json`.

## Step sequence

| # | Step | What it does |
|---|---|---|
| 1 | [`find_local_authorities`](steps/find_local_authorities/) | Joins the committed hand-authored authority name list to the CSO `resolve_website_urls` output, emitting the 31 local authorities with their `public_body_id`, `slug`, and municipal districts. This is the pipeline's `body_list_step` (`--public-body` values must appear in its output). |
| 2 | [`find_meeting_minutes_pages`](steps/find_meeting_minutes_pages/) | Resolves the minutes-publishing page per body/district: committed `override.json` URLs first (no HTTP), crawl-scoring fallback over the homepage otherwise. |
| 3 | [`find_meeting_minutes_pages_search`](steps/find_meeting_minutes_pages_search/) | Apify batch search for bodies where the crawl failed (`APIFY_TOKEN` required). It passes crawl successes through unchanged. |
| 4 | [`find_minutes_files`](steps/find_minutes_files/) | Crawls each minutes page (following year links one level deep), collecting links to minutes PDFs with a deterministic `meeting_date` where derivable. |
| 5 | [`transform_minutes_files`](steps/transform_minutes_files/) | Downloads each PDF and extracts prose text with pdfplumber (image-only scans yield empty text). |
| 6 | [`ocr_minutes_files`](steps/ocr_minutes_files/) | OCRs records whose text is blank or under 200 chars with Tesseract (pymupdf render and pytesseract). It passes usable records through unchanged and quarantines still-unusable ones (it sets them aside and skips them on later runs). |
| 7 | [`extract_motions`](steps/extract_motions/) | One LLM request per chunk (documents of 80,000 characters or fewer are one chunk) via the shared `src/lib/llm_extract.py`, returning `{"motions": [{motion_text, proposer, seconder, status_label}, …], "meeting_date": <LLM guess or null>}`. Chunk results merge in order, and the step carries the LLM's first non-null date forward as `stated_date`. A two-stage guard skips extreme CE-recommendation schedules before the LLM call. After extraction it quarantines procedural acceptance dumps (`motions: null`, `skip_reason`, `guard_evidence`). Reads `ocr_minutes_files/output.json`. |
| 8 | [`resolve_meeting_date`](steps/resolve_meeting_date/) | Deterministic per-document date resolution: a full date from `find_minutes_files`, else an LLM `stated_date` that parses to a full day, else a `<day> <Month>` from the document header combined with the `<Month> <YYYY>` in the link text (month cross-checked, and the URL folder is never a year source). An unresolvable date on a document with motions → `UnresolvedMeetingDate`. |
| 9 | [`canonicalize_motions`](steps/canonicalize_motions/) | Deterministic fan-in (it merges the outputs of earlier steps): maps status to the closed set, resolves the composite id `<slug>/<meeting_date>/m<NNN>`, dedupes, classifies meeting type. |
| 10 | [`export_motions`](steps/export_motions/) | Groups by authority and writes `public/motions/<slug>.json` plus `public/motions/index.json`. |

> Note: `find_meeting_minutes_pages` and `extract_motions` write `dirty_ids.json` files that no downstream step reads. `find_meeting_minutes_pages_search` does not read its upstream, and `resolve_meeting_date` does not use the dirty file. Those files only grow and are not pending work.

## Committed inputs (source of truth)

- [`steps/find_local_authorities/local_authorities.json`](steps/find_local_authorities/local_authorities.json): the 31-authority name list. Names must match the CSO output exactly. A name missing there is fatal.
- [`steps/find_meeting_minutes_pages/override.json`](steps/find_meeting_minutes_pages/override.json): curated `minutes_page_url` per body/district. It wins over crawling and makes no HTTP call. MVP caveat: the Meath URLs are placeholders. Make sure that you fill them before the first real run (see the override file's commit note).

## Running it

Run from the repo root, passing the pipeline directory explicitly (the shared runner's pipeline directory defaults to your current working directory):

```bash
# Full pipeline
uv run python pipelines/minutes_pipeline/process.py pipelines/minutes_pipeline --force --stop-on-error

# Meath only (scope to one authority)
uv run python pipelines/minutes_pipeline/process.py pipelines/minutes_pipeline --public-body 1511 --force --stop-on-error
```

`find_meeting_minutes_pages`, `find_meeting_minutes_pages_search` (Apify credits), `find_minutes_files`, `transform_minutes_files` and `extract_motions` make live HTTP and LLM calls. `extract_motions` requires the `MOTIONS_LLM_*` environment configuration (see `src/lib/llm_extract.py`). The OCR step needs the `tesseract` system binary on `PATH` (see [`steps/ocr_minutes_files/README.md`](steps/ocr_minutes_files/)). Run the test suite with `uv run pytest pipelines/minutes_pipeline/tests -q`.

## OCR and quarantine

`ocr_minutes_files` passes records with at least 200 characters of extracted text through unchanged. Blank or near-empty records get one Tesseract pass over the rendered PDF pages. If the result is still under 200 characters, the step logs `EmptyTextExtraction` or `NearEmptyText` and adds the `file_url` to `quarantined_ids.json`. Later runs skip that file. `--force` clears the quarantine and retries every file. If an OCR attempt raises, the step logs `OcrFailed` and retries the file on the next run. The file is not quarantined.

## Status script

Per the repo norm (see root `AGENTS.md`), run [`status.py`](status.py) for triage before you dig into step outputs. It walks one authority through every step: record counts per stage, that body's errors per step, and a verdict that names where the pipeline runs dry:

```bash
# By id or slug
uv run python pipelines/minutes_pipeline/status.py --public-body 1456
uv run python pipelines/minutes_pipeline/status.py --public-body carlow

# Bodies x steps matrix (rollout overview); --csv for spreadsheets
uv run python pipelines/minutes_pipeline/status.py --all
uv run python pipelines/minutes_pipeline/status.py --all --csv
```

Columns: per-step body record count, step completion time, body error count, plus stage signals (`website=MISSING`, `empty_text=`, `motions_null=`/`skipped=`/`motions_extracted=`, `date_unresolved=`). Errors are attributed via `errors.json → context.public_body_id`, grouped by type with an example `file_url` each.

Exit codes: `0` means the body flows end to end (≥1 motion exported). `1` means it runs dry (the first zero-record step is named, so fix there first). `2` means an unknown body or a missing authority output. The script flags drop-offs between consecutive stages as warnings (e.g. files found but none transformed). `--all` always exits `0` on success (`2` on data error). Its `DRY_AT` column carries the per-body verdict (`flowing` or the short step label).

## Motion status closed set

`carried`, `carried_as_amended`, `not_carried`, `withdrawn`, `deferred`, `not_recorded`.

## Fail-closed error policy

This aligns with the repo-wide data-handling principle: never guess, silently null, or silently drop.

- Unmappable `status_label` → `not_recorded` plus an `errors.json` entry.
- Unresolvable `meeting_date` on a document that carried motions → `UnresolvedMeetingDate` in `resolve_meeting_date/errors.json` (the motion is still excluded downstream, because it has no stable id). That document's `file_url` also appears in `canonicalize_motions/errors.json` as `MissingMeetingDate` (a defensive second guard), so two steps' error files record the same URL.
- A document that produced no motions → `NoMotionsExtracted` in `canonicalize_motions/errors.json` (no `MissingMeetingDate` noise for motion-less scans).
- Failed or unparseable LLM response → the whole document gets `motions: null` plus a per-document error (no partial guess).
- Guard quarantine → `MotionExtractionSkipped` in `extract_motions/errors.json` and `SkippedDocument` in `canonicalize_motions/errors.json`. `motions: null` means the step publishes nothing.
- A committed authority name missing from the CSO output → fatal, not a silent drop.

A run with unresolved reconstruction errors requires human review before publication. The MVP public output under `public/motions/` must be reviewed before merging to `main` (merging is what publishes).
