# All-bodies before/after (2026-11-14)

**Method.** Every eligible file was already cached (main cache topped up from the `motion-model-sweep` worktree cache: 1,449 of 1,449 eligible URLs, no downloads). `transform_disclosure_files --force --processes 8` (cache-only Mistral, no paid OCR), then `process.py --from assess_table_structure --to extract_disclosures_canonicalize_rows --force`. errors.json in that range reset to `[]` first. Before = on-disk outputs of the Nov 12-13 build, snapshotted before the run to `/Volumes/ext/dev/publicinformation/foi-before-snapshot-2026-11-12/` (outside the repo; the only copy). Tables below cover the union of bodies in before and after (130 bodies), so bodies that went to zero are included; ignore the generator's "NOT an all-bodies result" line. Dedup not run.

**Caveat: before/after bytes may differ.** The before build's downloads were removed from the cache; after used bytes from the motion-model-sweep cache. A body that replaced a file at the same URL in between shows a content change, not a code change.

## Finding: pymupdf is non-deterministic under threads
The step's default `ThreadPoolExecutor` gives different pymupdf (and therefore selection) results run to run on identical bytes. Tusla 2023 (http and https copies are byte-identical, sha256 aa60d2c06cf9...): threaded runs gave 126, 154, 131, 133, 159, 188 rows; four `--processes` runs all gave 116. Tusla 2022: threads pick camelot_lattice, processes pick pymupdf. PyMuPDF is documented as not thread-safe. **The 13-body before_after.md numbers came from threaded runs and are partly affected** (Tusla 1112: 525 there, 1,128 here). This run used processes and is deterministic on the checked body.

## Headline
- Records (canonicalize_rows): 63,159 -> 43,697 (-19,462, -31%).
- 14 bodies go to zero (2,283 records): 1089, 1177, 1202, 1484, 1496, 1505, 1552, 1573, 1653, 1752, 1758, 1771, 1867, 1876. No body is new in after.
- UnrecognizedDecisionStatus 644 -> 294, StatusValueIsDate 558 -> 341, UnrecognizedRequesterType 1,737 -> 1,587.

## Gate (assess_table_structure)
- 487 PDF files gated, holding 25,778 extracted rows.
- Failed checks per gated file: 1 check 297, 2 checks 138, 3+ checks 52.
- Single-check failures hold 13,552 rows. Near-threshold band per check (absolute):

| check | single-check files | near band | files in band | rows in band |
|---|---|---|---|---|
| width_uniformity | 151 | >=0.88 (th 0.92) | 25 | 1287 |
| split_word_rate | 116 | <=0.03 (th 0.02) | 36 | 1626 |
| repeated_header_share | 19 | <=0.10 (th 0.07) | 7 | 494 |
| fragment_share | 10 | <=0.10 (th 0.08) | 3 | 90 |
| column_type_purity | 1 | >=0.80 (th 0.85) | 1 | 80 |

- Parked false-positive candidates (Tusla 2022, 1653, Udaras 2023, RTE Q2-2025) need re-checking against this run: Tusla 2022 and 2023 now pass via pymupdf.

Coverage: 130 bodies (1010, 1024, 1038, 1047, 1052, 1053, 1089, 1093, 1094, 1104, 1107, 1110, 1112, 1122, 1129, 1149, 1151, 1153, 1157, 1162, 1163, 1164, 1169, 1176, 1177, 1194, 1196, 1198, 1200, 1202, 1204, 1205, 1207, 1208, 1210, 1211, 1212, 1213, 1227, 1235, 1244, 1245, 1259, 1262, 1293, 1295, 1298, 1335, 1336, 1339, 1340, 1342, 1388, 1389, 1390, 1391, 1392, 1394, 1400, 1404, 1437, 1438, 1442, 1443, 1449, 1455, 1456, 1460, 1470, 1471, 1475, 1484, 1486, 1493, 1496, 1497, 1500, 1501, 1505, 1508, 1511, 1525, 1544, 1552, 1559, 1561, 1562, 1568, 1570, 1571, 1573, 1574, 1587, 1590, 1594, 1597, 1602, 1622, 1629, 1647, 1653, 1655, 1658, 1661, 1679, 1711, 1732, 1741, 1747, 1752, 1753, 1758, 1771, 1773, 1774, 1775, 1777, 1786, 1806, 1817, 1827, 1834, 1844, 1864, 1867, 1868, 1870, 1873, 1876, 1882); 1374 PDF files. NOT an all-bodies result.

### Errors per error_type

| error_type | before | after | delta |
|---|---|---|---|
| StatusValueIsColumnHeader | 39 | 25 | -14 |
| StatusValueIsDate | 558 | 341 | -217 |
| StatusValueIsRequesterType | 1 | 0 | -1 |
| TableStructureUnreliable | 0 | 487 | 487 |
| UnrecognizedDecisionStatus | 644 | 294 | -350 |
| UnrecognizedRequesterType | 1737 | 1587 | -150 |

### Records per public_body_id (canonicalize_rows)

| public_body_id | before | after | delta |
|---|---|---|---|
| 1010 | 711 | 295 | -416 |
| 1024 | 19 | 12 | -7 |
| 1038 | 66 | 44 | -22 |
| 1052 | 203 | 203 | 0 |
| 1053 | 92 | 75 | -17 |
| 1089 | 9 | 0 | -9 |
| 1094 | 727 | 727 | 0 |
| 1104 | 372 | 312 | -60 |
| 1107 | 452 | 426 | -26 |
| 1110 | 37 | 37 | 0 |
| 1112 | 1086 | 1128 | 42 |
| 1122 | 126 | 71 | -55 |
| 1129 | 842 | 853 | 11 |
| 1151 | 206 | 57 | -149 |
| 1153 | 328 | 179 | -149 |
| 1157 | 210 | 108 | -102 |
| 1162 | 1531 | 1531 | 0 |
| 1163 | 1778 | 1152 | -626 |
| 1164 | 93 | 75 | -18 |
| 1169 | 16 | 12 | -4 |
| 1176 | 766 | 472 | -294 |
| 1177 | 43 | 0 | -43 |
| 1196 | 1578 | 1168 | -410 |
| 1198 | 1595 | 194 | -1401 |
| 1200 | 882 | 437 | -445 |
| 1202 | 726 | 0 | -726 |
| 1204 | 1332 | 614 | -718 |
| 1205 | 32 | 156 | 124 |
| 1207 | 4597 | 4289 | -308 |
| 1208 | 2796 | 1806 | -990 |
| 1210 | 616 | 196 | -420 |
| 1211 | 89 | 89 | 0 |
| 1212 | 2951 | 2064 | -887 |
| 1213 | 2748 | 767 | -1981 |
| 1227 | 1409 | 1409 | 0 |
| 1235 | 1348 | 539 | -809 |
| 1244 | 679 | 526 | -153 |
| 1245 | 204 | 83 | -121 |
| 1259 | 8 | 8 | 0 |
| 1262 | 241 | 241 | 0 |
| 1293 | 92 | 41 | -51 |
| 1295 | 863 | 942 | 79 |
| 1335 | 710 | 401 | -309 |
| 1336 | 8 | 8 | 0 |
| 1339 | 5 | 5 | 0 |
| 1340 | 647 | 647 | 0 |
| 1342 | 1389 | 1224 | -165 |
| 1388 | 212 | 224 | 12 |
| 1389 | 62 | 13 | -49 |
| 1390 | 767 | 376 | -391 |
| 1392 | 128 | 128 | 0 |
| 1400 | 212 | 212 | 0 |
| 1404 | 24 | 23 | -1 |
| 1437 | 48 | 36 | -12 |
| 1438 | 25 | 5 | -20 |
| 1443 | 687 | 183 | -504 |
| 1449 | 440 | 440 | 0 |
| 1455 | 64 | 53 | -11 |
| 1456 | 1011 | 739 | -272 |
| 1460 | 24 | 24 | 0 |
| 1470 | 33 | 48 | 15 |
| 1471 | 34 | 22 | -12 |
| 1475 | 598 | 58 | -540 |
| 1484 | 79 | 0 | -79 |
| 1486 | 1560 | 552 | -1008 |
| 1496 | 133 | 0 | -133 |
| 1497 | 379 | 379 | 0 |
| 1500 | 2 | 2 | 0 |
| 1501 | 1088 | 711 | -377 |
| 1505 | 98 | 0 | -98 |
| 1508 | 1138 | 1074 | -64 |
| 1511 | 1271 | 1271 | 0 |
| 1525 | 112 | 112 | 0 |
| 1544 | 272 | 251 | -21 |
| 1552 | 79 | 0 | -79 |
| 1561 | 11 | 11 | 0 |
| 1562 | 14 | 14 | 0 |
| 1568 | 104 | 91 | -13 |
| 1570 | 968 | 85 | -883 |
| 1571 | 556 | 515 | -41 |
| 1573 | 9 | 0 | -9 |
| 1574 | 433 | 89 | -344 |
| 1587 | 28 | 28 | 0 |
| 1590 | 785 | 694 | -91 |
| 1594 | 1465 | 1381 | -84 |
| 1597 | 3 | 3 | 0 |
| 1602 | 153 | 153 | 0 |
| 1622 | 4 | 4 | 0 |
| 1629 | 72 | 72 | 0 |
| 1647 | 33 | 31 | -2 |
| 1653 | 11 | 0 | -11 |
| 1655 | 1436 | 1529 | 93 |
| 1658 | 93 | 65 | -28 |
| 1679 | 119 | 21 | -98 |
| 1732 | 1973 | 1973 | 0 |
| 1741 | 394 | 331 | -63 |
| 1752 | 12 | 0 | -12 |
| 1753 | 29 | 29 | 0 |
| 1758 | 3 | 0 | -3 |
| 1771 | 57 | 0 | -57 |
| 1773 | 51 | 37 | -14 |
| 1774 | 67 | 82 | 15 |
| 1775 | 321 | 171 | -150 |
| 1786 | 204 | 187 | -17 |
| 1817 | 1346 | 423 | -923 |
| 1827 | 766 | 766 | 0 |
| 1834 | 726 | 489 | -237 |
| 1844 | 918 | 918 | 0 |
| 1864 | 6 | 6 | 0 |
| 1867 | 6 | 0 | -6 |
| 1868 | 44 | 7 | -37 |
| 1870 | 532 | 439 | -93 |
| 1873 | 441 | 441 | 0 |
| 1876 | 1018 | 0 | -1018 |
| 1882 | 110 | 53 | -57 |
| TOTAL | 63159 | 43697 | -19462 |

### PDF files per pdf_extractor

| pdf_extractor | before | after | delta |
|---|---|---|---|
| camelot_lattice | 0 | 212 | 212 |
| camelot_stream | 109 | 45 | -64 |
| mistral_cache | 0 | 137 | 137 |
| pdfplumber | 1263 | 933 | -330 |
| pymupdf | 0 | 47 | 47 |

### Files that changed extractor (transitions)

| before | after | files |
|---|---|---|
| absent | mistral_cache | 2 |
| camelot_stream | camelot_lattice | 11 |
| camelot_stream | mistral_cache | 34 |
| camelot_stream | pdfplumber | 34 |
| camelot_stream | pymupdf | 3 |
| pdfplumber | camelot_lattice | 201 |
| pdfplumber | camelot_stream | 18 |
| pdfplumber | mistral_cache | 101 |
| pdfplumber | pymupdf | 44 |

### Files that changed extractor (list)

| public_body_id | before | after | file_url |
|---|---|---|---|
| 1342 | pdfplumber | camelot_lattice | http://www.galway.ie/sites/default/files/2025-06/FOI%20Disclosure%20log%202017.pdf |
| 1342 | pdfplumber | camelot_lattice | http://www.galway.ie/sites/default/files/2025-06/FOI%20Disclosure%20log%202018.pdf |
| 1342 | pdfplumber | mistral_cache | http://www.galway.ie/sites/default/files/2025-06/FOI%20Disclosure%20log%202019.pdf |
| 1647 | camelot_stream | camelot_lattice | http://www.probation.ie/EN/PB/0/3C7CFCC3866559A08025888400584D73/$File/2021FOILogs.pdf |
| 1647 | pdfplumber | camelot_lattice | http://www.probation.ie/EN/PB/0/50BB0DA19912894F802586BD0048CAEC/$File/2020 non Personal FOI logs.pdf |
| 1647 | pdfplumber | camelot_lattice | http://www.probation.ie/EN/PB/0/6A2C9C0587C23708802586BD0048ABA5/$File/2019 non Personal FOI logs.pdf |
| 1112 | pdfplumber | pymupdf | http://www.tusla.ie/uploads/content/2021_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | pymupdf | http://www.tusla.ie/uploads/content/2022_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | pymupdf | http://www.tusla.ie/uploads/content/2023_FOI_Disclosures_Log.pdf |
| 1870 | pdfplumber | camelot_lattice | http://www.westmeathcoco.ie/en/media/DisclosureLogTemplate2023.pdf |
| 1870 | pdfplumber | camelot_lattice | http://www.westmeathcoco.ie/en/media/DisclosureLogTemplate2024.pdf |
| 1870 | pdfplumber | camelot_lattice | http://www.westmeathcoco.ie/en/media/FOI_DisclosureLog2025.pdf |
| 1758 | pdfplumber | camelot_stream | https://a.storyblok.com/f/46384/x/ac3c8cd7ee/foi-disclosure-log-2018-2020.pdf |
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
| 1335 | pdfplumber | camelot_lattice | https://assets-eu-01.kc-usercontent.com:443/5608854e-b2c7-0144-a5f6-88a7e629b0a4/67a1f976-5bc4-4948-ba5d-03982e0c8040/disclosure-foi-2018.pdf |
| 1335 | pdfplumber | camelot_lattice | https://assets-eu-01.kc-usercontent.com:443/5608854e-b2c7-0144-a5f6-88a7e629b0a4/7e855dcd-fe22-4f8f-b1f2-4d4894b05328/disclosure-foi-2019.pdf |
| 1335 | pdfplumber | camelot_lattice | https://assets-eu-01.kc-usercontent.com:443/5608854e-b2c7-0144-a5f6-88a7e629b0a4/c5b8a98b-111c-48ab-973a-c3f7e2f1a404/disclosure-foi-2022.pdf |
| 1198 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/033aa2c5/2025_DCEE_FOI_Disclosure_Log.pdf |
| 1212 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/0ba654f2/Freedom_of_Information_Quarter_4_Requests_2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/0e4f49c8/10._Non-personal_FOI_requests_answered_in_Oct_2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/12-non-personal-foi-requests-answered-in-dec-2023.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/1b65e3fb/9._Non-personal_FOI_requests_answered_in_Sep_2025.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/1f919c9b/Q2._FOI_Disclosure_Log_April_to_June_2025.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/2018-quarter-4-pdf-115kb.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/2019-quarter-1-pdf-117kb.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/2019-quarter-3-pdf-142kb.pdf |
| 1210 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/2025.04.01_DRCD_FOI_Disclosure_Log_Q1_2025.pdf |
| 1212 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/2371ea98/Freedom_of_Information_Quarter_3_Requests_2025.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/2625e929/DFHERIS_FOI_Logs_-_January_to_March_2026_-_For_Publication.pdf |
| 1213 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/2ac7debc/Quarter_2_2025.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/2ecd384f/Quarter_4_Freedom_of_Information_Logs_October_to_December_2025.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/34fabb9f/Q4_FOI_Disclosure_Log_October_to_December_2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/4._Non-personal_FOI_requests_answered_in_Apr_2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/5._Non-personal_FOI_requests_answered_in_May_2025.pdf |
| 1198 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/5ea732d5/AIE_Disclosure_Log_Q1_and_Q2_2026.pdf |
| 1594 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/5f66a911/Non_Personal_FOI_Requests_Q3_2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/6._Non-personal_FOI_requests_answered_in_June_2025.pdf |
| 1210 | camelot_stream | camelot_lattice | https://assets.gov.ie/static/documents/66495939/202512_DRCDG_Q4_DisclosureLog.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/7._Non-personal_FOI_requests_answered_in_July_2025.pdf |
| 1210 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/72841276/20251107_Q3DisclosureLog.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/7a390c4b/Final_Approved_Qtr_1_2025_FOI_Disclosure_Log.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/DFHERIS_FOI_Logs_-_April_to_June_2025.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/FOIDisLogJuly100625.pdf |
| 1200 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/FOI_Disclosure_Log_-_Q3_2024.pdf |
| 1200 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/FOI_Disclosure_Log_-_Q4_2024.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/FOI_Disclosure_Log_Q3_JULY_TO_SEPT_2024.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/FOI_Disclosure_Log__Q2_April_to_June_2024.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/FOI_Disclosure_Log__Q4_October_to_December_2024.pdf |
| 1213 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/Q3_2024_Disclosure_Log.pdf |
| 1213 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/Q4_2024_Disclosure_Log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/a3f4ba52/Quarter_1_2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/afe39b74/11._Non-personal_FOI_requests_answered_in_Nov_2025.pdf |
| 1594 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/aie-requests-2021.pdf |
| 1207 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/bda2d69d/Q3._FOI_Disclosure_Log_July_to_September_2025.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/d8689ada/DFHERIS_FOI_Logs_-_July_to_September_Quarter_3_2025.pdf |
| 1208 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/department-of-justice-non-personal-foi-requests-disclosure-log-2019.pdf |
| 1208 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/department-of-justice-non-personal-foi-requests-disclosure-log-2022.pdf |
| 1208 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/department-of-justice-non-personal-foi-requests-disclosure-log-2023.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-april-to-june-2023.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-april-to-june-2024.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-january-to-march-2023.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-january-to-march-2024.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-july-to-september-2023.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-july-to-september-2024.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-october-to-december-2023.pdf |
| 1205 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/dfheris-foi-logs-october-to-december-2024.pdf |
| 1196 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2017-pdf-553kb.pdf |
| 1213 | camelot_stream | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2020-q1.pdf |
| 1213 | camelot_stream | pdfplumber | https://assets.gov.ie/static/documents/disclosure-log-2020-q2.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2020-q3.pdf |
| 1213 | camelot_stream | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2020-q4.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2021-q1.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2021-q4.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/disclosure-log-2022-q1.pdf |
| 1213 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-2022-q3.pdf |
| 1213 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-2022-q4.pdf |
| 1213 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-2023-q3.pdf |
| 1213 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/disclosure-log-2024-q1.pdf |
| 1213 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-2024-q2.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-april-19e1ce02-7254-42d7-acf7-9623923db927.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-august-a4237ca9-d5c5-48fc-bad8-c6a51cf1a23d.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-december-c608eac8-4b01-4f08-8c50-3217a49a4a77.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-december-f819bb67-733f-40b3-9e6b-2ee298a933d4.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-july-226c4fed-f082-40a2-b134-6e44633a526c.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-july-4df8776d-81f3-46d8-a1e8-03a7ed81af6d.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-june-1138e419-a09d-4628-8f67-a0a5e3c46328.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-march-5119348b-245b-4815-9b02-b377645f1e62.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-march-d5da02f8-858d-49ac-96ab-8e0a11f25c7a.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-march-e1648b23-bb8f-44cd-9d90-5b5d15f0ed29.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-may-81b4088f-8f65-4877-a358-fb8b4a770067.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-may-a0731e19-0e13-4473-a0e7-788990cb4d5f.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-september-340c141d-2b5a-48e6-ade0-8ccd1caa653d.pdf |
| 1196 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/disclosure-log-september-863c1961-96a3-42b0-9632-4cae208d9e9c.pdf |
| 1200 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/foi-disclosure-log-2016-c6c6fc8f-4ec7-4f3b-a21f-3baee7625868.pdf |
| 1200 | absent | mistral_cache | https://assets.gov.ie/static/documents/foi-disclosure-log-2017-efec4c68-3b79-4410-9af4-bc13c05f3d86.pdf |
| 1200 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-disclosure-log-2019-c85f2f5e-3495-405f-a35d-4bb31b1b7bd4.pdf |
| 1198 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/foi-disclosure-log-2024.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-disclosure-log-july-to-september-2023.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-disclosure-log-october-to-december-2023.pdf |
| 1200 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-disclosure-log-q1-2022-6670e4aa-fb1f-4dc8-810b-c4f5c5b5e75d.pdf |
| 1200 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-disclosure-log-q1-2024-71e7fba3-cd59-4a2e-bf2d-e16487c12185.pdf |
| 1200 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/foi-disclosure-log-q2-2021-b2efdd24-f849-49f4-8b65-0b1b9bbcc552.pdf |
| 1200 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-disclosure-log-q2-2022-60673303-19ed-4235-b3a5-d7da4aeb5064.pdf |
| 1207 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-q1-disclosure-log-2024.pdf |
| 1210 | camelot_stream | pdfplumber | https://assets.gov.ie/static/documents/foi-requests-april-june-2018-63223afe-123b-4b22-b6fd-bb3aed0aef15.pdf |
| 1210 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-requests-april-june-2024.pdf |
| 1210 | camelot_stream | pdfplumber | https://assets.gov.ie/static/documents/foi-requests-january-march-2018.pdf |
| 1210 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-requests-january-march-2022.pdf |
| 1210 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/foi-requests-january-march-2024.pdf |
| 1210 | camelot_stream | pdfplumber | https://assets.gov.ie/static/documents/foi-requests-july-september-2023.pdf |
| 1210 | camelot_stream | camelot_lattice | https://assets.gov.ie/static/documents/foi-requests-october-december-2018.pdf |
| 1210 | camelot_stream | camelot_lattice | https://assets.gov.ie/static/documents/foi-requests-october-december-2023.pdf |
| 1212 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/freedom-of-information-quarter-2-requests-2021.pdf |
| 1212 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/freedom-of-information-quarter-3-requests-2022.pdf |
| 1212 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/freedom-of-information-quarter-3-requests-2024.pdf |
| 1212 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/freedom-of-information-request-quarter-4-2019.pdf |
| 1594 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-2021.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-aug-2024.pdf |
| 1204 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-feb-2023.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-feb-2024.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-jan-2024.pdf |
| 1204 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-july-2024.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-mar-2024-613e56c1-5cdf-4dde-aa0e-c6c1dfc841c2.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-nov-2023.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-nov-2024.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-oct-2023.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-answered-in-sep-2024.pdf |
| 1204 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/non-personal-foi-requests-dec-2024.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-feb-2025.pdf |
| 1204 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/non-personal-foi-requests-mar-2025.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q1-2016-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q1-2019-foi-disclosure-log.pdf |
| 1213 | camelot_stream | mistral_cache | https://assets.gov.ie/static/documents/q1-and-q2-foi-2017-disclosure-requests.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q2-2016-foi-disclosure-log.pdf |
| 1213 | pdfplumber | camelot_lattice | https://assets.gov.ie/static/documents/q2-2019-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q3-2016-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q3-2017-foi-disclosure-log.pdf |
| 1213 | pdfplumber | pymupdf | https://assets.gov.ie/static/documents/q3-2018-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q3-2019-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q4-2016-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | https://assets.gov.ie/static/documents/q4-2017-foi-disclosure-log.pdf |
| 1392 | pdfplumber | mistral_cache | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---april-to-june-2025-q2.pdf?sfvrsn=983dbd6e_7 |
| 1392 | pdfplumber | camelot_stream | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---april-to-june-2026-q2.pdf?sfvrsn=47d99c2c_3 |
| 1392 | pdfplumber | mistral_cache | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---january-to-march-2025-q1.pdf?sfvrsn=4115ee6b_11 |
| 1392 | pdfplumber | mistral_cache | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---july-to-september-2025-q3.pdf?sfvrsn=8602a498_5 |
| 1392 | pdfplumber | mistral_cache | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---october-to-december-2025-q4.pdf?sfvrsn=c8d370d8_5 |
| 1544 | pdfplumber | pymupdf | https://assets.nama.ie/uploads/documents/Copy-of-FOI-Disclosure-log-2024.pdf |
| 1571 | pdfplumber | camelot_lattice | https://assets.ntma.ie/general/Q1-Disclosure-Log-2025.pdf |
| 1602 | camelot_stream | camelot_lattice | https://assets.oic.ie/media/283692/b9122c8c-643f-491f-a9c5-017e8df02109.pdf |
| 1053 | pdfplumber | camelot_lattice | https://bim.ie/wp-content/uploads/2021/03/BIM-FOI-Log-2017-to-2019-Inclusive.pdf |
| 1053 | pdfplumber | camelot_lattice | https://bim.ie/wp-content/uploads/2021/03/FOI-requests-2020-to-2021-for-website_.docx.pdf |
| 1053 | pdfplumber | pymupdf | https://bim.ie/wp-content/uploads/2023/02/BIM-FOI-requests-2021-for-website.pdf |
| 1053 | pdfplumber | camelot_lattice | https://bim.ie/wp-content/uploads/2025/02/Freedom-of-Information-Log-2024.pdf |
| 1177 | pdfplumber | camelot_lattice | https://crawfordartgallery.ie/wp-content/uploads/20260527_FOI-LOG.pdf |
| 1202 | pdfplumber | mistral_cache | https://enterprise.gov.ie/en/publications/publication-files/foi-log-2025.pdf |
| 1456 | pdfplumber | camelot_lattice | https://kildarecoco.ie/YourCouncil/GovernanceandCompliance/FreedomofInformation/DisclosureLog/DISCLOSURE LOG SECOND HALF OF 2016.pdf |
| 1456 | pdfplumber | camelot_lattice | https://kildarecoco.ie/YourCouncil/GovernanceandCompliance/FreedomofInformation/DisclosureLog/disclosure log 2nd half of 2025.pdf |
| 1470 | absent | mistral_cache | https://laois.ie/sites/default/files/2024-06/FOI-Disclosure-Log-2023.pdf |
| 1484 | pdfplumber | camelot_lattice | https://lcetb.ie/wp-content/uploads/2026/06/FOI-DISCLOSURE-LOG_2025.pdf |
| 1505 | pdfplumber | mistral_cache | https://marine.ie/sites/default/files/MIFiles/Docs/Comms/foi-disclosure-log-2019-2025.pdf |
| 1505 | pdfplumber | camelot_lattice | https://marine.ie/sites/default/files/MIFiles/Docs_Comms/FOI Disclosure Log (2016-2018).pdf |
| 1552 | pdfplumber | mistral_cache | https://ncca.ie/media/4qffya5u/ncca-disclosure-log-2024.pdf |
| 1774 | pdfplumber | pymupdf | https://teagasc.ie/wp-content/uploads/Teagasc-FOI-Disclosure-Log-2025.pdf |
| 1867 | pdfplumber | camelot_stream | https://westerncare.com/wp-content/uploads/2020/07/RMD-6-foi-request.pdf |
| 1868 | pdfplumber | camelot_lattice | https://westerndevelopment.ie/wp-content/uploads/2021/02/2018-FOI-published-list.pdf |
| 1868 | camelot_stream | mistral_cache | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2021.pdf |
| 1868 | camelot_stream | mistral_cache | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2022.pdf |
| 1868 | camelot_stream | mistral_cache | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2023.pdf |
| 1868 | camelot_stream | mistral_cache | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2024.pdf |
| 1868 | camelot_stream | mistral_cache | https://westerndevelopment.ie/wp-content/uploads/2026/01/FOI-2025.pdf |
| 1024 | camelot_stream | camelot_lattice | https://www.alab.ie/media/FOI%20Disclosure_Log%202022.pdf |
| 1024 | pdfplumber | camelot_lattice | https://www.alab.ie/media/alab/FOI%20Register%20-%20Disclosure%20Log%202020.pdf |
| 1024 | pdfplumber | camelot_lattice | https://www.alab.ie/media/alab/FOI%20Register%20-%20Disclosure%20Log%202021.pdf |
| 1157 | pdfplumber | camelot_lattice | https://www.audit.gov.ie/media/2dbjzig4/foi-disclosure-log-q2-2026.pdf |
| 1052 | camelot_stream | mistral_cache | https://www.bordbia.ie/contentassets/ae9dcd8ebda3420d9c5182309ca770c8/bord-bia-foi-disclosure-log-2025.pdf |
| 1052 | camelot_stream | mistral_cache | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/bord-bia-foi-disclosure-log-2021.pdf |
| 1052 | camelot_stream | mistral_cache | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/disclosure-log-2015.pdf |
| 1052 | camelot_stream | mistral_cache | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/disclosure-log-2016.pdf |
| 1052 | camelot_stream | pdfplumber | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/disclosure-log-2017.pdf |
| 1052 | camelot_stream | pdfplumber | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/disclosure-log-2018.pdf |
| 1052 | camelot_stream | pdfplumber | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/foi-disclosure-log-2019.pdf |
| 1052 | camelot_stream | mistral_cache | https://www.bordbia.ie/globalassets/bordbia2020/food-and-living/recipes/new-recipes-6.7.20/22.2.21/bord-bia-foi-disclosure-log-2024.pdf |
| 1104 | camelot_stream | mistral_cache | https://www.centralbank.ie/docs/default-source/tns/about---tns/freedom-of-information/disclosure-logs/freedom-of-information-disclosure-log---2022.pdf?sfvrsn=4d6f991d_5 |
| 1104 | camelot_stream | mistral_cache | https://www.centralbank.ie/docs/default-source/tns/about---tns/freedom-of-information/disclosure-logs/freedom-of-information-disclosure-log---2024-(non-personal-requests).pdf?sfvrsn=8155651a_3 |
| 1104 | camelot_stream | mistral_cache | https://www.centralbank.ie/docs/default-source/tns/about---tns/freedom-of-information/disclosure-logs/freedom-of-information-disclosure-log---q1-2026-(non-personal-requests).pdf?sfvrsn=8aff731a_1 |
| 1104 | camelot_stream | mistral_cache | https://www.centralbank.ie/docs/default-source/tns/about---tns/freedom-of-information/disclosure-logs/freedom-of-information-disclosure-log-2023-(non-personal-requests).pdf?sfvrsn=81cf621a_9 |
| 1107 | pdfplumber | camelot_lattice | https://www.charitiesregulator.ie/media/2284/2020-disclosure-log.pdf |
| 1122 | camelot_stream | pymupdf | https://www.cityofdublinetb.ie/media/2025-Quarters-1-4-FOI-Disclosure-Log.pdf |
| 1122 | pdfplumber | camelot_lattice | https://www.cityofdublinetb.ie/media/City-of-Dublin-FOI-Disclosure-Log-2023-(1).pdf |
| 1129 | pdfplumber | camelot_lattice | https://www.clarecoco.ie/sites/default/files/2025-01/foi-disclosure-log-january-to-december-2021-43962.pdf |
| 1151 | pdfplumber | camelot_lattice | https://www.comreg.ie/media/2016/03/Disclosure-Log-2015-Publication-1.pdf |
| 1151 | pdfplumber | camelot_stream | https://www.comreg.ie/media/2019/05/Disclosure-Log-2018.pdf |
| 1151 | pdfplumber | camelot_stream | https://www.comreg.ie/media/2020/04/Disclosure-Log-2019.pdf |
| 1151 | pdfplumber | camelot_stream | https://www.comreg.ie/media/2021/09/FOI-Disclosure-Log-YE-2020_.pdf |
| 1151 | pdfplumber | camelot_stream | https://www.comreg.ie/media/2023/02/Disclosure-Log-YE-2022.pdf |
| 1151 | pdfplumber | camelot_stream | https://www.comreg.ie/media/2024/04/Disclosure-Log-ye-2023.pdf |
| 1163 | pdfplumber | pymupdf | https://www.corkcoco.ie/sites/default/files/2023-01/freedom-of-information-disclosure-log-2021-pdf.pdf |
| 1163 | pdfplumber | pymupdf | https://www.corkcoco.ie/sites/default/files/2023-06/freedom-of-information-disclosure-log-2022-pdf.pdf |
| 1389 | pdfplumber | camelot_lattice | https://www.coru.ie/media/02fazylt/foi-disclosure-log-2024.pdf |
| 1389 | pdfplumber | camelot_lattice | https://www.coru.ie/media/vdwdvd42/coru-foi-log-2022.pdf |
| 1176 | pdfplumber | camelot_lattice | https://www.courts.ie/docs/default-source/default-document-library/courts-documents/foi-2019-q3.pdf |
| 1176 | pdfplumber | pymupdf | https://www.courts.ie/docs/default-source/default-document-library/courts-documents/foi-2020-q4.pdf |
| 1176 | pdfplumber | pymupdf | https://www.courts.ie/docs/default-source/default-document-library/courts-documents/foi-2021-q1.pdf |
| 1176 | pdfplumber | pymupdf | https://www.courts.ie/docs/default-source/default-document-library/courts-documents/foi-2021-q3.pdf |
| 1176 | pdfplumber | pymupdf | https://www.courts.ie/docs/default-source/default-document-library/courts-documents/foi-2021-q4.pdf |
| 1176 | pdfplumber | pymupdf | https://www.courts.ie/docs/default-source/default-document-library/courts-documents/foi-2022-q1.pdf |
| 1245 | pdfplumber | camelot_lattice | https://www.dkit.ie/system/files/2026-03/FOI-Disclosure-Log-2016.pdf |
| 1245 | pdfplumber | camelot_lattice | https://www.dkit.ie/system/files/2026-03/FOI-Disclosure-Log-2017.pdf |
| 1245 | pdfplumber | camelot_lattice | https://www.dkit.ie/system/files/2026-03/FOI-Disclosure-Log-2019.pdf |
| 1245 | pdfplumber | camelot_lattice | https://www.dkit.ie/system/files/2026-03/FOI-Disclosure-Log-2022.pdf |
| 1245 | pdfplumber | camelot_lattice | https://www.dkit.ie/system/files/2026-03/FOI-Disclosure-Log-2025.pdf |
| 1245 | pdfplumber | camelot_lattice | https://www.dkit.ie/system/files/2026-04/FOI-Disclosure-Log-Q1-2026-January-March.pdf |
| 1244 | pdfplumber | mistral_cache | https://www.dlrcoco.ie/sites/dlrcoco/files/2023-09/2021%20Freedom%20of%20Information%20Disclosure%20Log.pdf |
| 1244 | pdfplumber | camelot_stream | https://www.dlrcoco.ie/sites/dlrcoco/files/2025-01/2024%20Freedom%20of%20Information%20Disclosure%20Log.pdf |
| 1235 | camelot_stream | mistral_cache | https://www.dublincity.ie/sites/default/files/2026-02/disclosure-log-2025.pdf |
| 1335 | camelot_stream | camelot_lattice | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/1_What_We_Do/Disclosure-Log-January-March-2020.pdf |
| 1335 | pdfplumber | camelot_lattice | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/Disclosure-Log-2022_1.pdf |
| 1335 | pdfplumber | mistral_cache | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/FOI-Disclosure-Log-2023.pdf |
| 1335 | pdfplumber | camelot_lattice | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/FOI-Disclosure-Log-January-December-2018_1.pdf |
| 1335 | pdfplumber | camelot_lattice | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/FOI-Disclosure-Log-January-December-2019.pdf |
| 1295 | pdfplumber | mistral_cache | https://www.fingal.ie/sites/default/files/2019-03/FOI%20Disclosure%20Log%20January%20to%20end%20of%20March%202018%20%281%29.pdf |
| 1295 | pdfplumber | camelot_lattice | https://www.fingal.ie/sites/default/files/2024-07/foi-disclosure-log-2023.pdf |
| 1295 | pdfplumber | mistral_cache | https://www.fingal.ie/sites/default/files/2026-01/2024-foi-disclosure-log.pdf |
| 1293 | pdfplumber | camelot_lattice | https://www.fspo.ie/documents/FOI Disclosure Log - 2026 - Q2.pdf |
| 1293 | pdfplumber | pymupdf | https://www.fspo.ie/documents/FOI-Disclosure-Log-2021.pdf |
| 1293 | pdfplumber | camelot_lattice | https://www.fspo.ie/documents/FOI-Disclosure-Log-2022.pdf |
| 1293 | pdfplumber | pymupdf | https://www.fspo.ie/documents/FOI-Disclosure-Log-2024-q1.pdf |
| 1293 | pdfplumber | pymupdf | https://www.fspo.ie/documents/FOI-Disclosure-Log-Q1-2026.pdf |
| 1679 | pdfplumber | camelot_lattice | https://www.grireland.ie/globalassets/rescource-centre/documents/foi-publication-scheme/disclosure-log-2019.pdf |
| 1679 | pdfplumber | mistral_cache | https://www.grireland.ie/globalassets/rescource-centre/documents/foi-publication-scheme/disclosure-log-2022.pdf |
| 1786 | pdfplumber | camelot_lattice | https://www.housingagency.ie/wp-content/uploads/2019/03/2017-foi-disclosure-register.pdf |
| 1786 | pdfplumber | camelot_lattice | https://www.housingagency.ie/wp-content/uploads/2019/03/2021-foi-disclosure-register.pdf |
| 1404 | pdfplumber | camelot_lattice | https://www.hri.ie/HRI/media/HRI/Comms/Documents/HRI-FOI-2026-Quarterly-Disclosure-Log-Q3.pdf |
| 1404 | pdfplumber | camelot_lattice | https://www.hri.ie/HRI/media/HRI/Comms/Documents/HRI-FOI-Disclosure-Log-2025_.pdf |
| 1388 | camelot_stream | mistral_cache | https://www.hsa.ie/media/flof5wpg/disclosure-log-2027.pdf |
| 1388 | camelot_stream | mistral_cache | https://www.hsa.ie/media/ybmfiyni/disclosure-log-2026.pdf |
| 1394 | pdfplumber | camelot_lattice | https://www.hse.gov.uk/foi/disclosure-pdfs/ecp14.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/0a67d7e8-2302-44ae-9fab-e0ccdf3e5d6a/2024-Procurement.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/2b090f43-bb40-4a2d-81a4-552a274485fe/2021%20Procurement.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/3bab9558-2845-473b-8a43-78aa62d8fe66/2020%20Operations.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/3e9b0195-4257-4a6f-a801-2adb51e9ea25/2020%20Infrastructure%20.pdf |
| 1443 | pdfplumber | pymupdf | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/3edba44b-a5ad-4954-8999-a2ad1c1f8773/2024-Operations.pdf |
| 1443 | pdfplumber | camelot_stream | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/4246c772-6f58-4e12-ba52-525be4ff1402/2022%20Infrastructure.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/4e014c14-512a-4845-ae6b-99a5b6eafdf1/2021-Fleet.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/64526275-e5e4-4141-a87e-92ccf83777c2/2022%20Operations.pdf |
| 1443 | pdfplumber | camelot_stream | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/73ca7a2f-be2d-4700-baa0-2f0965c8ab89/2023%20Human%20Resources.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/90f0ac4a-a985-40d8-8132-5c5426ed7a13/2017-Finance.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/a3e05660-ace5-4e0f-8767-229957dd34fb/2020-Customer-Care.pdf |
| 1443 | camelot_stream | pdfplumber | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/b5615c0b-db31-4e0e-8521-efd05ecbd74c/674c26fc-36b0-406e-8eb3-9e70e4dfc873.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/d38d1031-f535-4586-8e55-156659d2f429/2023%20Infrastructure.pdf |
| 1443 | pdfplumber | camelot_lattice | https://www.irishrail.ie/_kontent/d2e85689-fbf9-010a-a02e-587ed94b5032/fef48a7c-0f05-40cd-b0d0-991d8554d216/2024-Fleet.pdf |
| 1471 | camelot_stream | mistral_cache | https://www.lawreform.ie/wp-content/uploads/2026/03/foi-log-10072025-1.pdf |
| 1475 | camelot_stream | camelot_lattice | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q2-2024.pdf |
| 1475 | pdfplumber | pymupdf | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q2-2026.pdf |
| 1475 | camelot_stream | camelot_lattice | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q3-2024.pdf |
| 1475 | pdfplumber | pymupdf | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q3-2026.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q4-2024.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q4-2025.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-log-Q1-2025.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-log-Q1-2026.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-log-Q2-2025.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-log-Q3-2025.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q1-2021.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q1-2022.pdf |
| 1475 | camelot_stream | pymupdf | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q1-2023.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q1-2024.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q2-2021.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q2-2022.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q2-2023.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q3-2021.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q3-2022.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q3-2023.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q4-2021.pdf |
| 1475 | camelot_stream | pdfplumber | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q4-2022.pdf |
| 1475 | camelot_stream | mistral_cache | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q4-2023.pdf |
| 1486 | pdfplumber | mistral_cache | https://www.limerick.ie/sites/default/files/media/documents/2021-02/disclosure-log-foi-2019.pdf |
| 1486 | pdfplumber | camelot_lattice | https://www.limerick.ie/sites/default/files/media/documents/2022-04/disclosure-log-jan-dec-2020.pdf |
| 1486 | pdfplumber | pymupdf | https://www.limerick.ie/sites/default/files/media/documents/2022-05/Disclosure-Log-January-December-2021.pdf |
| 1486 | pdfplumber | camelot_lattice | https://www.limerick.ie/sites/default/files/media/documents/2022-07/Disclosure%20Log%20Jan-Jun%202022_0.pdf |
| 1486 | pdfplumber | camelot_lattice | https://www.limerick.ie/sites/default/files/media/documents/2023-06/Disclosure-Log-January-December-2022.pdf |
| 1486 | pdfplumber | mistral_cache | https://www.limerick.ie/sites/default/files/media/documents/2024-07/disclosure-log-jan-dec-2023.pdf |
| 1486 | pdfplumber | camelot_lattice | https://www.limerick.ie/sites/default/files/media/documents/2024-07/disclosure-log-jan-to-june-2024_redacted.pdf |
| 1486 | pdfplumber | mistral_cache | https://www.limerick.ie/sites/default/files/media/documents/2025-02/disclosure-log-jan-to-dec-2024.pdf |
| 1486 | camelot_stream | pdfplumber | https://www.limerick.ie/sites/default/files/media/documents/2026-02/disclosure-log-jan-to-dec-2025_redacted.pdf |
| 1501 | pdfplumber | pymupdf | https://www.louthcoco.ie/media/c2rdezoc/foi-2016.pdf |
| 1501 | pdfplumber | camelot_lattice | https://www.louthcoco.ie/media/mmrfs4gu/foi-disclosure-log-2017-louth-county-council.pdf |
| 1501 | pdfplumber | mistral_cache | https://www.louthcoco.ie/media/mrgeqb1q/foi-disclosure-log-2023.pdf |
| 1496 | camelot_stream | pdfplumber | https://www.lwetb.ie/wp-content/uploads/2022/09/FOI-Log-@Q2_2022.pdf |
| 1496 | camelot_stream | pdfplumber | https://www.lwetb.ie/wp-content/uploads/2026/08/FOI-Requests-Log.pdf |
| 1505 | pdfplumber | mistral_cache | https://www.marine.ie/sites/default/files/MIFiles/Docs/Comms/foi-disclosure-log-2019-2025.pdf |
| 1505 | pdfplumber | camelot_lattice | https://www.marine.ie/sites/default/files/MIFiles/Docs_Comms/FOI Disclosure Log (2016-2018).pdf |
| 1508 | pdfplumber | camelot_lattice | https://www.mayo.ie/getmedia/d199287e-9746-49fa-af66-72997909b925/MCC-FOI-Disclosure-log-Q1-2026.pdf |
| 1562 | pdfplumber | mistral_cache | https://www.museum.ie/getmedia/c53add27-b3eb-4214-94fa-a68ebd325065/FOI-2024-Log-Non-personal.pdf |
| 1570 | pdfplumber | pymupdf | https://www.nationaltransport.ie/wp-content/uploads/2026/04/2025-Q4-FOI-Disclosure-Log.pdf |
| 1010 | pdfplumber | mistral_cache | https://www.pleanala.ie/getattachment/0c25a07b-6742-4fa6-91cd-f06a9d8e8668/FOI-Disclosure-log-2025-Q2-ENG.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getattachment/2f17f6c0-8260-4ee9-842f-241e900500b2/Disclosure-Log-2020-Q3.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getattachment/8b3be3e1-7e47-42d4-a2fd-0791a10ba6ab/Disclosure-Log-2021-Q-2.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getattachment/8e3b8699-e0a2-4a7c-bd8f-52a4f14538f5/Disclosure-Log-2020-Q2.pdf?lang=en-IE |
| 1010 | camelot_stream | pymupdf | https://www.pleanala.ie/getattachment/d065db2d-0995-4fbd-9081-d1a228972377/FOI-Disclosure-Log-2026-Q3_web.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getattachment/d37e6437-74f8-4bae-82af-21362dc8a523/Disclosure-Log-2020-Q4.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getattachment/de3b2509-7332-4819-80c5-3d41aabe826c/Disclosure-Log-2019-Q4.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getattachment/eb2c0094-d2c1-403c-8303-048ac2634dc5/Disclosure-Log-2020-Q1.pdf?lang=en-IE |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/01020af6-e81b-4ef3-9959-93656ece08a1/2015-Q3.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/1b229844-a64a-4b33-a564-13ea242f396b/2019-Q1.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/1f0ca993-b178-481a-8972-57849a81b5e4/2015-Q2.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/294adf88-7c41-4bc2-aae7-b1e6b24a7da2/2016-Q4.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/5440d179-8ff4-4493-92bf-176cd2e93429/Disclosure-log-2022-Q1.pdf |
| 1010 | pdfplumber | camelot_stream | https://www.pleanala.ie/getmedia/5d0c2ca0-549d-48cc-adb2-d70abb399fac/FOI-Disclosure-log-2025-Q1.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/608adeb0-3a47-4456-bd9a-cd344c16d678/2018-Q3.pdf |
| 1010 | camelot_stream | camelot_lattice | https://www.pleanala.ie/getmedia/61aa69a5-c9ab-4cb1-b0a3-79cb598c4901/FOI-Disclosure-Log-2026-Q1.pdf |
| 1010 | pdfplumber | mistral_cache | https://www.pleanala.ie/getmedia/77023158-c0e0-417d-a105-6602a8db5c37/FOI-Disclosure-log-2024-Q2.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/83cfd086-8ad4-415d-944c-6afcb5af6007/2015-Q1.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/aac00db7-c49c-46a3-b1c8-c07ac86346b0/2017-Q4.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/ca4bcd8a-e0e8-4e5d-bd27-d33870385e6d/2015_Q4.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/d6bfbbf5-425c-4af0-be47-38c2fbd742b4/2016-Q1.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/dfd9869d-f1fb-4fe8-b2c9-c95663fb862b/2019-Q2.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/e3049b15-8e01-4388-836a-5cb53667c531/2016-Q2.pdf |
| 1010 | camelot_stream | pdfplumber | https://www.pleanala.ie/getmedia/ea8911e0-ba3c-4042-a9ef-4dad224c7f97/FOI-Disclosure-Log-2025-Q3.pdf |
| 1010 | pdfplumber | camelot_lattice | https://www.pleanala.ie/getmedia/f4eb6f6e-497c-471a-9b00-9c44d42d30e3/2016-Q3.pdf |
| 1658 | camelot_stream | mistral_cache | https://www.rnl.ie/assets/PDFs/Public-Sector-Info/FOI-Disclosure-Log-2021.pdf |
| 1658 | pdfplumber | camelot_lattice | https://www.rnl.ie/assets/PDFs/Public-Sector-Info/FOI-Disclosure-Log-2022.pdf |
| 1711 | camelot_stream | pdfplumber | https://www.skillnetireland.ie/uploads/attachments/FOI_Disclosure_Log_%281%29.pdf |
| 1741 | camelot_stream | pdfplumber | https://www.sportireland.ie/sites/default/files/media/document/2022-08/FOI%20Disclosure%20Log%202021.pdf |
| 1741 | camelot_stream | pdfplumber | https://www.sportireland.ie/sites/default/files/media/document/2022-08/Foi%20Disclosure%20Log%202020.pdf |
| 1747 | pdfplumber | camelot_stream | https://www.stjames.ie/media/FOI Request for Deceased Patient Records August 2026.pdf |
| 1773 | pdfplumber | camelot_stream | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q1%202018.pdf |
| 1773 | pdfplumber | camelot_stream | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q1%202021.pdf |
| 1773 | pdfplumber | camelot_stream | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q2%202018.pdf |
| 1773 | camelot_stream | pdfplumber | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q2%202023.pdf |
| 1773 | pdfplumber | pymupdf | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q4%202018.pdf |
| 1773 | pdfplumber | camelot_stream | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q4%202019.pdf |
| 1834 | pdfplumber | camelot_lattice | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2019.pdf |
| 1834 | pdfplumber | camelot_lattice | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2020.pdf |
| 1834 | pdfplumber | camelot_lattice | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2021.pdf |
| 1834 | pdfplumber | camelot_lattice | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2022.pdf |
| 1834 | pdfplumber | camelot_lattice | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2023.pdf |
| 1834 | pdfplumber | camelot_lattice | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2024.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20April%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20April%202020.pdf |
| 1817 | camelot_stream | pdfplumber | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20April%202021.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20August%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20December%202018.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20December%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20February%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20February%202020.pdf |
| 1817 | camelot_stream | pdfplumber | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20February%202021.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20January%202020.pdf |
| 1817 | camelot_stream | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20January%202022.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20July%202019.pdf |
| 1817 | camelot_stream | pdfplumber | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20July%202021.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20June%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20March%202020.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20May%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20May%202021.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20May%202022.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20November%202018.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20November%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20November%202020.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20October%202018.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20October%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20October%202020.pdf |
| 1817 | camelot_stream | pdfplumber | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20October%202021.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202017.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202018.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202019.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202020.pdf |
| 1817 | camelot_stream | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202021.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-12/FOI%20Disclosure%20Log%20August%202022.pdf |
| 1817 | camelot_stream | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-12/FOI%20Disclosure%20Log%20July%202022.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2022-12/FOI%20Disclosure%20Log%20November%202022.pdf |
| 1817 | camelot_stream | pdfplumber | https://www.tipperarycoco.ie/sites/default/files/2023-02/FOI%20Disclosure%20Log%20January%202023.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2023-05/FOI%20Disclosure%20Log%20April%202023.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2023-06/FOI%20DIsclosure%20Log%20May%202023.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2023-09/FOI%20Disclosure%20Log%20August%202023.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2023-12/FOI%20Disclosure%20Log%20November%202023.pdf |
| 1817 | pdfplumber | camelot_lattice | https://www.tipperarycoco.ie/sites/default/files/2024-02/January%20Disclosure%20Log%202024.pdf |
| 1817 | pdfplumber | camelot_lattice | https://www.tipperarycoco.ie/sites/default/files/2024-04/February%20Disclosure%20Log%202024_0.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2024-05/April%20Disclosure%20Log%202024.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2024-10/September%20Disclosure%20Log%202024.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2024-12/November%20Disclosure%20Log%202024.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-02/Janaury%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-03/February%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-10/August%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-10/July%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-10/June%202025.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2025-10/May%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-10/September%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-11/October%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2025-12/November%202025.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2026-02/January.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2026-03/February.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2026-04/March.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2026-05/April.pdf |
| 1817 | pdfplumber | mistral_cache | https://www.tipperarycoco.ie/sites/default/files/2026-06/May.pdf |
| 1817 | pdfplumber | pymupdf | https://www.tipperarycoco.ie/sites/default/files/2026-07/June.pdf |
| 1817 | pdfplumber | camelot_stream | https://www.tipperarycoco.ie/sites/default/files/2026-10/September.pdf |
| 1775 | pdfplumber | mistral_cache | https://www.tudublin.ie/media/website/explore/foi/documents/TU-Dublin-2019-Disclosure-Log.pdf |
| 1775 | pdfplumber | camelot_lattice | https://www.tudublin.ie/media/website/explore/foi/documents/TU-Dublin-2023-Disclosure-Log.pdf |
| 1112 | pdfplumber | pymupdf | https://www.tusla.ie/uploads/content/2021_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | pymupdf | https://www.tusla.ie/uploads/content/2022_FOI_Disclosures_Log.pdf |
| 1112 | pdfplumber | pymupdf | https://www.tusla.ie/uploads/content/2023_FOI_Disclosures_Log.pdf |
| 1112 | camelot_stream | camelot_lattice | https://www.tusla.ie/uploads/content/2025_FOI_Disclosure_Log.pdf |
| 1112 | camelot_stream | pdfplumber | https://www.tusla.ie/uploads/content/2026_FOI_Disclosure_Log_-_Quarter_1.pdf |
| 1882 | pdfplumber | pymupdf | https://www.udaras.ie/assets/uploads/2020/06/05_FOI_Loga-Nochta-2017.pdf |
| 1574 | pdfplumber | camelot_lattice | https://www.universityofgalway.ie/media/corporateandlegalaffairs/files/2023-FOI-Disclosure-Log.pdf |
| 1574 | pdfplumber | camelot_lattice | https://www.universityofgalway.ie/media/corporateandlegalaffairs/files/FOI-Disclosure-Log-2024.pdf |
| 1876 | pdfplumber | pymupdf | https://www.wicklow.ie/Portals/0/Documents/Governance/About-Freedom-of-Information/Disclosure Log 2016.pdf |
| 1876 | pdfplumber | camelot_lattice | https://www.wicklow.ie/Portals/0/Documents/Governance/About-Freedom-of-Information/Disclosure log 2017.pdf |
| 1876 | pdfplumber | camelot_lattice | https://www.wicklow.ie/Portals/0/adam/Documents/0eq7S5r0oUqeZl-pfCg78Q/Link/Disclosure Log 2025 12 mths.pdf |
| 1876 | pdfplumber | camelot_lattice | https://www.wicklow.ie/Portals/0/adam/Documents/_2QuxduQCEGNV7u6vpJU5Q/Link/Disclosure Log 2024.pdf |
| 1876 | pdfplumber | camelot_lattice | https://www.wicklow.ie/Portals/0/adam/Documents/cvn0KqS04kWf7BaRIeWjsg/Link/Disclosure log 2020-2.pdf |
| 1876 | pdfplumber | camelot_lattice | https://www.wicklow.ie/Portals/0/adam/Documents/nxlX4oak5Eesd0IW6ayoBQ/Link/Disclosure Log 12 months 2023.pdf |

### TableStructureUnreliable per body

| public_body_id | files |
|---|---|
| 1010 | 17 |
| 1024 | 2 |
| 1038 | 1 |
| 1047 | 1 |
| 1052 | 2 |
| 1053 | 1 |
| 1089 | 1 |
| 1093 | 2 |
| 1104 | 4 |
| 1107 | 1 |
| 1112 | 2 |
| 1122 | 5 |
| 1149 | 1 |
| 1151 | 8 |
| 1153 | 3 |
| 1163 | 3 |
| 1164 | 2 |
| 1169 | 1 |
| 1176 | 10 |
| 1177 | 2 |
| 1194 | 1 |
| 1196 | 9 |
| 1198 | 6 |
| 1200 | 12 |
| 1202 | 1 |
| 1204 | 12 |
| 1205 | 4 |
| 1207 | 2 |
| 1208 | 3 |
| 1210 | 14 |
| 1212 | 19 |
| 1213 | 28 |
| 1235 | 3 |
| 1244 | 2 |
| 1245 | 7 |
| 1293 | 11 |
| 1295 | 2 |
| 1298 | 1 |
| 1335 | 9 |
| 1342 | 2 |
| 1389 | 2 |
| 1390 | 5 |
| 1391 | 1 |
| 1392 | 5 |
| 1394 | 2 |
| 1437 | 3 |
| 1438 | 3 |
| 1442 | 1 |
| 1443 | 48 |
| 1455 | 1 |
| 1456 | 6 |
| 1475 | 13 |
| 1484 | 1 |
| 1486 | 9 |
| 1493 | 1 |
| 1501 | 5 |
| 1505 | 4 |
| 1508 | 1 |
| 1544 | 2 |
| 1552 | 1 |
| 1559 | 1 |
| 1562 | 1 |
| 1568 | 1 |
| 1570 | 19 |
| 1571 | 3 |
| 1573 | 1 |
| 1574 | 4 |
| 1590 | 1 |
| 1594 | 1 |
| 1602 | 2 |
| 1653 | 1 |
| 1655 | 1 |
| 1658 | 4 |
| 1679 | 5 |
| 1711 | 1 |
| 1732 | 1 |
| 1741 | 1 |
| 1747 | 2 |
| 1752 | 1 |
| 1771 | 4 |
| 1773 | 6 |
| 1775 | 5 |
| 1786 | 2 |
| 1817 | 63 |
| 1834 | 4 |
| 1867 | 2 |
| 1868 | 5 |
| 1870 | 2 |
| 1876 | 9 |
| 1882 | 3 |
| TOTAL | 487 |
