# Leftovers on the covered bodies

Scope: 13 bodies (1112, 1157, 1177, 1259, 1552, 1653, 1655, 1711, 1741, 1747, 1774, 1806, 1882), 91 PDF files, after-run `extract_disclosures_canonicalize_rows`. NOT an all-bodies result: the vocabulary candidates named in the brief come from other bodies and are counted below only where they occur here.

## Named vocabulary candidates in covered bodies

- `Ongoing`: 0 occurrences
- `Closed`: 0 occurrences
- `Release with redactions`: 0 occurrences
- `Clarification sought`: 0 occurrences
- `Student`: 1 occurrences
- `Staff Member`: 0 occurrences

## Unrecognized requester_type (after), grouped ignoring spaces/trailing dots

| count | bodies | variants (raw, count) |
|---|---|---|
| 592 | 1655 | `Journalist.` x581; `J ournalist.` x6; `J ournalist` x3; `J o u r n a l i s t` x1; `.Journalist.` x1 |
| 368 | 1655 | `Member of the public.` x358; `Member of the Public.` x7; `M ember of the public` x3 |
| 32 | 1655 | `Member of staff.` x21; `Member of staff` x11 |
| 6 | 1655 | `Staff.` x6 |
| 3 | 1655 | `Member of the Oireachtas.` x3 |
| 3 | 1655 | `Member of Oireachtas.` x3 |
| 2 | 1112 | `Journalist Journalist` x2 |
| 1 | 1655 | `Oireachtas.` x1 |
| 1 | 1655 | `Members of the public` x1 |
| 1 | 1655 | `Public.` x1 |
| 1 | 1655 | `Journalist and member of staff` x1 |
| 1 | 1112 | `Oireachtas and Reps` x1 |
| 1 | 1112 | `Student` x1 |
| 1 | 1112 | `Category of Request Others` x1 |
| 1 | 1259 | `Individual - Transfer from HSE` x1 |
| 1 | 1741 | `Legal` x1 |
| 1 | 1882 | `Duine Aonair/Indi` x1 |

## Unrecognized decision_status (after), grouped ignoring spaces/trailing dots

| count | bodies | variants (raw, count) |
|---|---|---|
| 7 | 1655 | `R S efused. ection 15(1)(a).` x7 |
| 6 | 1655 | `R S efused. tatutory Instrument SI 115 of 2000.` x6 |
| 4 | 1655 | `Statutory Instrument SI 115 of 2000.` x4 |
| 3 | 1655 | `G ranted.` x3 |
| 2 | 1655 | `R S efused. ection 15(1)(b) as a result of Section 12(1)(b).` x2 |
| 2 | 1655 | `R efused. Statutory Instrument SI 115 of 2000.` x2 |
| 1 | 1655 | `Not covered by the FOI Act.` x1 |
| 1 | 1655 | `R S efused. ection:15(1)(a).` x1 |
| 1 | 1655 | `Outside of the FOI Act.` x1 |
| 1 | 1655 | `Records requested not subject to the Freedom of Information Act. Section 37(1).` x1 |
| 1 | 1655 | `Section 37(1). Statutory Instrument SI 115 of 2000.` x1 |
| 1 | 1655 | `Section 15(1)(a).` x1 |
| 1 | 1655 | `Statutory Instrument SI 115 of 2000. Section 27(1).` x1 |
| 1 | 1655 | `PG Sections: 15(1)(d); 29 (1)(a) and (b); 30(1)(a), (b) and (c); 36(1)(b) and (c).` x1 |
| 1 | 1655 | `R S S efused. ection 15(1)(a). tatutory Instrument SI 115 of 2000.` x1 |
| 1 | 1655 | `R S S efused. ection 15(1)(c). tatutory Instrument SI 115 of 2000.` x1 |
| 1 | 1655 | `R S efused. ections: 32(1)(a); 37(1).` x1 |
| 1 | 1655 | `R S efused. ections 32(1)(a); 37(1).` x1 |
| 1 | 1655 | `R S I efused. ection 15(1)(a). nformation is not subject to release under FOI Act.` x1 |
| 1 | 1655 | `R S S efused. ection 36(1)(b). tatutory Instrument SI 115 of 2000.` x1 |
| 1 | 1655 | `R S efused. tatutory Instrument 115 of 2000.` x1 |
| 1 | 1655 | `R S efused. ection 32(1)(a).` x1 |
| 1 | 1655 | `R efused. Section 15(1)(a).` x1 |
| 1 | 1655 | `H andled outside of Freedom of Information Act.` x1 |
| 1 | 1655 | `R S efused. ection 37(1). Statutory Instrument SI 115 of 2000.` x1 |

Notes: the dominant leftover is RTE (1655) writing `Journalist.` / `Member of the public.` with a trailing full stop (a normalisation candidate, not new vocabulary). Variants like `J ournalist.` and `R S efused.` are camelot_lattice glyph-split artefacts in cell text (a cell-repair candidate for `normalize_disclosure_cells`), not vocabulary. Header aliases not yet mapped: RTE `Date FOI Received`, `Freedom Of Information Request`, `F OI No.`; C&AG (1157) `Records Requesteda`; Teagasc (1774) `Internal Reference` (foi_reference_id populated on 63/67 records before, 3/82 after).

## TableStructureUnreliable files (manual override / later extractor candidates)

| body | extractor | failed checks | rows | records before | file |
|---|---|---|---|---|---|
| 1655 | camelot_lattice | split_word_rate | 55 | 45 | https://about.rte.ie/wp-content/uploads/2025/10/RTE-FOI-Disclosure-Log-Q2-2025.pdf |
| 1112 | pdfplumber | width_uniformity, fragment_share | 86 | 0 | https://www.tusla.ie/uploads/content/2026_FOI_Disclosure_Log_-_Quarter_1.pdf |
| 1112 | camelot_lattice | width_uniformity, fragment_share | 139 | 0 | https://www.tusla.ie/uploads/content/2025_FOI_Disclosure_Log.pdf |
| 1112 | pymupdf | width_uniformity, fragment_share, split_word_rate | 98 | 108 | https://www.tusla.ie/uploads/content/2023_FOI_Disclosures_Log.pdf |
| 1112 | camelot_lattice | split_word_rate | 126 | 121 | http://www.tusla.ie/uploads/content/2022_FOI_Disclosures_Log.pdf |
| 1177 | camelot_lattice | width_uniformity, fragment_share | 25 | 43 | https://crawfordartgallery.ie/wp-content/uploads/20260527_FOI-LOG.pdf |
| 1177 | camelot_stream | width_uniformity, split_word_rate | 55 | 0 | https://crawfordartgallery.ie/wp-content/uploads/Access-to-Information-on-the-Environment-2.pdf |
| 1552 | mistral_cache | repeated_header_share | 118 | 79 | https://ncca.ie/media/4qffya5u/ncca-disclosure-log-2024.pdf |
| 1653 | pdfplumber | width_uniformity | 11 | 11 | https://www.qqi.ie/sites/default/files/2026-09/foi-disclosure-log-jan-jun-26.pdf |
| 1711 | pdfplumber | width_uniformity, fragment_share | 21 | 0 | https://www.skillnetireland.ie/uploads/attachments/FOI_Disclosure_Log_%281%29.pdf |
| 1741 | pdfplumber | width_uniformity, fragment_share | 11 | 10 | https://www.sportireland.ie/sites/default/files/media/document/2023-06/2023%20Disclosure%20Log%20Q2%20%282%29.pdf |
| 1747 | camelot_stream | width_uniformity | 30 | 0 | https://www.stjames.ie/media/FOI Patient Record Request Form August 2026.pdf |
| 1747 | camelot_stream | width_uniformity, fragment_share, split_word_rate | 68 | 0 | https://www.stjames.ie/media/FOI Request for Deceased Patient Records August 2026.pdf |
| 1882 | pdfplumber | width_uniformity | 13 | 12 | https://www.udaras.ie/assets/uploads/2021/09/Loga-Nochta-2020-ASF-.pdf |
| 1882 | pdfplumber | split_word_rate | 34 | 34 | https://udaras.ie/assets/uploads/2024/01/FOI-Disclosure-Log-2023.pdf |
| 1882 | pymupdf | width_uniformity, fragment_share | 13 | 11 | https://www.udaras.ie/assets/uploads/2020/06/05_FOI_Loga-Nochta-2017.pdf |

16 distinct files (the Tusla 2022/2023 files appear under both http and https URLs; before_after.md counts the 18 error entries). 'Records before' > 0 means the file yielded records previously and is now fail-closed; candidates for gate false positives: RTE Q2-2025 (split_word_rate 0.025 only, clean-looking table), 1552 NCCA (mistral_cache, repeated_header_share only), 1653 (width_uniformity only, 11 rows), 1882 Loga-Nochta-2020, 1741 2023 Q2.
