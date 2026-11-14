# Gold set for the extractor bake-off (PROVISIONAL)

**Status: PROVISIONAL. Needs a user spot-check before Task 5 Step 7 scores against it.**

Each `<sha256>.json` holds only `{"columns": [...], "rows": [...]}`: the first 15 data rows plus the last 5 data rows of the file (no duplicates; files with fewer than 20 rows hold all of them). Cell text is as printed, a cell wrapped over several lines (or several paragraphs, or across a page break) joined with one space, repeated page headers and title/footer lines excluded. Column names are the first-page header with multi-line headers joined by a space.

## Method

- Row and column boundaries were decided by looking at the rendered page images (110 dpi PNGs, kept outside the repo).
- Characters were taken from the PDF text layer by cropping each cell's rectangle (column x-bounds and row y-bounds read off the image) with pymupdf word boxes. No table extractor (pdfplumber, camelot, pymupdf find_tables, docling, Mistral) was used to seed any gold file, so no candidate scores 100% by construction.
- Per page, every word inside the table region was checked to land in exactly one cell (word-count reconciliation), so no text was dropped.
- Page images were viewed for the first and last transcribed page of each file and for any page whose structure was unusual (header repeats, split rows, rotated pages); the middle pages were reconciled by word counts and row-number sequences, not individually eyeballed. Hence the spot-check request.

## Files

### 41fa00e9e9549b3f3ee5a12ba3fd84e2510091545eed3ff6f56704e8a6393ce6
- public body id: 1655  (stratum: width_shift)
- file_url: https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-q4-disclosure-log-2018.pdf
- pages transcribed: 1-5, 19-20
- rows in gold: 20
- notes / uncertainty: Header on p19-20 reads 'Requestor'/'received'; columns use page-1 wording. Row numbers skip (e.g. 208, 210, 212, 214) as printed. Last page holds 1 row, so last-5 spans p19-20.

### 9c4f12d2901c31cc12268969145a17a736aa9db000916f087de2938000036d86
- public body id: 1655  (stratum: width_shift)
- file_url: https://about.rte.ie/wp-content/uploads/2020/01/RTE-FOI-DISCLOSURE-LOG-Q4.pdf
- pages transcribed: 1-5, 17-18
- rows in gold: 20
- notes / uncertainty: First-page column wording; row 126 request cell has two stacked paragraphs joined with one space.

### 6ab587f28c8be32d25d4a6a4f6df056d2f19138cc331c8a14f5b837e423dcb7a
- public body id: 1295  (stratum: width_shift)
- file_url: https://www.fingal.ie/sites/default/files/2019-03/FOI%20Disclosure%20Log%202016.pdf
- pages transcribed: 1-3, 34-35
- rows in gold: 20
- notes / uncertainty: Page is rotated 90 degrees (landscape). Columns kept in printed order: Date of Request, Reference Number, Description, Requester Category, Decision Type, Date of Release, Internal Review Decision, OIC Decision; the last two are empty in every transcribed row. Header cell text (bilingual, three stacked lines each) taken from text layer; first letter of Iarratais/iarrthora may be capital I vs lower-case l (indistinguishable in the font). Last page has 4 rows so last-5 includes FOI/2016/0169 from p34.

### e93ccc8d9b8cf36330287def1bc8c86728ecef24a6aad029f89553564f1c5c39
- public body id: 1295  (stratum: width_shift)
- file_url: https://www.fingal.ie/sites/default/files/2026-01/2024-foi-disclosure-log.pdf
- pages transcribed: 1-2, 10-11
- rows in gold: 20
- notes / uncertainty: Page 2 and later pages have no repeated header and start directly with data rows. Last page has 3 rows so last-5 includes 2 rows from p10. Column 7 (IR Decision) holds a date in FOI/2024/002 and the word Affirm in FOI/2024/189; last column (Appeal Decision) is empty in all rows. Reference numbers skip as printed.

### 4cb607b1be84d65652029fd161a9103cbf9ab2687981a49ee03d223674295e1b
- public body id: 1390  (stratum: split_words)
- file_url: https://www.hiqa.ie/sites/default/files/2018-01/FOI-Disclosure-Log-2015-Q3-4.pdf
- pages transcribed: 1-5, 9-10
- rows in gold: 20
- notes / uncertainty: Text layer bullet glyph is U+F0B7 (Symbol font private-use); gold uses the printed bullet U+2022. Bulleted items inside one cell are joined with one space. Every page repeats the header; rows never span pages. 32 data rows in total, last-5 are rows 28-32 (FOIR 065, 067, 069, 070 on p9 and FOIR 071 on p10). The Issued/Email footer lines under the table on p10 are excluded.

### 494a788e1104dd71dc3825d34d6b224e2f9f399021804bd251c97a71887dedb4
- public body id: 1293  (stratum: fragments)
- file_url: https://www.fspo.ie/documents/FOI-Disclosure-Log-2021.pdf
- pages transcribed: 1-2
- rows in gold: 9
- notes / uncertainty: Only 9 data rows exist in the whole file (fewer than 20), so all are included. The last row (Journalist, 21 October 2021) wraps over the page break; its Request cell is joined across p1-p2 with one space. Requests are n/a where printed n/a.

### ec6c89af73b7b4d767ef94f6937b1e000b739b16dc419a95146074d0f6eeeb79
- public body id: 1207  (stratum: header_repeat)
- file_url: https://assets.gov.ie/static/documents/foi-requests-log-july-to-september-2022.pdf
- pages transcribed: 1, 3
- rows in gold: 20
- notes / uncertainty: Layout has no ruling lines and cell text is bottom-aligned against the FOI reference, so row membership was assigned by reference position. A header row repeats mid-page 1 (between FOI-0274-2022 and FOI-0277-2022, and on each page) and is excluded. Wrapped URL in FOI-0291-2022 ends 'real- estate)' (line break after the hyphen, joined with one space). Last-5 rows come from p3; the file has 3 pages and the 15 first rows are all on p1. Page 2 was not transcribed.

### 569928ad2bebad897ad0f6b8faf5edbc8c9c8e14bdf820cf744ae46b75253921
- public body id: 1107  (stratum: clean_with_errors)
- file_url: https://www.charitiesregulator.ie/media/1932/foi-disclosure-log-2017.pdf
- pages transcribed: 1, 3
- rows in gold: 20
- notes / uncertainty: Printed oddities kept: row 14 date resolved '31/05/17:' (trailing colon); row 37 resolved date '21/11/2017' (4-digit year); row 36 date resolved is blank. A title banner row 'CHARITIES REGULATOR FOI REQUESTS 2017' above the header is not part of the columns. No repeated header on p2-p3. Page 2 not transcribed (15 first rows are all on p1). Last-5 = rows 36-40.

### 32096024434b85751cc11f79609208095006697ba508191fdf9901fb49555a9e
- public body id: 1437  (stratum: clean_no_errors)
- file_url: https://www.fiscalcouncil.ie/wp-content/uploads/2024/04/FOI-Disclosure-Log-2023.pdf
- pages transcribed: 1-2
- rows in gold: 7
- notes / uncertainty: Only 7 data rows in the whole file (fewer than 20), so all are included. No repeated header on p2 (just the page title). In the render the words 'the information', 'in the', 'on administrative', 'of the' look run together in a few Decision cells, but the text layer holds normal spaces; gold uses single spaces. Wrapped URLs are joined at the printed line break with one space (e.g. 'social- affairs/...').

### 4b31f0d260881723b7c085a4e0d0c6e2421e8ac6d776430028f470ad1f91ed71
- public body id: 1210  (stratum: fragments)
- file_url: https://assets.gov.ie/static/documents/66495939/202512_DRCDG_Q4_DisclosureLog.pdf
- pages transcribed: 1-8 (rows 1-15 start on p1-p4 and the 15th continues onto p5; last 5 rows are on p6-p8)
- rows in gold: 20
- notes / uncertainty: Rows split across page breaks (continuation text at the top of the next page, other cells empty) are one gold row, summary joined across the break with one space; the eFOI banner repeated on each page and the column header (p1 only) are excluded. 'DRCD-FOI-' / '2025-0140' wrap onto two lines in the ID cell and are joined with one space ('DRCD-FOI- 2025-0140'). 25 data rows in total; last-5 are FOI 2025-0109, 0108, 0107, 0106, 0105 (0106 spans p7-p8). Cells contain Irish-language text; accents taken from the text layer.

## Cross-cutting uncertainties

- Bullets in the HIQA file: the text layer holds U+F0B7 (Symbol font private-use glyph); gold uses the printed bullet U+2022. A candidate that emits U+F0B7 would be penalised by an exact match; decide in Step 7 whether to normalise.
- Wrapped URLs and hyphenated line breaks are joined with one space at the printed line break (e.g. 'social- affairs/...'), which is what a text-layer extractor produces; an extractor that re-joins hyphenated words would differ.
- Fingal 2016 headers: first letter of 'Iarratais'/'iarrthora' is indistinguishable between capital I and lower-case l in the font; the text layer reads it as lower-case l in some headers. Header text is not scored by the cell-accuracy metric as planned (data rows only).
- No cell was illegible; all text came from the text layer, so there are no OCR-style guesses.
