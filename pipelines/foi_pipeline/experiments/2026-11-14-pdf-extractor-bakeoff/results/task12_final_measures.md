# Task 12 final measures (read-only)

Records 59600 -> 56850 (2750 lost, 4.6%); errors 2875 -> 1308.

## Gate blast radius

- files gated before 72, now 138; newly gated 66; gated files still emitting records: 3 (257 records)
- records lost from newly gated files: 2903; errors those files had before: 566
- newly gated with records before and 0 errors: 29 files, 1320 records
- newly gated with error rate < 5% before: 36
- newly gated with >= 40 records and <= 3 errors before: 17

## Records with no reference and no dates

3228 of 56850 (spec baseline 3,354 of 59,600)

Top bodies: 1486: 747, 1235: 547, 1655: 521, 1390: 444, 1456: 229, 1104: 141, 1112: 111, 1834: 94

## Files with errors on >= 20% of rows (errors / (records + errors))

52 files, 647 errors, 758 surviving records; before: 99 files.
Docling scope (gated 138 + these not gated 51) = 189

| body | records | errors | rate | extractor | dominant class | file |
|---|---|---|---|---|---|---|
| 1295 | 119 | 268 | 69% | pdfplumber | cross_role | https://www.fingal.ie/sites/default/files/2019-03/FOI%20Disclosure%20Log%202016.pdf |
| 1508 | 43 | 43 | 50% | camelot_stream | unknown_value | https://www.mayo.ie/getmedia/22f4ee22-443f-440d-9186-e8d8907f67d3/Disclosure-Log-Q1-2024.pdf |
| 1508 | 35 | 35 | 50% | camelot_stream | unknown_value | https://www.mayo.ie/getmedia/137e2288-371f-4f9c-9127-ec488798faac/Disclosure-Log-Q4-2023.pdf |
| 1655 | 54 | 30 | 36% | camelot_lattice | glyph_split | https://about.rte.ie/wp-content/uploads/2021/06/RTE-FOI-DISCLOSURE-LOG-Q4-2020-1.pdf |
| 1122 | 18 | 20 | 53% | pdfplumber | unknown_value | https://www.cityofdublinetb.ie/media/Disclosure-Log-2020.pdf |
| 1200 | 34 | 16 | 32% | pdfplumber | unknown_value | https://assets.gov.ie/static/documents/foi-disclosure-log-q1-2022-6670e4aa-fb1f-4dc8-810b-c4f5c5b5e75d.pdf |
| 1786 | 42 | 14 | 25% | pdfplumber | unknown_value | https://www.housingagency.ie/wp-content/uploads/2026/05/2022_Disclosure_Register.pdf |
| 1335 | 40 | 13 | 25% | pdfplumber | unknown_value | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/FOI-Disclosure-Log-January-December-2019.pdf |
| 1200 | 25 | 13 | 34% | pdfplumber | unknown_value | https://assets.gov.ie/static/documents/foi-disclosure-log-q2-2022-60673303-19ed-4235-b3a5-d7da4aeb5064.pdf |
| 1335 | 40 | 13 | 25% | pdfplumber | unknown_value | https://assets-eu-01.kc-usercontent.com:443/5608854e-b2c7-0144-a5f6-88a7e629b0a4/7e855dcd-fe22-4f8f-b1f2-4d4894b05328/disclosure-foi-2019.pdf |
| 1562 | 14 | 12 | 46% | None | cross_role | https://www.museum.ie/getmedia/1dd83c82-3ce7-4758-ac9c-262b9844c306/FOI-Log-2025_.xlsx |
| 1775 | 45 | 12 | 21% | pdfplumber | unknown_value | https://www.tudublin.ie/media/website/explore/foi/documents/TU-Dublin-2021-Disclosure-Log.pdf |
| 1561 | 11 | 11 | 50% | pdfplumber | unknown_value | https://nationalmilkagency.ie/wp-content/uploads/2026/04/FOI-Disclosure-Log-April-2026.pdf |
| 1392 | 21 | 11 | 34% | mistral_cache | unknown_value | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---july-to-september-2025-q3.pdf?sfvrsn=8602a498_5 |
| 1164 | 18 | 10 | 36% | pdfplumber | unknown_value | https://www.corketb.ie/wp-content/uploads/2026/06/FOI-Disclosure-Log-2023.pdf |
| 1573 | 9 | 9 | 50% | pdfplumber | unknown_value | https://www.nui.ie/app/uploads/2026/03/FOI-Disclosure-Log.pdf |
| 1392 | 16 | 9 | 36% | mistral_cache | unknown_value | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---october-to-december-2025-q4.pdf?sfvrsn=c8d370d8_5 |
| 1392 | 18 | 7 | 28% | mistral_cache | unknown_value | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---april-to-june-2025-q2.pdf?sfvrsn=983dbd6e_7 |
| 1868 | 7 | 6 | 46% | camelot_stream | unknown_value | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2024.pdf |
| 1679 | 18 | 6 | 25% | pdfplumber | unknown_value | https://www.grireland.ie/globalassets/rescource-centre/documents/foi-publication-scheme/disclosure-log-2024.pdf |
| 1622 | 4 | 6 | 60% | pdfplumber | unknown_value | https://assets.gov.ie/static/documents/foi-disclosures-log.pdf |
| 1438 | 0 | 5 | 100% | pdfplumber | cross_role | https://www.ihrec.ie/downloads/Freedom-of-Information-Disclosure-Log-Q3-2024.pdf |
| 1164 | 12 | 5 | 29% | pdfplumber | unknown_value | https://www.corketb.ie/wp-content/uploads/2026/06/FOI-Disclosure-Log-2024.pdf |
| 1868 | 5 | 4 | 44% | mistral_cache | unknown_value | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2023.pdf |
| 1392 | 9 | 4 | 31% | pdfplumber | unknown_value | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---january-to-march-2026-q1---updated.pdf?sfvrsn=560d88c8_7 |
| 1455 | 12 | 4 | 25% | pdfplumber | unknown_value | https://kwetb.ie/wp-content/uploads/2023/08/KWETB-FOI-DISCLOSURE-LOG-2021-1.pdf |
| 1153 | 13 | 4 | 24% | pdfplumber | unknown_value | https://www.cru.ie/documents/28330/CRU_2017_FOI_Disclosure_Log.pdf |
| 1773 | 1 | 3 | 75% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q4%202022.pdf |
| 1773 | 1 | 3 | 75% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/2021/FOI%20Disclosure%20Log%20Q4%202021.pdf |
| 1460 | 6 | 3 | 33% | pdfplumber | unknown_value | https://kcetb.ie/wp-content/uploads/2026/01/Disclosure-Log-2025.pdf |
| 1587 | 6 | 3 | 33% | pdfplumber | unknown_value | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2023.pdf |
| 1817 | 0 | 3 | 100% | mistral_cache | cross_role | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202020.pdf |
| 1786 | 6 | 3 | 33% | pdfplumber | unknown_value | https://www.housingagency.ie/wp-content/uploads/2019/03/2016-foi-disclosure-register.pdf |
| 1817 | 6 | 3 | 33% | pymupdf | cross_role | https://www.tipperarycoco.ie/sites/default/files/2026-07/June.pdf |
| 1758 | 0 | 3 | 100% | camelot_stream | cross_role | https://a.storyblok.com/f/46384/x/ac3c8cd7ee/foi-disclosure-log-2018-2020.pdf |
| 1773 | 1 | 3 | 75% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q3%202022.pdf |
| 1455 | 11 | 3 | 21% | pdfplumber | cross_role | https://kwetb.ie/wp-content/uploads/2023/08/KWETB-FOI-DISCLOSURE-LOG-2020-1.pdf |
| 1587 | 7 | 3 | 30% | pdfplumber | unknown_value | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2021.pdf |
| 1773 | 1 | 2 | 67% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q3%202023.pdf |
| 1868 | 5 | 2 | 29% | mistral_cache | unknown_value | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2021.pdf |
| 1773 | 1 | 2 | 67% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q1%202022.pdf |
| 1773 | 1 | 2 | 67% | pdfplumber | unknown_value | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q2%202024.pdf |
| 1010 | 6 | 2 | 25% | camelot_lattice | unknown_value | https://www.pleanala.ie/getmedia/1f0ca993-b178-481a-8972-57849a81b5e4/2015-Q2.pdf |
| 1587 | 4 | 2 | 33% | pdfplumber | unknown_value | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2022.pdf |
| 1437 | 2 | 2 | 50% | pdfplumber | unknown_value | https://www.fiscalcouncil.ie/wp-content/uploads/2021/03/FOI-Disclosure-Log-2016.pdf |
| 1773 | 1 | 2 | 67% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q1%202020.pdf |
| 1868 | 3 | 2 | 40% | mistral_cache | unknown_value | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2022.pdf |
| 1773 | 1 | 2 | 67% | pdfplumber | cross_role | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q2%202022.pdf |
| 1817 | 2 | 1 | 33% | mistral_cache | unknown_value | https://www.tipperarycoco.ie/sites/default/files/2022-12/FOI%20Disclosure%20Log%20July%202022.pdf |
| 1868 | 1 | 1 | 50% | pdfplumber | unknown_value | https://westerndevelopment.ie/wp-content/uploads/2021/02/2019-FOI-published-list.pdf |
| 1773 | 2 | 1 | 33% | pdfplumber | unknown_value | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q4%202018.pdf |
| 1773 | 1 | 1 | 50% | pdfplumber | unknown_value | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q3%202019.pdf |

## Files with errors on >= 50% of rows (errors / (records + errors))

21 files, 426 errors, 251 surviving records; before: 31 files.


## Alternative definition: share of surviving records carrying known_issues

- >= 20%: 57 files, 867 records, 648 errors
- >= 50%: 31 files, 275 records, 213 errors

Records with known_issues: 1185; canonicalize errors: 1308 (an error does not always drop its row).

## Per body: errors and records, before -> after (all bodies that changed)

| body | errors before | errors after | records before | records after |
|---|---|---|---|---|
| 1655 | 1101 | 98 | 1584 | 1502 |
| 1594 | 54 | 2 | 1382 | 661 |
| 1501 | 8 | 6 | 1088 | 628 |
| 1295 | 554 | 291 | 878 | 993 |
| 1508 | 0 | 82 | 1138 | 864 |
| 1153 | 16 | 4 | 328 | 79 |
| 1864 | 114 | 0 | 6 | 120 |
| 1342 | 16 | 13 | 1389 | 1190 |
| 1122 | 84 | 20 | 115 | 18 |
| 1244 | 3 | 3 | 679 | 526 |
| 1200 | 63 | 33 | 813 | 704 |
| 1104 | 27 | 23 | 367 | 237 |
| 1552 | 14 | 0 | 101 | 0 |
| 1390 | 7 | 7 | 767 | 663 |
| 1388 | 0 | 0 | 224 | 125 |
| 1834 | 12 | 9 | 727 | 654 |
| 1210 | 22 | 3 | 446 | 425 |
| 1213 | 15 | 15 | 2524 | 2561 |
| 1817 | 48 | 18 | 1054 | 1052 |
| 1151 | 14 | 0 | 206 | 192 |
| 1052 | 10 | 8 | 203 | 182 |
| 1475 | 0 | 0 | 118 | 141 |
| 1177 | 7 | 0 | 15 | 0 |
| 1471 | 0 | 0 | 22 | 0 |
| 1164 | 17 | 17 | 75 | 55 |
| 1053 | 2 | 2 | 92 | 75 |
| 1389 | 0 | 0 | 30 | 13 |
| 1752 | 4 | 0 | 12 | 0 |
| 1882 | 3 | 2 | 110 | 98 |
| 1868 | 19 | 15 | 27 | 21 |
| 1647 | 0 | 0 | 31 | 23 |
| 1207 | 53 | 50 | 4546 | 4545 |
| 1658 | 5 | 6 | 96 | 97 |
| 1335 | 34 | 33 | 692 | 691 |
| 1196 | 8 | 7 | 1564 | 1564 |
