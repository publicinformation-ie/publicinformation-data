# Before/after on cached bodies

**Coverage: 13 of 129 bodies (in transform_disclosure_files output), 91 PDF files. NOT an all-bodies result.** The user did not approve the ~1,100-file re-download, so only bodies whose eligible files were all already in the DisclosureFileCache were run: 1112, 1157, 1177, 1259, 1552, 1653, 1655, 1711, 1741, 1747, 1774, 1806, 1882. No download occurred (cache stayed at 331 files before and after).

Method: `process.py --from transform_disclosure_files --to extract_disclosures_canonicalize_rows --public-body <id> --force --stop-on-error` per body, no `--allow-paid-ocr` (Mistral cache-only), nothing past canonicalize_rows. The two canonicalize steps rewrite their whole output on a scoped run, so they were then re-run once unscoped (`--from extract_disclosures_canonicalize --to extract_disclosures_canonicalize_rows --force`) over the accumulated 13-body upstream output. Before = on-disk step outputs of the main checkout (Nov 12-13 build; most of these are untracked built files). After = this worktree. Dedup was not run. Tables are from `before_after.py`.

Coverage: 13 bodies (1112, 1157, 1177, 1259, 1552, 1653, 1655, 1711, 1741, 1747, 1774, 1806, 1882); 91 PDF files. NOT an all-bodies result.

### Errors per error_type

| error_type | before | after | delta |
|---|---|---|---|
| TableStructureUnreliable | 0 | 18 | 18 |
| UnrecognizedDecisionStatus | 134 | 47 | -87 |
| UnrecognizedRequesterType | 600 | 1016 | 416 |

### Records per public_body_id (canonicalize_rows)

| public_body_id | before | after | delta |
|---|---|---|---|
| 1112 | 1086 | 525 | -561 |
| 1157 | 210 | 108 | -102 |
| 1177 | 43 | 0 | -43 |
| 1259 | 8 | 8 | 0 |
| 1552 | 79 | 0 | -79 |
| 1653 | 11 | 0 | -11 |
| 1655 | 1436 | 1529 | 93 |
| 1741 | 394 | 331 | -63 |
| 1774 | 67 | 82 | 15 |
| 1882 | 110 | 53 | -57 |
| TOTAL | 3444 | 2636 | -808 |

### PDF files per pdf_extractor

| pdf_extractor | before | after | delta |
|---|---|---|---|
| camelot_lattice | 0 | 39 | 39 |
| camelot_stream | 12 | 5 | -7 |
| mistral_cache | 0 | 1 | 1 |
| pdfplumber | 79 | 40 | -39 |
| pymupdf | 0 | 6 | 6 |

### Files that changed extractor (transitions)

| before | after | files |
|---|---|---|
| camelot_stream | camelot_lattice | 1 |
| camelot_stream | pdfplumber | 7 |
| pdfplumber | camelot_lattice | 38 |
| pdfplumber | camelot_stream | 1 |
| pdfplumber | mistral_cache | 1 |
| pdfplumber | pymupdf | 6 |

### Files that changed extractor (list)

| public_body_id | before | after | file_url |
|---|---|---|---|
| 1112 | pdfplumber | pymupdf | http://www.tusla.ie/uploads/content/2021_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | camelot_lattice | http://www.tusla.ie/uploads/content/2022_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | pymupdf | http://www.tusla.ie/uploads/content/2023_FOI_Disclosures_Log.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/RTE-Freedom-of-Information-Disclosure-Log-Q2-2019.pdf |
| 1655 | camelot_stream | pdfplumber | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-disclosure-log-2016.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-disclosure-log-2018-q1.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-disclosure-log-q1-2019.pdf |
| 1655 | camelot_stream | pdfplumber | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-disclosure-log-q3-2017.pdf |
| 1655 | camelot_stream | pdfplumber | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-q1-and-q2-disclosure-log-2017.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-q2-2018-disclosure-log.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-q3-disclosure-log-2018.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-q4-disclosure-log-2017.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/07/rte-freedom-of-information-q4-disclosure-log-2018.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2019/11/RTE-FOI-DISCLOSURE-LOG-Q3.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2020/01/RTE-FOI-DISCLOSURE-LOG-Q4-Carried-Over.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2020/01/RTE-FOI-DISCLOSURE-LOG-Q4.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2020/07/RTE-FOI-DISCLOSURE-LOG-Q1-2020.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2020/10/RTE-FOI-DISCLOSURE-LOG-Q2-2020.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2021/01/RTE-FOI-DISCLOSURE-LOG-Q3-2020.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2021/06/RTE-FOI-DISCLOSURE-LOG-Q1-2021.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2021/06/RTE-FOI-DISCLOSURE-LOG-Q4-2020-1.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2021/09/RTE-FOI-DISCLOSURE-LOG-Q2-2021.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2022/01/RTE-FOI-DISCLOSURE-LOG-Q3-2021.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2022/06/RTE-FOI-Disclosure-Log-Q1-2022.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2022/10/RTE-FOI-Disclosure-Log-Q2-2022.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2023/03/RTE-FOI-Disclosure-Log-Q3.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2023/05/RTE-FOI-Disclosure-Log-Q4.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2023/11/Q2-2023-Disclosure-Log-Publication.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2024/03/RTE-FOI-Disclosure-Log-Q3-2023.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2024/05/Q4-2023-Disclosure-Log-Publication.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2024/07/RTE-FOI-Decision-Log-Q1-2024.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2024/09/RTE-FOI-Disclosure-Log-Q2-2024.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2025/02/RTE-FOI-Disclosure-Log-Q3-2024.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2025/06/RTE-FOI-Disclosure-Log-Q4-2024.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2025/10/RTE-FOI-Disclosure-Log-Q1-2025.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2025/10/RTE-FOI-Disclosure-Log-Q2-2025.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2026/01/RTE-FOI-Decision-Log-Q3-2025.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2026/03/RTE-FOI-Decision-Log-Q4-2025.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2026/08/RTE-FOI-Decision-Log-Q1-2026.pdf |
| 1655 | pdfplumber | camelot_lattice | https://about.rte.ie/wp-content/uploads/2026/10/RTE-FOI-Decision-Log-Q2-2026.pdf |
| 1177 | pdfplumber | camelot_lattice | https://crawfordartgallery.ie/wp-content/uploads/20260527_FOI-LOG.pdf |
| 1552 | pdfplumber | mistral_cache | https://ncca.ie/media/4qffya5u/ncca-disclosure-log-2024.pdf |
| 1774 | pdfplumber | pymupdf | https://teagasc.ie/wp-content/uploads/Teagasc-FOI-Disclosure-Log-2025.pdf |
| 1157 | pdfplumber | camelot_lattice | https://www.audit.gov.ie/media/2dbjzig4/foi-disclosure-log-q2-2026.pdf |
| 1711 | camelot_stream | pdfplumber | https://www.skillnetireland.ie/uploads/attachments/FOI_Disclosure_Log_%281%29.pdf |
| 1741 | camelot_stream | pdfplumber | https://www.sportireland.ie/sites/default/files/media/document/2022-08/FOI%20Disclosure%20Log%202021.pdf |
| 1741 | camelot_stream | pdfplumber | https://www.sportireland.ie/sites/default/files/media/document/2022-08/Foi%20Disclosure%20Log%202020.pdf |
| 1747 | pdfplumber | camelot_stream | https://www.stjames.ie/media/FOI Request for Deceased Patient Records August 2026.pdf |
| 1112 | pdfplumber | pymupdf | https://www.tusla.ie/uploads/content/2021_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | camelot_lattice | https://www.tusla.ie/uploads/content/2022_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | pymupdf | https://www.tusla.ie/uploads/content/2023_FOI_Disclosures_Log.pdf |
| 1112 | camelot_stream | camelot_lattice | https://www.tusla.ie/uploads/content/2025_FOI_Disclosure_Log.pdf |
| 1112 | camelot_stream | pdfplumber | https://www.tusla.ie/uploads/content/2026_FOI_Disclosure_Log_-_Quarter_1.pdf |
| 1882 | pdfplumber | pymupdf | https://www.udaras.ie/assets/uploads/2020/06/05_FOI_Loga-Nochta-2017.pdf |

### TableStructureUnreliable per body

| public_body_id | files |
|---|---|
| 1112 | 6 |
| 1177 | 2 |
| 1552 | 1 |
| 1653 | 1 |
| 1655 | 1 |
| 1711 | 1 |
| 1741 | 1 |
| 1747 | 2 |
| 1882 | 3 |
| TOTAL | 18 |


## Explanations: error types

- TableStructureUnreliable 0 -> 18: new fail-closed gate; 18 error entries over 17 distinct files (the Tusla 2022 and 2023 files appear under both an http and an https URL). Per-file failed checks and false-positive candidates are in leftovers.md.
- UnrecognizedDecisionStatus 134 -> 47: columns are now aligned for 1655 (RTE) and 1157 (C&AG), so status cells hold statuses rather than description fragments (before: `Section 42(g) of`, `of Information`). 1157 96 -> 2. 1177 11 -> 0 and 1552 9 -> 0 because those files are now gated. 1655 rose 18 -> 45 only because many more RTE rows parse; the remaining values are reason text such as `Statutory Instrument SI 115 of 2000.` or glyph-split `R S efused.`.
- UnrecognizedRequesterType 600 -> 1016: exposure rather than regression of alignment. 1655 went 547 -> 1008 because RTE requester cells now land in the requester column (requester_type populated on 1527 of 1529 records, was 851 of 1436) and RTE writes `Journalist.` / `Member of the public.` with a trailing full stop that is not in the mapping (581 + 358 of the 1008). 1112 (Tusla) 44 -> 5. The fix is trailing-punctuation normalisation (leftovers.md), not extraction.

## Explanations: bodies whose record count moved

- 1112 (Tusla) 1086 -> 525 (-561): 6 of its 12 PDFs are now fail-closed (2022 and 2023 under both URLs, 2025 and 2026 Q1). The 2022 file (121 records, listed twice by its http/https URL pair) and 2023 (108, twice) were pdfplumber outputs that produced records before and are now gated on split_word_rate / fragment_share; this is data previously present and now absent (trade-off, and for 2022 a possible false positive: fragment_share 0.04, only split_word_rate 0.055 fails).
- 1157 (C&AG) 210 -> 108 (-102): pdfplumber (514 rows, long multi-line requests cut into fragments, 96 status errors) -> camelot_lattice (114 rows). The PDF is 17 pages of multi-line requests; 108 records with 107 dates and 108 decisions populated is plausible; the previous 210 included fragments.
- 1177 (Crawford Art Gallery) 43 -> 0 (-43): camelot_lattice chosen but fails width_uniformity + fragment_share (25 rows, width 6, fragment_share 0.20), so it is emptied. Before, only 19 of 43 records had a status and 20 a date, i.e. partly misaligned.
- 1552 (NCCA) 79 -> 0 (-79): the cached Mistral OCR result is now selected (mistral_cache, 118 rows, fragment 0.017, split 0.005) but fails repeated_header_share alone, so it is emptied. Likely false positive; no paid call was made.
- 1653 11 -> 0 (-11): same 11-row pdfplumber table, now fails width_uniformity alone. Before all 11 records had status and dates. Plausible false positive on a small table.
- 1655 (RTE) 1436 -> 1529 (+93): 34 of 39 files pdfplumber -> camelot_lattice, 3 camelot_stream -> pdfplumber, 2 unchanged. Sampled Q1-2021: the PDF has 52 numbered FOI lines (pdftotext), after = 52 records, before = 73 over-split. Q3-2019 0 -> 43 and Q4-2023 0 -> 39 now parse. Q2-2025 45 -> 0: gated by split_word_rate 0.025 alone although its rows (FOI No., date, request, requester, decision) look clean (false positive). decision_status populated 665 -> 1525. foi_reference_id (890) and date_received (0) stay poorly populated because headers `F OI No.` and `Date FOI Received` are unmapped.
- 1741 (Sport Ireland) 394 -> 331 (-63): FOI Disclosure Log 2021 went camelot_stream (53 records) -> pdfplumber, whose 53 rows pass the gate but whose header is one merged cell (`Date Request Received Ref Number ...`, other cells None). The header step cannot map it and the 52 data rows yield 0 records: a header-detection gap exposed by the extractor change, not a gate effect. 2023 Q2 10 -> 0 is gated (width_uniformity + fragment_share).
- 1774 (Teagasc) 67 -> 82 (+15): pdfplumber -> pymupdf; date_received populated 4 -> 79 and decision_status 0 -> 79, but foi_reference_id 63 -> 3 (`Internal Reference` header not mapped).
- 1882 (Udaras na Gaeltachta) 110 -> 53 (-57): three files gated (Loga-Nochta-2017 pymupdf 11 -> 0, Loga-Nochta-2020 12 -> 0, FOI-Disclosure-Log-2023 34 -> 0). 2023 (34 rows, width 6, fragment 0, only split_word_rate 0.038) looks clean: false positive candidate.
- 1259, 1711, 1747, 1806: no canonical record change (1259 8 -> 8; 1711 and 1747 gated files had 0 records before; 1806 has no PDF record).

## Sampled changed files (3 per mechanism, checked against pdftotext output of the cached PDF)

- pdfplumber -> camelot_lattice: RTE Q1-2021 (52 numbered lines in PDF; 52 records after, 73 before): ok. C&AG Q2-2026 (17 pages, Date Request Received / Records Requested / Decision / Reply Date; first record 2026-06-23 / 2026-06-29 / Refused, aligned): ok. RTE Q2-2025: gated although the extracted rows match the PDF layout: gate wrong.
- pdfplumber -> pymupdf: Teagasc 2025 (7 pages; dates and decisions now populated, reference id lost): mixed. Tusla 2021 (117 rows): ok via the https URL record. Udaras 2017: gated.
- camelot_stream -> pdfplumber: Sport Ireland 2021 (merged header, 0 records): worse. Skillnet FOI_Disclosure_Log (gated, 0 records before and after): neutral. Tusla 2026 Q1 (gated, 0 before): neutral. No benefit demonstrated on these three.
- gate (fail-closed): 1177 camelot_lattice and Tusla 2025 are structurally broken (fragment_share 0.12-0.20); RTE Q2-2025, NCCA, 1653 and Udaras 2023 look like false positives.

## Not verified

Checks are pdftotext text and row counts plus inspection of pipeline intermediate rows; no visual check of PDF images was made. 'False positive' labels are judgments from the metrics and extracted rows. The result is 13 bodies, so it says nothing about the other bodies' ~1,100 uncached files.
