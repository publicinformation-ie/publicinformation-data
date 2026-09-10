# minutes_pipeline

Ingests Irish local-authority council meeting minutes (MVP: Meath County Council) and extracts the **motions** from each minutes document — a motion being a formal proposal put to a vote. Discovery mirrors the FOI pipeline's shape (authorities → minutes pages → minutes PDFs → text), but motion extraction is **prose**: an LLM reads each document and returns structured JSON, which the pipeline then canonicalises into stable, deduplicated motion records exported under `public/motions/`.

The authoritative step order is defined in [`pipeline.json`](pipeline.json). Steps run sequentially; each writes its output to `steps/<step>/output.json`.

## Step sequence

| # | Step | What it does |
|---|---|---|
| 1 | [`find_local_authorities`](steps/find_local_authorities/) | Joins the committed hand-authored authority name list to the CSO `resolve_website_urls` output, emitting the 31 local authorities with their `public_body_id`, `slug`, and municipal districts. This is the pipeline's `body_list_step` (`--public-body` validates against its output). |
| 2 | [`find_meeting_minutes_pages`](steps/find_meeting_minutes_pages/) | Resolves the minutes-publishing page per body/district: committed `override.json` URLs first (no HTTP), crawl-scoring fallback over the homepage otherwise. |
| 3 | [`find_minutes_files`](steps/find_minutes_files/) | Crawls each minutes page (following year links one level deep), collecting links to minutes PDFs with a deterministic `meeting_date` where derivable. |
| 4 | [`transform_minutes_files`](steps/transform_minutes_files/) | Downloads each PDF and extracts prose text — marker-pdf first, pdfplumber fallback. |
| 5 | [`extract_motions`](steps/extract_motions/) | One LLM request per document (via the shared `src/lib/llm_extract.py`) returning `{"motions": [{motion_text, proposer, seconder, status_label}, …], "meeting_date": <LLM guess or null>}`; the LLM's date is carried forward untouched as `stated_date`. |
| 6 | [`resolve_meeting_date`](steps/resolve_meeting_date/) | Deterministic per-document date resolution: a full date from `find_minutes_files`, else an LLM `stated_date` that parses to a full day, else a `<day> <Month>` from the document header combined with the `<Month> <YYYY>` in the link text (month cross-checked; the URL folder is never a year source). Unresolvable + has motions → `UnresolvedMeetingDate`. |
| 7 | [`canonicalize_motions`](steps/canonicalize_motions/) | Deterministic fan-in: maps status to the closed set, resolves the composite id `<slug>/<meeting_date>/m<NNN>`, dedupes, classifies meeting type. |
| 8 | [`export_motions`](steps/export_motions/) | Groups by authority and writes `public/motions/<slug>.json` plus `public/motions/index.json`. |

## Committed inputs (source of truth)

- [`steps/find_local_authorities/local_authorities.json`](steps/find_local_authorities/local_authorities.json) — the 31-authority name list. Names must match the CSO output exactly; a name missing there is **fatal**.
- [`steps/find_meeting_minutes_pages/override.json`](steps/find_meeting_minutes_pages/override.json) — curated `minutes_page_url` per body/district; wins over crawling, no HTTP. **MVP caveat:** the Meath URLs are placeholders — verify/fill them before the first real run (see the override file's commit note).

## Running it

Run from the repo root, passing the pipeline directory explicitly (the shared runner's pipeline directory defaults to your current working directory):

```bash
# Full pipeline
uv run python pipelines/minutes_pipeline/process.py pipelines/minutes_pipeline --force --stop-on-error

# Meath only (scope to one authority)
uv run python pipelines/minutes_pipeline/process.py pipelines/minutes_pipeline --public-body 1511 --force --stop-on-error
```

`find_meeting_minutes_pages`, `find_minutes_files`, `transform_minutes_files` and `extract_motions` make live HTTP / LLM calls; `extract_motions` requires the `MOTIONS_LLM_*` env config (see `src/lib/llm_extract.py`). Run the test suite with `uv run pytest pipelines/minutes_pipeline/tests -q`.

## Motion status closed set

`carried`, `carried_as_amended`, `not_carried`, `withdrawn`, `deferred`, `not_recorded`.

## Fail-closed error policy

Aligns with the repo-wide data-handling principle — never guess, silently null, or silently drop:

- Unmappable `status_label` → `not_recorded` **plus** an `errors.json` entry.
- Unresolvable `meeting_date` on a document that carried motions → `UnresolvedMeetingDate` in `resolve_meeting_date/errors.json` (motion still excluded downstream — no stable id).
- A document that produced no motions → `NoMotionsExtracted` in `canonicalize_motions/errors.json` (no `MissingMeetingDate` noise for motion-less scans).
- Failed/unparseable LLM response → whole document gets `motions: null` **plus** a per-document error (no partial guess).
- A committed authority name missing from the CSO output → **fatal**, not a silent drop.

A run with unresolved reconstruction errors requires human review before publication. The MVP public output under `public/motions/` must be reviewed before running `scripts/publish_pages.sh`.
