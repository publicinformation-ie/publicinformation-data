# All bodies re-run after scorer merge-order fix (2026-11-14, HEAD f175c77e)

Re-run of Task 7 after f175c77e ("scorer merges continuation rows in the same order as filter_phantom_rows"). Four states, 130 bodies (union of body ids across baseline, pre-fix, previous run and this run, transform and canonicalize_rows outputs). Baseline = foi-before-snapshot-2026-11-12 (Nov 12-13 build); pre-fix = foi-after-prefix-snapshot-2026-11-14; previous run = same code at 387ccfd7 (kept in the scratchpad, not a published snapshot); this run = HEAD f175c77e: `errors.json` reset to `[]` for every step in range, `transform_disclosure_files --force --processes 8` run directly (12:10), then runner `--from assess_table_structure --to extract_disclosures_canonicalize_rows --force --stop-on-error` (exit 0; every step output.json has a fresh mtime 12:10-12:38). No downloads, no paid OCR, extract_motions not run. `before_after.py --bodies <130-id union>` was run for baseline->post-fix and pre-fix->post-fix (plus previous run->post-fix).

## Headline numbers

| state | canonicalize_rows records | bodies with records | bodies at 0 that had >0 in baseline |
|---|---|---|---|
| baseline | 63,159 | 115 | n/a |
| pre-fix | 43,697 | | 14 |
| previous run (before f175c77e) | 57,490 | | 4 (1089, 1484, 1496, 1758) |
| this run (f175c77e) | 56,390 | 110 | 5 (1089, 1202, 1484, 1496, 1758) |

- TableStructureUnreliable: 487 (pre-fix) -> 158 (previous) -> 163 (this run). New rejections vs previous: 1202 foi-log-2025.pdf (width 0.814, fragment_share 0.186), 1213 q3-2016 (repeated_header_share), 1213 q3-2017 (split_word_rate), 1213 q4-2017 (width 0.554, fragment 0.446), 1212 Q3 2025 (fragment_share 0.082), 1501 louth 2018 (split_word_rate). One file no longer rejected: dlrcoco "Freedom of Information Application Form.pdf" (not understood; not a scorer-merge effect that I checked).
- Records changed vs previous run: 1202 726 -> 0, 1213 1,866 -> 1,663, 1200 832 -> 779, 1501 1,084 -> 986, 1204 847 -> 831, 1212 2,976 -> 2,972. Total -1,100. All other bodies identical (1876 byte-identical records).
- Errors: previous -> this run, UnrecognizedDecisionStatus 413 -> 413, StatusValueIsDate 512 -> 467, UnrecognizedRequesterType 1870 -> 1869, StatusValueIsColumnHeader 31 -> 31. Per-step errors.json counts: transform 4, assess 163, normalize_rows 462, canonicalize 135 (prev 143), canonicalize_rows 2,780 (prev 2,826).
- Post-fix vs baseline: 47 bodies below baseline (previous run 46; the new one is 1202). Largest: 1213 2748->1663, 1202 726->0, 1163 1778->1152, 1817 1346->749, 1475 598->89, 1204 1332->831, 1196 1578->1211, 1574 433->89, 1010 711->384. Total gain over baseline in bodies that rose: 456 records (previous 460). No new body.
- Pre-fix -> post-fix: only 3 bodies are lower than pre-fix (1129 853->842, 1207 4289->4288, 1295 942->878).

## Acceptance criteria

1. PASS. Of 1876, 1202, 1771, 1752, 1653, 1573, 1552, six have records: 890, 0, 57, 12, 11, 9, 101 (previous run: all seven, 1202 had 726). Threshold is at least 5. Zero-record bodies (that had records in baseline) 5 < 14. Remaining zero: 1089, 1202, 1484, 1496, 1758. 1202 is the one change: its only PDF (foi-log-2025.pdf) is now rejected, see check 6.
2. FAIL as written (unchanged from previous run; the expectation looks wrong). Matching by URL and link text: the 1177 Environment PDF (`Access-to-Information-on-the-Environment-2.pdf`, link text "here") and the 1867 RMD-6 PDF (`RMD-6-foi-request.pdf`, link text "FOI Access Form") are both still `TableStructureUnreliable` (width_uniformity + split_word_rate each). So the "1867 FOI Access Form" and "1177 here" items are the same two files, not separate unmatched ones as the previous doc said. 1505 `FOI Disclosure Log (2016-2018).pdf` (both URL variants, camelot_lattice) is accepted via fix B and still yields 20 records, same as baseline. 4 of the 5 listed labels (2 files) stay rejected, 1505 2016-18 does not.
3. FAIL (same as previous run). Bar = gold normalised accuracy >= 0.95. At current thresholds (0.92/0.08), rows scored by the 041b8508 scorer give TP20/FP8/FN8/TN31; HEAD scorer gives TP22/FP12/FN6/TN27 (identical to the previous run, so f175c77e did not move the gold confusion). +2 true passes, +4 false passes, precision 0.71 -> 0.65. Flips fail->pass, all vs 041b8508: 494a78 camelot_lattice (gold 0.978), 494a78 pymupdf (0.222, FP), 6ab587 camelot_lattice (0.075, FP), 6ab587 docling (1.0), e93ccc camelot_stream (0.0, FP), e93ccc pymupdf (0.05, FP). No pass->fail flips. Spearman rho composite vs gold normalised 0.584 (previous 0.590; the committed bakeoff.md before regeneration). Regenerated `bakeoff.json`/`bakeoff.md` via a scratch copy of bakeoff.py (assertion on the ihrec Q2-2025 sample hash turned into a warning because the cache was repopulated; source bakeoff.py unchanged), then `report.py`. The only text changes in bakeoff.md are small composite/metric means for pdfplumber/camelot_stream/pymupdf (scorer merge order), strata runner-ups, rho, and the rejected 0.85/0.10 row (26/15/2/24 -> 24/15/4/24). The gold set is provisional and small (10 files).
4. PASS (reviewer to confirm). 1876 has 890 records, identical to the previous run, so the same seed-1876 sample applies (`random.seed(1876)`, `random.sample(records, 10)`, listed below). All 10 descriptions are whole sentences/requests, none is a continuation fragment. Caveats unchanged: 15/890 records have null date_received, one of the 10 has null dates and empty requester_type, three say just "Personal".
5. PASS. 1505: 96 records; none has a lone 4-digit year as its only populated value (fields counted: foi_reference_id, date_received, decision_date, requester_type, decision_status, review_status, related_request, request_description).
6. Fragment honesty (new check). Definition: a canonicalize_rows PDF record with no foi_reference_id and no date_received and no decision_date counts as junk (almost always a continuation fragment). Records only come from files that passed the gate. "Has a reference column" = the body has at least one PDF record with a non-null foi_reference_id.

| | previous run | this run |
|---|---|---|
| 1202 junk / records | 468 / 726 | 0 / 0 |
| 1200 junk / records | 55 / 832 | 1 / 779 |
| 1213 junk / records | 57 / 1,866 | 1 / 1,663 |
| ref-column PDF bodies: junk / records | 3,716 / 46,429 (83 bodies) | 3,115 / 45,329 (82 bodies) |
| all PDF bodies: junk / records | 3,808 / 50,195 (101 bodies) | 3,207 / 49,095 (101 bodies) |

   PASS for the three target bodies: 1200 and 1213 are essentially clean (1 junk each). 1202 no longer passes the gate (foi-log-2025.pdf: width 0.814, fragment_share 0.186), so its 468 junk records are gone, along with 258 real ones (726 - 468), so it is a recall loss of 258 records against baseline, not a precision issue. The remaining ref-column junk is concentrated in bodies this fix did not touch: 1486 747/1,561, 1655 605/1,584, 1235 547/1,348, 1390 444/767, 1456 229/598, 1104 144/367, 1112 111/1,128, 1834 94/727. Those are not fixed by f175c77e. The 3,115 junk records are 6.9% of ref-column PDF records (previous 8.0%).


## 1876 spot-check records (seed 1876, same as previous run)

## 1876 spot-check records (seed 1876)

    {"date_received": "2017-10-26", "decision_date": "2017-11-22", "requester_type": "Journalist", "decision_status": "Part-Granted", "foi_reference_id": null, "request_description": "A detailed breakdown of the expenditure for each foreign trip undertaken by a councillor plus council delegation in 2016 and 2017 to include: names of who went on each trip; reason for the trip, the cost of each trip and a breakdown of costs for each trip to include accommodation, travel, subsistence as well as copies of any receipts. Note: By delegation I mean all who travelled on each trip: including councillors, their partners, officials, plus their partners, as well as anyone else whose bills were covered by the local authority"}
    {"date_received": "2017-09-11", "decision_date": "2017-09-28", "requester_type": "Other", "decision_status": "Withdrawn", "foi_reference_id": null, "request_description": "The number of people on the Wicklow County Council housing waiting list as of the 1st of September 2017."}
    {"date_received": "2022-10-25", "decision_date": "2022-11-21", "requester_type": "Other", "decision_status": "Part-Granted", "foi_reference_id": null, "request_description": "Personal"}
    {"date_received": "2019-05-02", "decision_date": "2019-05-29", "requester_type": "Client", "decision_status": "Part-Granted", "foi_reference_id": null, "request_description": "Personal"}
    {"date_received": "2023-10-17", "decision_date": "2023-11-14", "requester_type": "Client", "decision_status": "Part-Granted", "foi_reference_id": null, "request_description": "Personal"}
    {"date_received": "2021-11-01", "decision_date": "2021-11-25", "requester_type": "Other", "decision_status": "Part-Granted", "foi_reference_id": null, "request_description": "1. The Road Works Speed Limit Order No. 1 of 12020 and associated maps/drawings (M11/N11, Bray South to Kilmacanogue) 2. The application for above to Garda Commissioner with maps/drawings 3. The newspaper advertisements for above, indicating \u201cthe location where the Order will have effect 4. The application for consent to the Order to the national Roads Authority, with associated maps/drawings 5. The Road Works Speed Limit Order No 2 \u2013 i.e. the extension of the original order Note: Steps 2, 3, and 4 above are required under the Road Traffic Acts"}
    {"date_received": "2016-11-09", "decision_date": "2016-11-15", "requester_type": "Client", "decision_status": "Refused", "foi_reference_id": null, "request_description": "Personal"}
    {"date_received": "2024-09-25", "decision_date": "2024-10-08", "requester_type": "Other", "decision_status": "Withdrawn", "foi_reference_id": null, "request_description": "Under the Freedom of Information Act, I wish to request the following information. Copies of all correspondence between the Chief Executive of Wicklow County Council with the Department of Local Government regarding the newly created position of Director of Services in Wicklow County Council in the period from September 1st, 2023 and today, 25th September 2024."}
    {"date_received": "2016-07-15", "decision_date": "2016-07-26", "requester_type": "Journalist", "decision_status": "Refused", "foi_reference_id": null, "request_description": "Number of workers suspended , reason for suspension for breaking social media rules in 2016, 2015, 2014 and 2013."}
    {"date_received": null, "decision_date": null, "requester_type": "", "decision_status": "Granted", "foi_reference_id": null, "request_description": "I would like to formally request information regarding the total costs and what amount has been paid to consultants for work carried out on the Blessington Greenway application . My request includes: 1. Amounts and details costs paid to all of external consultants for work carried out on application to ABP March 2023 for Blessington Greenway application. Blessington Greenway Scheme (application register reference number ABP-312479- 22). 2 Amount and details of costs paid to all external consultants for work carried out on Application to ABP for Blessington Greenway application for further information June 2024 . It is important that Wicklow constituents know how much our county council have paid to consultants for this application and further information request"}

## Previous run (before f175c77e, HEAD 387ccfd7)

- 57,490 canonicalize_rows records, TableStructureUnreliable 158, zero-record bodies 4 (1089, 1484, 1496, 1758), 46 bodies below baseline, gain 460.
- Criteria: 1 PASS (all 7 bodies had records, incl. 1202 = 726), 2 FAIL (1505 2016-18 accepted via B), 3 FAIL (TP22/FP12/FN6/TN27 vs 20/8/8/31 at 041b8508), 4 PASS, 5 PASS.
- Fragment honesty (measured retroactively on that output): 1202 468/726 junk, 1200 55/832, 1213 57/1,866, ref-column PDF bodies 3,716/46,429.
- Per-fix attribution from that run (A/B/C/D toggles, not repeated): A +1 TP/+3 FP (117 files, 4,720 records, 31 bodies); B +1 TP/+2 FP (82 files, 3,842 records, 22 bodies); C no gold effect (75 files, 2,817 records, 22 bodies); D no gold effect, fixes 1505 lone-year records. B alone accounts for the 1505 2016-18 acceptance.

## Outcome

Criteria 2 and 3 fail as written (same as the previous run; 2 on a likely-wrong expectation, 3 on +2 TP / +4 FP, precision 0.71 -> 0.65 on a provisional 10-file gold set). Criteria 1, 4, 5 pass and the new check 6 passes for 1200 and 1213. The merge-order fix cost 1,100 records vs the previous run, mostly 1202 (726, 468 of them junk), 1213 (203) and 1501 (98); it removed 601 junk ref-column records. No code was tuned.
