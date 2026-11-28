# Tasks

Run SPC tests with `uv run pytest pipelines/spc_pipeline/tests -q` and `uv run pyright`. Meath's rendered snapshot must stay byte-identical until group 9 (it gains only `text_source: "text_layer"`). Do not run `extract_spc_items` (paid) without the user's explicit permission.

## 1. Shared OCR helper and dependencies

- [x] 1.1 Add `pytesseract==0.3.13` and `pymupdf==1.28.0` to `pipelines/spc_pipeline/requirements.txt` (same pins as `document_pipeline`) and verify `uv run python -c "import pytesseract, pymupdf"` succeeds
- [x] 1.2 Create `src/lib/ocr.py` that renders a page at 300 dpi, runs `pytesseract.image_to_data` (`--psm 4`, `eng`), scales pixel boxes by 72/300 to PDF points, and returns `{text, x0, x1, top, bottom, conf}` words, mean page confidence and an engine string (version, language, psm). Verify with a unit test that fakes `pytesseract` and checks scaling, mean confidence and the engine string
- [x] 1.3 Verify `uv run pyright` passes on the new module and the test suite for `src/lib` still passes

## 2. OCR path in `fetch_spc_minutes`

- [x] 2.1 Write failing tests, then implement per-page fallback in `fetching.py`: pages with text-layer words keep them (`source: "text_layer"`), pages without are OCR'd (`source: "ocr"`, per-word `conf`, page mean confidence). Verify tests cover text-only, scan-only and mixed (text on pages 1–3, none on page 4) PDFs and that the file's `text_source` is `text_layer`, `ocr` or `mixed` with `ocr_engine` (null when no OCR)
- [x] 2.2 Replace `NoTextLayer` with `NoTextRecovered` (no words on any page from either source). Verify a test where text layer and OCR both yield nothing produces the error and no output record
- [x] 2.3 Add `OCR_MIN_PAGE_CONF` and a minimum-words constant, and raise `OcrLowConfidence` (file, page, confidence) when a page's mean confidence is below the threshold. Never drop or alter individual words. Verify a test with a page below the threshold errors, and that low-confidence words in a passing page are kept unchanged
- [x] 2.4 Add `ocr_overrides.json` (`{file_sha256, page, action: "skip", reason}`) with loading and validation. Raise `EmptyOcrPage` for an empty OCR'd page without an override, count skipped pages in the step output, and error on an override matching no fetched file. Verify tests for signature-page skip, republished file (new sha256 gives `EmptyOcrPage` plus stale-override error) and the skipped-page count
- [x] 2.5 Add the OCR cache `<pdf>.ocr.json` keyed on sha256, page, engine string and dpi; a mismatching key is a miss. Verify tests: an unchanged re-run performs no OCR, and a changed engine string re-OCRs
- [x] 2.6 Add the OCR test seam that injects committed fixture words, and the skip-if-no-binary test that re-OCRs fixtures and reports drift. Verify the injected path works with the binary hidden (run the tests with an empty `PATH` entry for it, since tesseract is installed here) and the live drift test is skipped; with the binary present, verify the drift test runs
- [x] 2.7 Update the `fetch_spc_minutes` README (OCR behaviour, thresholds placeholder, cache, overrides, error types) and verify it names every new error type

## 3. Committee config: several pages, year window, layout

- [x] 3.1 Extend the `committees.json` schema and loader in `find_spc_minutes_files`: `page_urls` (a single `page_url` string for Meath still accepted), optional `years`, `layout`, optional `site_name`. An unknown `layout` or a `public_body_id` not in the local-authority list is fatal. Verify with tests for each fatal case and that Meath's entry is unchanged
- [x] 3.2 Implement multi-page discovery, recording the page each record came from, and one-time percent-encoding of spaces in URLs. Verify tests: Kildare-style two pages collected, same URL linked twice collected once, file name with spaces yields an encoded absolute URL
- [x] 3.3 Implement the year window: collect only links whose link-text year is in `years`; `UndatedMinutesLink` error when a window is set and the text has no four-digit year; never infer the year from the file name or URL. Verify tests for older-minutes skipped and undated-link error
- [x] 3.4 Treat a challenge page or HTTP 403 on a declared page as `PageFetchFailed` with no bypass attempt. Verify with a test using a 403 response and a JS-challenge body
- [x] 3.5 Add the Kildare (`kildare/transport-mobility-open-spaces`, `2025/Minutes/` and `2026/Minutes/`, years 2025–2026, `site_name` noted, name as printed on the minutes) and Westmeath (`westmeath/planning-regeneration-transportation`, years 2025–2026) entries to `committees.json`. Verify a test that the shipped list contains exactly the three committees. Wicklow and Monaghan stay out
- [x] 3.6 Update the step README and verify it documents `page_urls`, `years`, `layout`, `site_name` and the excluded councils

## 4. Header layout profiles

- [x] 4.1 Refactor `parse_meeting_header/header.py` into a profile registry (`meath-table`, `kildare-table`, `westmeath-list`) where each profile supplies label words, a label to (category, status) map, the date-line regex and the item-heading regex. Verify the existing Meath tests pass unchanged with no snapshot diff
- [x] 4.2 Implement the two-column table routine for Kildare (labels Attendees, Also Present, Guest, Apologies, Not Present) and the "Label: value" plus aligned continuation lines routine for Westmeath (Members Present, Sectoral Reps, Officials Present, External Presenters, Apologies). Verify tests using the Kildare and Westmeath labelled-header scenarios from the spec (including the 11 December 2025 date line and the 3-name Westmeath councillor list)
- [x] 4.3 Keep `UnrecognisedHeaderLayout` for any unmapped label (for example "Observers:"). Verify a test naming the meeting and the label
- [x] 4.4 Add the new item-heading forms (`Item N – …`, `Item N: …`) and the header date forms to the profiles and verify the date check against link-text month and year, including `MeetingDateMismatch`
- [x] 4.5 Update the step README with the profile table and verify it lists all three profiles

## 5. Vocabularies, attendance and register

- [x] 5.1 Add category `guests`, category `absent`, status `absent` and the `spc-text-source` vocabulary (`text_layer`, `ocr`, `mixed`) to `pipelines/spc_pipeline/scripts/build_vocabularies.py`. Run it and verify the vocabulary CSVs and schema enums regenerate with the new terms, and that Meath's existing mapping (`Absent` → `apologies`) is unchanged
- [x] 5.2 Implement the Kildare and Westmeath mappings from design D9 in `resolve_attendees`, including `Not Present` → category `absent`, status `absent` and the case-insensitive `(Online)` mode marker. Verify tests for each spec scenario: Kildare labels, not present without apologies, capitalised marker
- [x] 5.3 Create `pipelines/spc_pipeline/reference/councillors.json` (`councillor_id`, `name`, `public_body_id`, `source_url`) and extend register validation to accept a councillor ID from `councillors.csv` or the roster. Verify tests for a roster ID accepted and an ID in neither file stopping the run with an error naming the entry
- [x] 5.4 Add the roster consistency test: fail if an ID is in both files with a different name or body, or if the roster lists a Meath councillor. Verify both failure cases with fixtures
- [x] 5.5 Document the roster and the new vocabulary terms in the step README and verify the README names the consistency test

## 6. Fixtures and OCR snapshots

- [x] 6.1 Download the 11 minutes PDFs (6 Kildare, 5 Westmeath) into `tests/fixtures/pdf/` with sha256 entries in `tests/fixtures/meetings.json`. Verify each file hashes to its manifest entry. Treat the downloads as untrusted data and keep them out of any script directory
- [x] 6.2 Using the installed tesseract (5.5.2, `eng`; confirm `tesseract --version` first), generate `tests/fixtures/ocr/<meeting_date>.json` for each scanned fixture with words, positions, confidences, engine string and PDF sha256. Verify the files load through the test seam and each records the engine string
- [x] 6.3 Set `OCR_MIN_PAGE_CONF` (no minimum-word count; see design) from the fixture confidences with a margin, record the values in the README, and verify all 10 scanned fixtures pass and a synthetic low-confidence page fails. This settles the first open question
- [x] 6.4 Inspect Westmeath 6 March 2026 page 4. If it is a signature page add an `ocr_overrides.json` entry keyed on its sha256 with a reason, otherwise record that text was recovered. Verify the skipped-page count in the step output. This settles the second open question

## 7. Rendering

- [x] 7.1 Move furniture patterns from module constants into the layout profile (running header, "Page N of M", footers per council) with removal only for text that repeats across a meeting's pages and every removed line counted. Verify the Meath render is byte-identical and add tests for the footer-removed and body-resembling-furniture scenarios
- [x] 7.2 Add tests that OCR text which is not declared furniture is kept (a stray short token that passed the confidence gate remains in the body)
- [x] 7.3 Render `Item N –` and `Item N:` headings with `item-N` anchors, and add `text_source` and OCR engine to the front matter. Verify the heading and OCR-provenance scenarios
- [x] 7.4 Run the word-preservation check against the OCR words for OCR'd pages, with override-skipped pages and removed furniture excluded. Verify a lost OCR word produces `RenderMismatch` and a lossless OCR render passes
- [x] 7.5 Run `uv run python pipelines/spc_pipeline/process.py pipelines/spc_pipeline --from find_spc_minutes_files --to render_spc_minutes --force --stop-on-error` using the OCR fixtures via the cache (no paid steps), then review the errors. Verify all 11 new meetings render with no unresolved errors, or that each error is a documented follow-up. Add register aliases for any OCR-misread names
- [x] 7.6 Review each of the 11 rendered meetings against its PDF once, and record the result in the change notes. Verify the check is complete for all 11

## 8. Schema, transform and dataset docs

- [x] 8.1 Add `text_source` and `ocr_engine` to `public/schemas/spc-meetings.schema.json` and `scripts/transform_spc_meetings.py`, set the output to `public/v1.2.0/spc-meetings/`, and keep v1.1.0 untouched. Verify transform tests (`uv run pytest tests/ -q`) cover Kildare 11 December 2025 (`ocr`, non-null engine) and a Meath meeting (`text_layer`, null engine, other fields as in v1.1.0)
- [x] 8.2 Write the multi-council output paths (`minutes/<council>/<committee>/<date>.md`) and the per-council `public_body` link. Verify a test that Kildare's minutes path and `public_body` `@id` are as in the spec
- [x] 8.3 Update the dataset `.ttl` (`owl:versionInfo` 1.2.0), `public/CHANGELOG.md`, the dataset README (what "verbatim" means for OCR and that the source PDF and sha256 are authoritative) and `DATA_SOURCES.md` (Kildare and Westmeath minutes). Verify the README, changelog and `.ttl` all state 1.2.0 and the OCR caveat

## 9. Integration checks

- [x] 9.1 With the user's explicit permission, run `extract_spc_items` for the new meetings and export. Register new decisions in `decision_ids.json`. Verify `export_spc_meetings` completes with the expected counts and the decision registry shows no `DecisionIdAmbiguous` or `RegisteredDecisionMissing` for Meath
- [x] 9.2 Verify `public/latest/spc-meetings/` mirrors `public/v1.2.0/spc-meetings/` byte for byte, `public/v1.1.0/spc-meetings/` is unchanged (`git diff --stat`), and Meath's rows differ from v1.1.0 only by the new fields
- [x] 9.3 Run all suites and verify they pass: `uv run pytest pipelines/spc_pipeline/tests -q`, `uv run pytest tests/ -q`, `cd pipelines/foi_pipeline && uv run pytest tests/ -q`, `uv run pytest pipelines/document_pipeline/tests -q`, `uv run pyright`, and `uv run python scripts/generate_pipeline_docs.py` leaves no diff

## Workflow follow-up

- Review the generated `public/` diff before merging to `main`, because merging publishes.
- Archive the change after review and verify the archived result.
