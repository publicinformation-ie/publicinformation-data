# Role gate: extractor changes, withheld files, body falls

Generated from the Task 2 snapshot (before) and steps/ (after). Records = canonicalize_rows records; errors = canonicalize_rows errors.

## Files whose pdf_extractor changed

| body | before | after | records before->after | errors before->after | withheld (failed checks) | file |
|---|---|---|---|---|---|---|
| 1010 | mistral_cache | pdfplumber | 0->0 | 0->0 | split_word_rate,role_contamination | https://www.pleanala.ie/getattachment/0c25a07b-6742-4fa6-91cd-f06a9d8e8668/FOI-Disclosure-log-2025-Q2-ENG.pdf?lang=en-IE |
| 1053 | pdfplumber | mistral_cache | 17->0 | 0->0 | role_contamination,anchored_row_share | https://bim.ie/wp-content/uploads/2024/11/FOI-Log-2023.pdf |
| 1122 | pymupdf | camelot_lattice | 0->0 | 0->0 | column_type_purity,role_contamination,anchored_row_share | https://www.cityofdublinetb.ie/media/2025-Quarters-1-4-FOI-Disclosure-Log.pdf |
| 1122 | camelot_lattice | camelot_stream | 20->0 | 9->0 | width_uniformity,fragment_share,column_type_purity,anchored_row_share | https://www.cityofdublinetb.ie/media/City-of-Dublin-FOI-Disclosure-Log-2023-(1).pdf |
| 1122 | pdfplumber | camelot_stream | 6->0 | 3->0 | width_uniformity,fragment_share,column_type_purity,anchored_row_share | https://www.cityofdublinetb.ie/media/City-of-Dublin-FOI-Disclosure-Log-Q3-Q4-2022.pdf |
| 1122 | pdfplumber | camelot_stream | 25->0 | 23->0 | width_uniformity,fragment_share,anchored_row_share | https://www.cityofdublinetb.ie/media/Disclosure-Log-2021.pdf |
| 1122 | pdfplumber | camelot_stream | 0->0 | 0->0 | width_uniformity,fragment_share,anchored_row_share | https://www.cityofdublinetb.ie/media/Disclosure-Log-2022-Q1-and-Q2.pdf |
| 1122 | pdfplumber | pymupdf | 27->0 | 20->0 | width_uniformity,anchored_row_share | https://www.cityofdublinetb.ie/media/FOI-Disclosure-Log-2024-2.pdf |
| 1151 | camelot_lattice | camelot_stream | 14->0 | 14->0 | width_uniformity,fragment_share,anchored_row_share | https://www.comreg.ie/media/2016/03/Disclosure-Log-2015-Publication-1.pdf |
| 1153 | pdfplumber | camelot_stream | 27->0 | 0->0 | width_uniformity,fragment_share,role_contamination,anchored_row_share | https://www.cru.ie/documents/29700/2024_FOI_Disclosure_Log.pdf |
| 1153 | pdfplumber | camelot_stream | 53->0 | 0->0 | width_uniformity,fragment_share,anchored_row_share | https://www.cru.ie/documents/30609/2025_FOI_Disclosure_Log.pdf |
| 1163 | pymupdf | mistral_cache | 0->0 | 0->0 | split_word_rate | https://www.corkcoco.ie/sites/default/files/2023-01/freedom-of-information-disclosure-log-2021-pdf.pdf |
| 1163 | pymupdf | camelot_lattice | 0->0 | 0->0 | split_word_rate | https://www.corkcoco.ie/sites/default/files/2023-06/freedom-of-information-disclosure-log-2022-pdf.pdf |
| 1177 | pymupdf | camelot_lattice | 15->0 | 7->0 | width_uniformity,fragment_share | https://crawfordartgallery.ie/wp-content/uploads/20260527_FOI-LOG.pdf |
| 1200 | pdfplumber | pymupdf | 86->0 | 30->0 | role_contamination | https://assets.gov.ie/static/documents/foi-disclosure-log-2019-c85f2f5e-3495-405f-a35d-4bb31b1b7bd4.pdf |
| 1200 | pdfplumber | camelot_stream | 23->0 | 0->0 | fragment_share,role_contamination,anchored_row_share | https://assets.gov.ie/static/documents/foi-disclosure-log-q4-2021.pdf |
| 1202 | mistral_cache | pdfplumber | 0->0 | 0->0 | width_uniformity,fragment_share,anchored_row_share | https://enterprise.gov.ie/en/publications/publication-files/foi-log-2025.pdf |
| 1205 | camelot_stream | mistral_cache | 0->0 | 0->0 | width_uniformity,role_contamination | https://assets.gov.ie/static/documents/dfheris-foi-logs-april-to-june-2024.pdf |
| 1207 | camelot_lattice | mistral_cache | 121->120 | 1->0 |  | https://assets.gov.ie/static/documents/1f919c9b/Q2._FOI_Disclosure_Log_April_to_June_2025.pdf |
| 1210 | pymupdf | camelot_lattice | 21->20 | 1->0 |  | https://assets.gov.ie/static/documents/foi-requests-january-march-2022.pdf |
| 1210 | pdfplumber | camelot_lattice | 13->0 | 13->0 | role_contamination | https://assets.gov.ie/static/documents/foi-requests-july-december-2017.pdf |
| 1210 | pdfplumber | camelot_stream | 7->0 | 5->0 | width_uniformity,fragment_share,split_word_rate,anchored_row_share | https://assets.gov.ie/static/documents/foi-requests-july-september-2018.pdf |
| 1212 | pymupdf | mistral_cache | 0->0 | 0->0 | width_uniformity,fragment_share | https://assets.gov.ie/static/documents/2371ea98/Freedom_of_Information_Quarter_3_Requests_2025.pdf |
| 1213 | camelot_stream | mistral_cache | 79->80 | 0->0 |  | https://assets.gov.ie/static/documents/q2-2016-foi-disclosure-log.pdf |
| 1213 | pdfplumber | mistral_cache | 33->69 | 0->0 |  | https://assets.gov.ie/static/documents/q4-2016-foi-disclosure-log.pdf |
| 1213 | mistral_cache | camelot_stream | 0->0 | 0->0 | split_word_rate | https://assets.gov.ie/static/documents/q4-2017-foi-disclosure-log.pdf |
| 1293 | pymupdf | camelot_lattice | 9->9 | 0->0 |  | https://www.fspo.ie/documents/FOI-Disclosure-Log-2021.pdf |
| 1295 | pdfplumber | mistral_cache | 6->123 | 122->0 |  | https://www.fingal.ie/sites/default/files/2024-07/foi-disclosure-log-2023.pdf |
| 1295 | camelot_stream | mistral_cache | 141->139 | 141->0 |  | https://www.fingal.ie/sites/default/files/2026-01/2024-foi-disclosure-log.pdf |
| 1335 | camelot_lattice | mistral_cache | 45->44 | 2->1 |  | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/FOI-Disclosure-Log-January-December-2018_1.pdf |
| 1342 | pdfplumber | mistral_cache | 199->0 | 3->0 | role_contamination,anchored_row_share | http://www.galway.ie/sites/default/files/2025-06/FOI%20Disclosure%20log%202019.pdf |
| 1388 | pdfplumber | camelot_stream | 25->0 | 0->0 |  | https://www.hsa.ie/media/51rpmq2n/foi-disclosure-log-2017.pdf |
| 1388 | pdfplumber | camelot_stream | 25->0 | 0->0 |  | https://www.hsa.ie/media/hf4e0xmx/foi-disclosure-log-2016.pdf |
| 1388 | pdfplumber | mistral_cache | 23->0 | 0->0 | role_contamination | https://www.hsa.ie/media/lnmki5ak/foi-disclosure-log-2020.pdf |
| 1388 | pdfplumber | mistral_cache | 10->0 | 0->0 | role_contamination | https://www.hsa.ie/media/mqhlwofq/foi-disclosure-log-2019.pdf |
| 1389 | pdfplumber | camelot_lattice | 17->0 | 0->0 |  | https://www.coru.ie/media/02fazylt/foi-disclosure-log-2024.pdf |
| 1389 | camelot_lattice | pdfplumber | 0->0 | 0->0 | width_uniformity,fragment_share,anchored_row_share | https://www.coru.ie/media/vdwdvd42/coru-foi-log-2022.pdf |
| 1471 | mistral_cache | pymupdf | 22->0 | 0->0 | width_uniformity,fragment_share,column_type_purity,anchored_row_share | https://www.lawreform.ie/wp-content/uploads/2026/03/foi-log-10072025-1.pdf |
| 1475 | camelot_lattice | mistral_cache | 0->23 | 0->0 |  | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Disclosure-Log/Disclosure-Log-Q2-2024.pdf |
| 1475 | camelot_stream | mistral_cache | 0->0 | 0->0 | width_uniformity | https://www.leitrim.ie/Council/Corporate-Governance/Freedom-of-Information/Freedom-of-Information-Requests/Disclosure-Log-Q4-2021.pdf |
| 1484 | camelot_lattice | pdfplumber | 0->0 | 0->0 | width_uniformity,fragment_share,anchored_row_share | https://lcetb.ie/wp-content/uploads/2026/06/FOI-DISCLOSURE-LOG_2025.pdf |
| 1501 | pdfplumber | camelot_lattice | 107->0 | 0->0 | role_contamination,anchored_row_share | https://www.louthcoco.ie/media/0d3hkhve/foi-disclosures-log-2019.pdf |
| 1501 | pdfplumber | camelot_stream | 65->0 | 0->0 | width_uniformity,fragment_share,column_type_purity,role_contamination,anchored_row_share | https://www.louthcoco.ie/media/bwcfc1mo/foi-disclosures-log-2020.pdf |
| 1501 | pdfplumber | pymupdf | 36->0 | 0->0 | anchored_row_share | https://www.louthcoco.ie/media/c2rdezoc/foi-2016.pdf |
| 1501 | pdfplumber | camelot_lattice | 88->0 | 0->0 | anchored_row_share | https://www.louthcoco.ie/media/jgmmylj5/foi-disclosure-log-2021.pdf |
| 1501 | pdfplumber | pymupdf | 64->0 | 2->0 | width_uniformity | https://www.louthcoco.ie/media/mmrfs4gu/foi-disclosure-log-2017-louth-county-council.pdf |
| 1501 | pdfplumber | camelot_lattice | 102->98 | 0->0 |  | https://www.louthcoco.ie/media/xiwfstmv/foi-disclosure-log-2018-for-web-copy.pdf |
| 1508 | pdfplumber | camelot_stream | 34->35 | 0->35 |  | https://www.mayo.ie/getmedia/137e2288-371f-4f9c-9127-ec488798faac/Disclosure-Log-Q4-2023.pdf |
| 1508 | pdfplumber | camelot_stream | 32->0 | 0->0 | width_uniformity,fragment_share,split_word_rate | https://www.mayo.ie/getmedia/1d36077f-63b0-4f22-8d19-06e739f1e0d6/Disclosure-Log-Q1-2025.pdf |
| 1508 | pdfplumber | camelot_stream | 42->43 | 0->43 |  | https://www.mayo.ie/getmedia/22f4ee22-443f-440d-9186-e8d8907f67d3/Disclosure-Log-Q1-2024.pdf |
| 1508 | pdfplumber | camelot_stream | 27->27 | 0->0 |  | https://www.mayo.ie/getmedia/25fd167c-a70c-4a45-930e-3ddb56e8cbea/FOI-Disclosure-Log-Q3-2024.pdf |
| 1508 | pdfplumber | camelot_stream | 33->34 | 0->4 |  | https://www.mayo.ie/getmedia/36f3b42a-43cd-46af-8093-bdc80fc93b4e/MCC-FOI-Disclosure-Log-Q4-2025.pdf |
| 1508 | pdfplumber | camelot_stream | 49->0 | 0->0 |  | https://www.mayo.ie/getmedia/4ac9f123-e7de-4e07-8d25-90d5d973ae01/Disclosure-Log-Q3-2023.pdf |
| 1508 | pdfplumber | camelot_stream | 31->0 | 0->0 | width_uniformity,split_word_rate,role_contamination | https://www.mayo.ie/getmedia/5bd554a5-67ff-4c94-b0ad-8f9b325e4534/FOI-Disclosure-Log-Q4-2024.pdf |
| 1508 | pdfplumber | camelot_stream | 52->46 | 0->0 |  | https://www.mayo.ie/getmedia/b5612d9f-79d9-427e-865c-029d4f713e96/FOI-Disclosure-Log-Q3-2025.pdf |
| 1574 | camelot_lattice | mistral_cache | 48->48 | 0->0 |  | https://www.universityofgalway.ie/media/corporateandlegalaffairs/files/FOI-Disclosure-Log-2024.pdf |
| 1594 | camelot_stream | pdfplumber | 0->0 | 0->0 | width_uniformity,fragment_share,column_type_purity,role_contamination | https://assets.gov.ie/static/documents/5f66a911/Non_Personal_FOI_Requests_Q3_2025.pdf |
| 1594 | pdfplumber | camelot_lattice | 19->0 | 1->0 | role_contamination | https://assets.gov.ie/static/documents/AIE_Requests_2024.pdf |
| 1594 | pdfplumber | camelot_stream | 37->0 | 8->0 | width_uniformity,fragment_share,role_contamination,anchored_row_share | https://assets.gov.ie/static/documents/aie-requests-2021.pdf |
| 1594 | pdfplumber | camelot_lattice | 118->0 | 0->0 | role_contamination | https://assets.gov.ie/static/documents/non-personal-foi-requests-2017.pdf |
| 1594 | pdfplumber | pymupdf | 156->0 | 3->0 | role_contamination | https://assets.gov.ie/static/documents/non-personal-foi-requests-2019.pdf |
| 1647 | pdfplumber | camelot_lattice | 8->0 | 0->0 | role_contamination | http://www.probation.ie/EN/PB/0/50BB0DA19912894F802586BD0048CAEC/$File/2020 non Personal FOI logs.pdf |
| 1655 | camelot_lattice | pymupdf | 37->39 | 33->0 |  | https://about.rte.ie/wp-content/uploads/2022/01/RTE-FOI-DISCLOSURE-LOG-Q3-2021.pdf |
| 1658 | camelot_lattice | pymupdf | 18->19 | 3->4 |  | https://www.rnl.ie/assets/PDFs/Public-Sector-Info/FOI-Disclosure-Log-2022.pdf |
| 1752 | pdfplumber | camelot_lattice | 12->0 | 4->0 |  | https://www.stvincents.ie/app/uploads/2019/03/FOI-Disclosure-Log-2018-Publication-Scheme-2.pdf |
| 1817 | mistral_cache | pymupdf | 0->0 | 0->0 | split_word_rate | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20April%202020.pdf |
| 1817 | mistral_cache | pymupdf | 0->0 | 7->0 | split_word_rate,role_contamination | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20December%202018.pdf |
| 1817 | mistral_cache | pymupdf | 0->0 | 0->0 | split_word_rate | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20February%202019.pdf |
| 1817 | pymupdf | mistral_cache | 0->0 | 0->0 | width_uniformity | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20February%202020.pdf |
| 1817 | mistral_cache | camelot_stream | 0->0 | 0->0 | width_uniformity,fragment_share | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20January%202022.pdf |
| 1817 | pdfplumber | mistral_cache | 1->0 | 13->0 | role_contamination | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20March%202019.pdf |
| 1817 | pdfplumber | mistral_cache | 14->13 | 3->0 |  | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20May%202019.pdf |
| 1817 | camelot_stream | mistral_cache | 0->0 | 0->0 | width_uniformity,split_word_rate | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202021.pdf |
| 1834 | pdfplumber | camelot_stream | 73->0 | 3->0 | fragment_share,column_type_purity,role_contamination,anchored_row_share | https://www.tcd.ie/media/tcd/infocompliance/pdfs/FOI-Disclosure-Log-2017.pdf |
| 1868 | camelot_lattice | pdfplumber | 4->0 | 3->0 | width_uniformity,fragment_share,column_type_purity,anchored_row_share | https://westerndevelopment.ie/wp-content/uploads/2021/02/2018-FOI-published-list.pdf |

75 files changed extractor.

## Bodies whose record count fell, with the withheld files that explain it

| body | records before->after | lost to newly withheld files | lost elsewhere (net) | newly withheld files: (before recs, failed checks) |
|---|---|---|---|---|
| 1594 | 1382->661 | 721 | 0 | AIE_Requests_2024.pdf (19, role_contamination); aie-requests-2021.pdf (37, width_uniformity+fragment_share+role_contamination+anchored_row_share); non-personal-foi-requests-2017.pdf (118, role_contamination); non-personal-foi-requests-2018.pdf (152, role_contamination); non-personal-foi-requests-2020.pdf (141, role_contamination); non-personal-foi-requests-2019.pdf (156, role_contamination); non-personal-foi-requests-q1-2024.pdf (68, role_contamination); non-personal-foi-requests-q2-2024.pdf (30, role_contamination) |
| 1501 | 1088->628 | 456 | 4 | foi-2016.pdf (36, anchored_row_share); foi-disclosure-log-2017-louth-county-council. (64, width_uniformity); foi-disclosures-log-2020.pdf (65, width_uniformity+fragment_share+column_type_purity+role_contamination+anchored_row_share); foi-disclosures-log-2019.pdf (107, role_contamination+anchored_row_share); foi-disclosure-log-2021.pdf (88, anchored_row_share); foi-disclosure-log-2023.pdf (96, role_contamination+anchored_row_share) |
| 1508 | 1138->864 | 222 | 52 | FOI-Disclosure-Log-Q4-2024.pdf (31, width_uniformity+split_word_rate+role_contamination); Disclosure-Log-Q1-2025.pdf (32, width_uniformity+fragment_share+split_word_rate); Disclosure-Log-Q2-2025.pdf (38, role_contamination); Disclosure-Log-Q2-2024.pdf (53, role_contamination); FOI_DisclosureLog_2023_Q2.pdf (33, role_contamination); FOI_DisclosureLog_2023_Q1.pdf (35, role_contamination) |
| 1153 | 328->79 | 249 | 0 | 2025_FOI_Disclosure_Log.pdf (53, width_uniformity+fragment_share+anchored_row_share); 2024_FOI_Disclosure_Log.pdf (27, width_uniformity+fragment_share+role_contamination+anchored_row_share); 2023-FOI-Disclosure-Log_1_1_3.pdf (39, anchored_row_share); CRU_2022_FOI_Discloure_Log.pdf (48, anchored_row_share); CRU_2021_FOI_Disclosure_Log_1.pdf (25, anchored_row_share); 2026_FOI_Disclosure_Log_1.pdf (57, role_contamination) |
| 1342 | 1389->1190 | 199 | 0 | FOI%20Disclosure%20log%202019.pdf (199, role_contamination+anchored_row_share) |
| 1244 | 679->526 | 153 | 0 | 2021%20Freedom%20of%20Information%20Disclosur (153, role_contamination+anchored_row_share) |
| 1200 | 813->704 | 109 | 0 | foi-disclosure-log-2019-c85f2f5e-3495-405f-a3 (86, role_contamination); foi-disclosure-log-q4-2021.pdf (23, fragment_share+role_contamination+anchored_row_share) |
| 1390 | 767->663 | 104 | 0 | FOI-Disclosure-Log-2019.pdf (55, anchored_row_share); FOI-Disclosure-Log-2018.pdf (49, anchored_row_share) |
| 1388 | 224->125 | 49 | 50 | foi-disclosure-log-2020.pdf (23, role_contamination); foi-disclosure-log-2019.pdf (10, role_contamination); foi-disclosure-log-2018.pdf (16, role_contamination) |
| 1122 | 115->18 | 97 | 0 | City-of-Dublin-ETB-FOI-Disclosure-Log-Q1-and- (19, role_contamination); FOI-Disclosure-Log-2024-2.pdf (27, width_uniformity+anchored_row_share); City-of-Dublin-FOI-Disclosure-Log-2023-(1).pd (20, width_uniformity+fragment_share+column_type_purity+anchored_row_share); City-of-Dublin-FOI-Disclosure-Log-Q3-Q4-2022. (6, width_uniformity+fragment_share+column_type_purity+anchored_row_share); Disclosure-Log-2021.pdf (25, width_uniformity+fragment_share+anchored_row_share) |
| 1655 | 1584->1502 | 84 | -2 | RTE-FOI-DISCLOSURE-LOG-Q2-2020.pdf (22, role_contamination); rte-freedom-of-information-q4-disclosure-log- (62, role_contamination) |
| 1834 | 727->654 | 73 | 0 | FOI-Disclosure-Log-2017.pdf (73, fragment_share+column_type_purity+role_contamination+anchored_row_share) |
| 1471 | 22->0 | 22 | 0 | foi-log-10072025-1.pdf (22, width_uniformity+fragment_share+column_type_purity+anchored_row_share) |
| 1052 | 203->182 | 21 | 0 | bord-bia-foi-disclosure-log-2023.pdf (21, role_contamination) |
| 1210 | 446->425 | 20 | 1 | foi-requests-july-september-2018.pdf (7, width_uniformity+fragment_share+split_word_rate+anchored_row_share); foi-requests-july-december-2017.pdf (13, role_contamination) |
| 1164 | 75->55 | 20 | 0 | FOI-Disclosure-Log-2018.pdf (12, anchored_row_share); FOI-Disclosure-Log-2019.pdf (8, role_contamination+anchored_row_share) |
| 1053 | 92->75 | 17 | 0 | FOI-Log-2023.pdf (17, role_contamination+anchored_row_share) |
| 1389 | 30->13 | 0 | 17 |  |
| 1177 | 15->0 | 15 | 0 | 20260527_FOI-LOG.pdf (15, width_uniformity+fragment_share) |
| 1151 | 206->192 | 14 | 0 | Disclosure-Log-2015-Publication-1.pdf (14, width_uniformity+fragment_share+anchored_row_share) |
| 1752 | 12->0 | 0 | 12 |  |
| 1882 | 110->98 | 12 | 0 | Loga-Nochta-2020-ASF-.pdf (12, anchored_row_share) |
| 1647 | 31->23 | 8 | 0 | 2020 non Personal FOI logs.pdf (8, role_contamination) |
| 1868 | 27->21 | 6 | 0 | 2018-FOI-published-list.pdf (4, width_uniformity+fragment_share+column_type_purity+anchored_row_share); 2020-FOI-published-list.pdf (2, anchored_row_share) |
| 1817 | 1054->1052 | 1 | 1 | FOI%20Disclosure%20Log%20March%202019.pdf (1, role_contamination); FOI%20Disclosure%20Log%20September%202018.pdf (0, role_contamination); FOI%20Disclosure%20Log%20December%202018.pdf (0, split_word_rate+role_contamination) |
| 1207 | 4546->4545 | 0 | 1 |  |
| 1335 | 692->691 | 0 | 1 |  |

Negative 'elsewhere' means other files of that body gained records (extractor changes, header fixes). Positive means unexplained loss.

## Bodies whose record count rose

| body | before->after |
|---|---|
| 1295 | 878->993 |
| 1864 | 6->120 |
| 1213 | 2524->2561 |
| 1475 | 118->141 |
| 1658 | 96->97 |

## Files with errors on >=20% of rows (after)

| body | file | extractor | records | errors | before rec/err | status |
|---|---|---|---|---|---|---|
| 1052 | https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/disclosure-log-2015.pdf | camelot_stream | 5 | 1 | 5/1 | same as before (unfixed) |
| 1104 | https://www.centralbank.ie/docs/default-source/tns/about---tns/freedom-of-information/disclosure-logs/freedom-of-information-disclosure-log-2023-(non-personal-requests).pdf?sfvrsn=81cf621a_9 | mistral_cache | 69 | 16 | 69/16 | withheld |
| 1817 | https://www.tipperarycoco.ie/sites/default/files/2022-12/FOI%20Disclosure%20Log%20July%202022.pdf | mistral_cache | 2 | 1 | 2/1 | same as before (unfixed) |
| 1295 | https://www.fingal.ie/sites/default/files/2019-03/FOI%20Disclosure%20Log%202016.pdf | pdfplumber | 119 | 268 | 119/268 | same as before (unfixed) |
| 1437 | https://www.fiscalcouncil.ie/wp-content/uploads/2021/03/FOI-Disclosure-Log-2016.pdf | pdfplumber | 2 | 2 | 2/2 | same as before (unfixed) |
| 1561 | https://nationalmilkagency.ie/wp-content/uploads/2026/04/FOI-Disclosure-Log-April-2026.pdf | pdfplumber | 11 | 11 | 11/11 | same as before (unfixed) |
| 1508 | https://www.mayo.ie/getmedia/22f4ee22-443f-440d-9186-e8d8907f67d3/Disclosure-Log-Q1-2024.pdf | camelot_stream | 43 | 43 | 42/0 | changed |
| 1508 | https://www.mayo.ie/getmedia/137e2288-371f-4f9c-9127-ec488798faac/Disclosure-Log-Q4-2023.pdf | camelot_stream | 35 | 35 | 34/0 | changed |
| 1562 | https://www.museum.ie/getmedia/1dd83c82-3ce7-4758-ac9c-262b9844c306/FOI-Log-2025_.xlsx | None | 14 | 12 | 14/12 | same as before (unfixed) |
| 1335 | https://www.failteireland.ie/FailteIreland/media/WebsiteStructure/Documents/4_Corporate_Documents/FOI-Disclosure-Log-January-December-2019.pdf | pdfplumber | 40 | 13 | 40/13 | same as before (unfixed) |
| 1438 | https://www.ihrec.ie/downloads/Freedom-of-Information-Disclosure-Log-Q3-2024.pdf | pdfplumber | 0 | 5 | 0/5 | same as before (unfixed) |
| 1200 | https://assets.gov.ie/static/documents/foi-disclosure-log-q1-2022-6670e4aa-fb1f-4dc8-810b-c4f5c5b5e75d.pdf | pdfplumber | 34 | 16 | 34/16 | same as before (unfixed) |
| 1200 | https://assets.gov.ie/static/documents/foi-disclosure-log-q2-2022-60673303-19ed-4235-b3a5-d7da4aeb5064.pdf | pdfplumber | 25 | 13 | 25/13 | same as before (unfixed) |
| 1622 | https://assets.gov.ie/static/documents/foi-disclosures-log.pdf | pdfplumber | 4 | 6 | 4/6 | same as before (unfixed) |
| 1573 | https://www.nui.ie/app/uploads/2026/03/FOI-Disclosure-Log.pdf | pdfplumber | 9 | 9 | 9/9 | same as before (unfixed) |
| 1758 | https://a.storyblok.com/f/46384/x/ac3c8cd7ee/foi-disclosure-log-2018-2020.pdf | camelot_stream | 0 | 3 | 0/3 | same as before (unfixed) |
| 1245 | https://www.dkit.ie/system/files/2026-03/FOI-Disclosure-Log-2018.pdf | pdfplumber | 5 | 1 | 5/1 | same as before (unfixed) |
| 1392 | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---october-to-december-2025-q4.pdf?sfvrsn=c8d370d8_5 | mistral_cache | 16 | 9 | 16/9 | same as before (unfixed) |
| 1392 | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---july-to-september-2025-q3.pdf?sfvrsn=8602a498_5 | mistral_cache | 21 | 11 | 21/11 | same as before (unfixed) |
| 1392 | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---april-to-june-2025-q2.pdf?sfvrsn=983dbd6e_7 | mistral_cache | 18 | 7 | 18/7 | same as before (unfixed) |
| 1392 | https://assets.hpra.ie/data/docs/default-source/corporate/freedom-of-information/foi-disclosure-log---january-to-march-2026-q1---updated.pdf?sfvrsn=560d88c8_7 | pdfplumber | 9 | 4 | 9/4 | same as before (unfixed) |
| 1335 | https://assets-eu-01.kc-usercontent.com:443/5608854e-b2c7-0144-a5f6-88a7e629b0a4/7e855dcd-fe22-4f8f-b1f2-4d4894b05328/disclosure-foi-2019.pdf | pdfplumber | 40 | 13 | 40/13 | same as before (unfixed) |
| 1164 | https://www.corketb.ie/wp-content/uploads/2026/06/FOI-Disclosure-Log-2023.pdf | pdfplumber | 18 | 10 | 18/10 | same as before (unfixed) |
| 1164 | https://www.corketb.ie/wp-content/uploads/2026/06/FOI-Disclosure-Log-2024.pdf | pdfplumber | 12 | 5 | 12/5 | same as before (unfixed) |
| 1587 | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2025.pdf | pdfplumber | 5 | 1 | 5/1 | same as before (unfixed) |
| 1587 | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2022.pdf | pdfplumber | 4 | 2 | 4/2 | same as before (unfixed) |
| 1587 | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2023.pdf | pdfplumber | 6 | 3 | 6/3 | same as before (unfixed) |
| 1587 | https://www.nmbi.ie/NMBI/media/NMBI/Freedom-of-Information-Disclosure-Log-2021.pdf | pdfplumber | 7 | 3 | 7/3 | same as before (unfixed) |
| 1460 | https://kcetb.ie/wp-content/uploads/2026/01/Disclosure-Log-2025.pdf | pdfplumber | 6 | 3 | 6/3 | same as before (unfixed) |
| 1786 | https://www.housingagency.ie/wp-content/uploads/2019/03/2016-foi-disclosure-register.pdf | pdfplumber | 6 | 3 | 6/3 | same as before (unfixed) |
| 1786 | https://www.housingagency.ie/wp-content/uploads/2026/05/2022_Disclosure_Register.pdf | pdfplumber | 42 | 14 | 42/14 | same as before (unfixed) |
| 1455 | https://kwetb.ie/wp-content/uploads/2023/08/KWETB-FOI-DISCLOSURE-LOG-2021-1.pdf | pdfplumber | 12 | 4 | 12/4 | same as before (unfixed) |
| 1455 | https://kwetb.ie/wp-content/uploads/2023/08/KWETB-FOI-DISCLOSURE-LOG-2020-1.pdf | pdfplumber | 11 | 3 | 11/3 | same as before (unfixed) |
| 1153 | https://www.cru.ie/documents/28330/CRU_2017_FOI_Disclosure_Log.pdf | pdfplumber | 13 | 4 | 13/4 | same as before (unfixed) |
| 1658 | https://www.rnl.ie/assets/PDFs/Public-Sector-Info/FOI-Disclosure-Log-2022.pdf | pymupdf | 19 | 4 | 18/3 | changed |
| 1773 | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q2%202024.pdf | pdfplumber | 1 | 2 | 1/2 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q3%202023.pdf | pdfplumber | 1 | 2 | 1/2 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q1%202022.pdf | pdfplumber | 1 | 2 | 1/2 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q2%202022.pdf | pdfplumber | 1 | 2 | 1/2 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q3%202022.pdf | pdfplumber | 1 | 3 | 1/3 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/FOIDecisions/FOI%20Disclosure%20Log%20Q4%202022.pdf | pdfplumber | 1 | 3 | 1/3 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Freedom%20of%20Information/2021/FOI%20Disclosure%20Log%20Q4%202021.pdf | pdfplumber | 1 | 3 | 1/3 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q1%202020.pdf | pdfplumber | 1 | 2 | 1/2 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q3%202019.pdf | pdfplumber | 1 | 1 | 1/1 | same as before (unfixed) |
| 1773 | https://www.taxappeals.ie/_fileupload/Purchases/PromptPayments/FOI%20Disclosure%20Log%20Q4%202018.pdf | pdfplumber | 2 | 1 | 2/1 | same as before (unfixed) |
| 1775 | https://www.tudublin.ie/media/website/explore/foi/documents/TU-Dublin-2021-Disclosure-Log.pdf | pdfplumber | 45 | 12 | 45/12 | same as before (unfixed) |
| 1775 | https://www.tudublin.ie/media/website/explore/foi/documents/TU-Dublin-2020-Disclosure-Log.pdf | pdfplumber | 29 | 6 | 29/6 | same as before (unfixed) |
| 1868 | https://westerndevelopment.ie/wp-content/uploads/2021/02/2019-FOI-published-list.pdf | pdfplumber | 1 | 1 | 1/1 | same as before (unfixed) |
| 1868 | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2021.pdf | mistral_cache | 5 | 2 | 5/2 | same as before (unfixed) |
| 1868 | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2022.pdf | mistral_cache | 3 | 2 | 3/2 | same as before (unfixed) |
| 1868 | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2023.pdf | mistral_cache | 5 | 4 | 5/4 | same as before (unfixed) |
| 1868 | https://westerndevelopment.ie/wp-content/uploads/2025/06/FOI-2024.pdf | camelot_stream | 7 | 6 | 7/6 | same as before (unfixed) |
| 1010 | https://www.pleanala.ie/getmedia/1f0ca993-b178-481a-8972-57849a81b5e4/2015-Q2.pdf | camelot_lattice | 6 | 2 | 6/2 | same as before (unfixed) |
| 1817 | https://www.tipperarycoco.ie/sites/default/files/2026-07/June.pdf | pymupdf | 6 | 3 | 6/3 | same as before (unfixed) |
| 1817 | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20September%202020.pdf | mistral_cache | 0 | 3 | 0/3 | same as before (unfixed) |
| 1817 | https://www.tipperarycoco.ie/sites/default/files/2022-07/FOI%20Disclosure%20Log%20May%202018.pdf | pdfplumber | 9 | 2 | 9/2 | same as before (unfixed) |
| 1679 | https://www.grireland.ie/globalassets/rescource-centre/documents/foi-publication-scheme/disclosure-log-2024.pdf | pdfplumber | 18 | 6 | 18/6 | same as before (unfixed) |
| 1655 | https://about.rte.ie/wp-content/uploads/2021/06/RTE-FOI-DISCLOSURE-LOG-Q4-2020-1.pdf | camelot_lattice | 54 | 30 | 54/65 | changed |
| 1122 | https://www.cityofdublinetb.ie/media/Disclosure-Log-2020.pdf | pdfplumber | 18 | 20 | 18/20 | same as before (unfixed) |
