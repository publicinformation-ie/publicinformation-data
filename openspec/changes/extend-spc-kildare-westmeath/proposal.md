# Proposal

## Why

The SPC pipeline has only ever read one committee: Meath's six minutes PDFs, all with a text layer. Adding two more councils shows whether "adding a committee is a configuration edit" holds up against real formats. A survey of the candidates (2025–2026) found that most councils publish scanned minutes: 10 of the 11 new files have no text layer. Kildare's six come from a PaperCut copier, and four of Westmeath's five come from a Canon scanner. As specified today, the pipeline publishes almost none of them, because `spc-minutes-ingestion` forbids OCR.

## What Changes

- **New committees.** Kildare County Council's Transport, Mobility and Open Spaces SPC (committee ID `kildare/transport-mobility-open-spaces`) and Westmeath County Council's Planning, Regeneration & Transportation SPC. The published committee name is the one printed on the minutes. Kildare's web page still uses an older name ("Transportation, Safety and Emergency Services"), which is kept only as a note in the config.
- **Several pages per committee.** A committee can list more than one minutes page. Kildare publishes minutes on a separate page for each year (`…/2025/Minutes/`, `…/2026/Minutes/`). There is still no crawling: every page is declared in committed config.
- **Year window.** A committee can limit discovery to given years. This change sets 2025–2026 for the new committees. Westmeath's single page lists minutes back to 2016. The year comes from the link text, and the existing check against the printed header date still applies.
- **OCR for scanned minutes. BREAKING (spec):** the rule "The pipeline SHALL NOT run OCR" is replaced. A PDF with no text layer on a page is read with the repo's existing local engine: tesseract via `pytesseract`, pages rendered with `pymupdf`, as in `minutes_pipeline/ocr_minutes_files`. The SPC steps need each word with its position on the page, so the call returns words with their boxes rather than plain text. A file with a text layer on some pages and scans on others is read page by page.
- **OCR fails closed.** A file that yields no text at all, or a page whose OCR confidence is below a set threshold, produces an error and no meeting. Low-confidence text is never published. A page that is legitimately blank or holds only signatures is skipped only when a committed, reviewed override names that file and page.
- **Reproducible OCR in tests.** For each scanned fixture, the OCR word output is committed alongside its PDF and sha256, so CI and the byte-for-byte render snapshot run without tesseract installed. Each meeting records the engine and version that read it.
- **Text provenance is published.** Each meeting record states where its text came from (`text_layer` or `ocr`, plus the engine version). The word-preservation check then proves the render matches that text. For OCR meetings that means "verbatim to the OCR", and the dataset README says so. Adding the field is a minor schema version bump.
- **New header and attendance layouts.** Kildare prints "Attendees / Also Present / Guest / Apologies / Not Present" in a two-column table. Westmeath prints "Members Present / Sectoral Reps / Officials Present / External Presenters / Apologies". Items are printed as "Item 1 – …" or "Item 1: …". The parser maps each council's labels to the existing attendance categories and statuses. A label it does not know is an error, not a guess.
- **Register entries and a councillor roster.** New people go into `reference/people.json`. `minutes_pipeline/reference/councillors.csv` is generated from the Meath motions data and holds no Kildare or Westmeath councillors. A committed SPC councillor roster is therefore added for those councils. It uses the same `<council>/<name-slug>` ID form, and a councillor ID must exist in either file. Where both files list a councillor, the IDs must agree.
- **Excluded councils.** Wicklow (Sucuri JavaScript challenge) and Monaghan (Cloudflare 403) block non-browser clients. They are out of scope, and the pipeline will not circumvent bot protection.

## Capabilities

### New Capabilities

### Modified Capabilities
- `spc-minutes-ingestion`: committees may declare several pages and a year window; the shipped committee list includes Kildare and Westmeath; a PDF without a text layer is OCR'd with tesseract, with fail-closed confidence rules, instead of being rejected; the header date requirement covers the new header forms.
- `spc-minutes-rendering`: page furniture, item headings and attendance blocks cover the Kildare and Westmeath layouts; the word-preservation check runs against OCR words where the meeting was OCR'd.
- `spc-attendance`: printed category labels from the new layouts map to the existing categories, including Kildare's "Not Present" and "Guest" rows; an unknown label is an error. A councillor ID may come from the SPC councillor roster as well as `councillors.csv`.
- `spc-meetings-dataset`: each meeting record carries its text source and OCR engine version; minor version bump; the README states what "verbatim" means for OCR'd minutes.

## Impact

- `pipelines/spc_pipeline/steps/find_spc_minutes_files/`: `committees.json` schema (`page_urls`, `years`), discovery and tests.
- `pipelines/spc_pipeline/steps/fetch_spc_minutes/`: an OCR path alongside the text layer; mixed PDFs handled page by page; `NoTextLayer` replaced by OCR errors.
- `parse_meeting_header`, `resolve_attendees`, `render_spc_minutes`: new layouts; `reference/people.json` entries.
- `extract_spc_items`: no code change expected. Running it for 11 new meetings is a paid step that needs the user's permission for that run (`CLAUDE.md`). New decisions are registered in `decision_ids.json` as usual.
- `scripts/transform_spc_meetings.py`, `public/schemas/spc-meetings.schema.json`, a new `public/v<next minor>/spc-meetings/`, `public/CHANGELOG.md`, `DATA_SOURCES.md` (Kildare and Westmeath minutes).
- Dependencies: `pytesseract` and `pymupdf` added to `pipelines/spc_pipeline/requirements.txt`, pinned as in `document_pipeline`. The `tesseract` binary is needed only for live runs, and is not installed on the current development machine (`brew install tesseract`).
- Tests: about 11 new PDF fixtures, with committed OCR outputs and sha256 manifest entries.
