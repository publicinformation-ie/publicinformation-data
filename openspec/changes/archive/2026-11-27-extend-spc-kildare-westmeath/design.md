# Design

## Context

See proposal.md for why. The current state that shapes the approach:

- `fetch_spc_minutes/fetching.py` uses pdfplumber to emit, for each page, `{page, width, height, words: [{text, x0, x1, top, bottom}]}` in PDF points with the origin at the top left. A file with no words on any page raises `NoTextLayer`. `parse_meeting_header`, `resolve_attendees` and `render_spc_minutes` all read this word structure, and their layout rules use point-based gaps (for example, a label column ends where a gap of more than 20 pt starts).
- `parse_meeting_header/header.py` is built for Meath's layout. The label words (`Attendees`, `Absent`, `(Officials):`, `Presenters`, …) and the regexes that turn labels into categories are hard-coded constants. An unrecognised layout raises `UnrecognisedHeaderLayout`.
- `minutes_pipeline/ocr_minutes_files` already OCRs scanned minutes: it renders pages with `pymupdf` at about 300 dpi and runs `pytesseract.image_to_string`, which returns plain text only. Its pins are `pymupdf==1.28.0` and `pytesseract==0.3.13`. The `tesseract` binary is installed on the current development machine (tesseract 5.5.2, `eng` data), but CI does not have it.
- `minutes_pipeline/reference/councillors.csv` is generated from the Meath motions CSV by `build_councillor_reference.py`, so it holds only Meath councillors. `resolve_attendees` validates every `councillor` register entry against it.
- Test fixtures: the six Meath PDFs live under `tests/fixtures/pdf/`, listed in `tests/fixtures/meetings.json` with each file's sha256. The rendered Markdown is compared byte for byte with `public/latest/spc-meetings/minutes/`.
- Survey of 2025–2026 sources:
  - Kildare: six PDFs, all scanned (PaperCut). They sit on two pages, `…/2025/Minutes/` and `…/2026/Minutes/`, and their file names contain spaces.
  - Westmeath: five PDFs, all on one page that runs back to 2016. Four are scanned (Canon iR-ADV). The fifth, 6 March 2026, has a text layer on pages 1–3, but page 4 has no text.
  - The scans are clean, single-column 300-dpi-class printouts.

## Goals / Non-Goals

**Goals:**
- One word structure for every downstream step, whether a page's words came from the text layer or from OCR. The parser, resolver, renderer and word check stay unaware of where the words came from.
- OCR output that can be reproduced in CI without tesseract, and pipeline runs that never OCR the same bytes twice under the same settings.
- Committee layout differences expressed as committed data where they are vocabulary, such as labels and furniture patterns, and as code only where they are geometry.

**Non-Goals:**
- Generic header layout inference. Each council's layout is declared, and an unseen layout is an error.
- OCR of handwriting, tables or multi-column scans.
- Crawling or link-following beyond the declared pages.
- Changing Meath's published records, apart from the new provenance field.
- Fetching from sites behind bot protection.

## Decisions

**D1. OCR inside `fetch_spc_minutes`, per page, emitting the existing word structure.** For each page with no text-layer words, render it with `pymupdf` at 300 dpi and run `pytesseract.image_to_data`. Pixel coordinates are scaled by 72/300 to PDF points, so the existing point-based layout thresholds keep working. Each page records `source: "text_layer" | "ocr"`. Each OCR word keeps its `conf` and the `line` number Tesseract gave its text line, and each page keeps its mean confidence. Downstream steps group OCR words into lines by `line`, not by `top`: a scan is rarely level, and a `top` tolerance split one printed line into several. The meeting's `text_source` is `text_layer`, `ocr` or `mixed`, plus the engine string (tesseract version, language and page-segmentation mode).
*Alternatives considered:*
- Reuse `ocr_minutes_files` as a cross-pipeline step: it emits plain text with no positions, and it works per file, not per page.
- A separate `ocr_spc_minutes` step: this would split one concern (getting a page's words) across two steps, and it would need a pass-through for text-layer files anyway.

**D2. Shared OCR helper in `src/lib/ocr.py`.** The helper already existed (added for `document_pipeline`, psm 3, pixel boxes). This change extends it with `engine_string`, `words_in_points` (point-scaled words carrying Tesseract's own line number) and `ocr_page_words`; `document_pipeline` keeps psm 3 and its behaviour. The SPC pipeline passes `--psm 4` (eng, 300 dpi). `ocr_minutes_files` can adopt it later, but this change does not move that step.
*Alternative:* copying the code into the SPC step. Rejected so that one place defines how this repo runs tesseract.

**D3. OCR cache keyed on content and settings.** OCR output is cached next to the PDF cache as `<pdf>.ocr.json`. The key is the PDF sha256, the page number, the engine string and the dpi. A cache entry that does not match the key is a cache miss, never stale data reused.

**D4. Committed OCR fixtures for tests.** For each scanned fixture PDF, `tests/fixtures/ocr/<meeting_date>.json` holds the words, positions and confidences tesseract produced, with the engine string and the PDF's sha256. Tests inject these through the same seam as the cache, so CI never calls tesseract and the byte-for-byte render snapshot stays deterministic. A test that runs only when the binary is present (skipped otherwise) re-OCRs the fixtures and reports any drift against the engine string. A tesseract upgrade is a deliberate fixture refresh with a reviewable `public/` diff.

**D5. Confidence gate per page.** A page whose mean word confidence is below `OCR_MIN_PAGE_CONF` fails, and so does a file with no words on any page. Either produces an `OcrLowConfidence` or `NoTextRecovered` error, and no meeting. Both thresholds are committed constants in the step, set from the 10 scanned fixtures so that all of them pass with a margin, and the value is recorded in the README. No individual word is dropped for low confidence: dropping a word would quietly rewrite the text, which the word check could no longer detect. A page with no text is allowed only through D6.

**D6. Reviewed page overrides.** `fetch_spc_minutes/ocr_overrides.json` lists `{file_sha256, page, action: "skip", reason}` for pages that are legitimately blank or signature-only. An override applies only to a page that would fail the gate: a page with no words, or a blank sheet whose speckle OCR reads as junk words (Westmeath 28 November 2025, page 4: 3 words, mean confidence 13.7). The junk words are dropped from the record and counted in `skipped_word_count`; a page that passes the gate is never skipped. Westmeath 6 March 2026 page 4 turned out to hold real text, so it needs no override. The entry is keyed on sha256, so a republished file must be reviewed again. The number of skipped pages is reported. An override that no longer matches any fetched file is an error, as with `override.json`'s stale-target check.

**D7. `committees.json` gains `page_urls`, `years` and `layout`.**
- `page_urls` replaces `page_url`. A single string is still accepted for Meath, so Meath's config is unchanged. Each discovered record keeps the page it was found on.
- `years` is optional. When it is set, the four-digit year from the link text must be in the list. A link with no year in its text, while a window is set, gives an `UndatedMinutesLink` error and no record: the year is never inferred from the file name or the URL.
- `layout` names a header-layout profile.
- `site_name` is optional and holds the page's own name for the committee (for Kildare, "Transportation, Safety and Emergency Services"). It is kept as provenance only.

URLs with spaces are percent-encoded once when discovered.

**D8. Header layout profiles: labels as data, geometry as code.** `parse_meeting_header` gets a small registry of layout profiles: `meath-table` (the current code), `kildare-table` and `westmeath-list`. A profile supplies:
- the label words that start a label row;
- a mapping from label text to `(category, status)`;
- the regex that finds the date line;
- the regex for item headings (`^\d+\.\d+`, `^Item \d+ [–-]`, `^Item \d+:`).

Two geometry routines cover all three councils. One handles Meath's two-column label/value table. The other handles "Label: value" rows followed by continuation lines that line up with the value column; reading the real PDFs showed that Kildare and Westmeath print the same geometry, so both use it and differ only in profile data (labels, date line, one person per line or per title). An unmapped label is still `UnrecognisedHeaderLayout`.
*Alternative:* inferring the layout from the document. Rejected as guessing, which goes against the repo's data-handling rule.

**D9. Kildare's "Not Present" and "Guest" get their own vocabulary terms.** The new labels map as follows.

| Council | Label | Category | Status |
|---|---|---|---|
| Kildare | Attendees | `councillors` | `present` |
| Kildare | Also Present | `officials` | `present` |
| Kildare | Guest | new category `guests` | `present` |
| Kildare | Apologies | `apologies` | `apologies` |
| Kildare | Not Present | new category `absent` | new status `absent` |
| Kildare | Also (no "Present") | `officials` | `present` |
| Kildare | Online | `councillors`, mode `remote` | `present` |
| Westmeath | Members Present | `councillors` | `present` |
| Westmeath | Sectoral Reps | `sectoral_representatives` | `present` |
| Westmeath | Officials Present | `officials` | `present` |
| Westmeath | External Presenters | `presenters` | `present` |
| Westmeath | Apologies | `apologies` | `apologies` |

Kildare prints apologies and non-attendance separately. Folding "Not Present" into `apologies` would say something the minutes do not. Meath's existing mapping (`Absent` → `apologies`) is unchanged, so no published Meath row moves. The new terms are added to `scripts/build_vocabularies.py`, so the vocabulary CSVs and the schema enums are regenerated.

**D10. SPC councillor roster.** `pipelines/spc_pipeline/reference/councillors.json` lists `{councillor_id, name, public_body_id, source_url}` for Kildare and Westmeath councillors who appear in the minutes. The `source_url` is the council's elected-members page. Register validation accepts a `councillor` entry whose ID is in `councillors.csv` or in this roster. A test fails if the two files share an ID with a different name or body, or if the roster lists a Meath councillor (that council is owned by `councillors.csv`). When motions later cover a new council, its generated IDs must match the roster's, which the same test enforces.

**D11. Furniture and item rules per committee.** Furniture patterns (running headers, "Page N of M", footers) move from module constants into the layout profile. Removal still matches only lines that repeat as furniture across a meeting's pages, and every removal is counted. Scanner speckle that OCR reads as stray punctuation is not special-cased. If it fails the confidence gate it stops the meeting; if it passes, it is source text, and it stays.

**D12. Schema and vocabulary bump to the next minor version.**
- Each meeting record gains `text_source` (enum `text_layer`, `ocr`, `mixed`) and `ocr_engine` (a string, or null when the text came from the text layer).
- The vocabularies gain the status `absent` and the categories `guests` and `absent`. A new `spc-text-source` vocabulary is added for `text_source`.
- The dataset is published at `public/v1.2.0/spc-meetings/`. The changes are additive, so it is a minor bump.
- The dataset README says that for `ocr` and `mixed` meetings, "verbatim" means verbatim to the OCR text, and that the source PDF is authoritative.

## Risks / Trade-offs

- [OCR misreads a word with high confidence: the word check passes, and the published text is wrong] → The provenance field and the README make the OCR caveat explicit, and the source URL and sha256 are always published. Review the 11 rendered meetings against their PDFs once before the first publish.
- [Names misread by OCR fail to resolve] → Unresolved names already withhold only that meeting's attendance. The fix is a register alias, as for Meath, and is reviewable.
- [Decision quotes drift when tesseract is upgraded] → The existing decision ID registry flags drift as `DecisionIdAmbiguous` or `RegisteredDecisionMissing` instead of renumbering. Fixture refreshes are deliberate (D4).
- [A council re-uploads a file with new bytes] → The new sha256 misses the OCR cache and any override. That is intended, and the result is re-reviewed.
- [Layout profiles grow with every council] → Accepted. The README already says new layouts may need parser changes, and profiles keep each one small and data-led.
- [The roster duplicates data the motions pipeline may later own] → The test in D10 keeps the two consistent. Once motions cover a council, its roster rows can be removed.
- [CPU cost of OCR, roughly 50 pages] → Run once per sha256, then cached (D3).

## Migration Plan

1. Land the D1–D6 OCR path with Meath unchanged. Meath's render snapshot must not change. Meath meetings gain only `text_source: "text_layer"`.
2. Add the committees, profiles, roster and register entries. Then run `--to render_spc_minutes` (unpaid) and review the errors.
3. With the user's explicit permission for that run, run `extract_spc_items` for the new meetings, then export v1.2.0.
4. Rollback: revert the commits. v1.1.0 stays published and unchanged.

## Open Questions

None open. Settled during implementation: `OCR_MIN_PAGE_CONF` is 80.0 (real pages score 90.0 to 95.7; no per-page minimum word count, because a signature page would fail it), and Westmeath 6 March 2026 page 4 holds real text and needs no override.
