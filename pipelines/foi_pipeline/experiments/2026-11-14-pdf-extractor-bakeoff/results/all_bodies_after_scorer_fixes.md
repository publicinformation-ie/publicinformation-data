# All bodies after scorer fixes A-D + NCCA override (2026-11-14)

Three states, 130 bodies (union of body ids across baseline, pre-fix and post-fix transform and canonicalize_rows outputs). Baseline = foi-before-snapshot-2026-11-12 (Nov 12-13 build); pre-fix = foi-after-prefix-snapshot-2026-11-14; post-fix = this run (HEAD 387ccfd7, `transform_disclosure_files --force --processes 8`, then runner `--from assess_table_structure --to extract_disclosures_canonicalize_rows --force --stop-on-error`; errors.json reset to `[]` first for every step in range; no downloads, no paid OCR, extract_motions not run). Full per-body tables: `before_after.md` style output for both comparisons was generated with `before_after.py --bodies <union>`; summary below.

## Headline numbers

| state | canonicalize_rows records | bodies at 0 that had >0 in baseline |
|---|---|---|
| baseline | 63,159 | n/a |
| pre-fix | 43,697 | 14 |
| post-fix | 57,490 | 4 (1089, 1484, 1496, 1758) |

- TableStructureUnreliable: 487 (pre-fix) -> 158 (post-fix).
- Pre-fix to post-fix errors: UnrecognizedDecisionStatus 294 -> 413, StatusValueIsDate 341 -> 512, UnrecognizedRequesterType 1587 -> 1870, StatusValueIsColumnHeader 25 -> 31 (more records flow through, so more value errors).
- Post-fix vs baseline: 46 bodies still below baseline (largest: 1163 1778->1152, 1475 598->89, 1574 433->89, 1817 1346->749, 1010 711->384, 1213 2748->1866, 1204 1332->847, 1876 1018->890, 1758 3->0, 1496 133->0, 1484 79->0, 1089 9->0). Total gain over baseline in bodies that rose: 460 records. No new body.
- Step run check: every step from transform through canonicalize_rows has a fresh output.json mtime (10:59-11:27) and the runner exited 0. Post-run errors counts: transform 4, assess 158, normalize_rows 462, canonicalize 143, canonicalize_rows 2826.

## Acceptance criteria

1. PASS. Of 1876, 1202, 1771, 1752, 1653, 1573, 1552 all 7 have records: 890, 726, 57, 12, 11, 9, 101 (baseline 1018, 726, 57, 12, 11, 9, 79; pre-fix all 0). Zero-record bodies 4 < 14 (same counting definition on the pre-fix snapshot gives 14, matching the handoff). Remaining zero: 1089, 1484, 1496, 1758.
2. FAIL as written, but the expectation looks wrong (corrected 2026-11-14). Still `TableStructureUnreliable`: 1867 RMD-6 ("FOI Access Form"), 1177 "here". The 1177 Environment PDF and the 1867 "FOI Access Form" could not be matched to URLs. 1505 `FOI Disclosure Log (2016-2018).pdf` (both URL variants) is accepted only through fix B (camelot_lattice or pymupdf; 11 rows, 7 columns, width uniformity 1.0) and yields 20 records in canonicalize_rows, same as baseline; so the criterion's expectation looks wrong rather than B being wrong. Also recovered, not in the Review Focus list: 1867 Section-F-FOI-plus-other-website-Feb-2021.pdf (6 records), 1177 20260527_FOI-LOG.pdf (15 records), 1505 2019-2025 (76). The 1505 2016-18 file was only failing width_uniformity pre-fix.
3. FAIL (restated 2026-11-14; the earlier "8 fail->pass flips below 0.95" was wrong). Bar = gold normalised accuracy >= 0.95 (bakeoff.md). That comparison used a stale bakeoff.json from 3bbb3e1a with the old 0.85/0.10 thresholds; 0.92/0.08 came in 041b8508. Re-scored with the 041b8508 scorer vs HEAD, confusion counts are baseline TP20/FP8/FN8/TN31 -> HEAD TP22/FP12/FN6/TN27: +2 true passes and +4 false passes, precision 0.71 -> 0.65. The gold set is provisional and small (10 files). Of the eight earlier-listed flips, four were already passing at 041b8508 (4cb607 camelot_lattice and docling, e93ccc mistral_cache, ec6c89 mistral_cache). Known false passes: e93ccc pymupdf, e93ccc camelot_stream (A), 494a78 pymupdf (A), 6ab587 camelot_lattice (A-or-B interaction; fails only with both off, width 0.912 vs 0.92). No pass->fail flips. Spearman rho composite vs gold normalised 0.740 -> 0.590. Note the sample file Freedom-of-Information-Disclosure-Log-Q2-2025.pdf (ihrec, no gold, sha 351020f0) has different cached bytes than sample.json's hash (cache was repopulated); bakeoff.py asserts on this, so a scratch copy with the assertion turned into a warning was used. Source `bakeoff.py` unchanged.
4. PASS (reviewer to confirm). 1876 has 890 records; `random.seed(1876)`, `random.sample(records, 10)`, full records below. All 10 descriptions are whole sentences/requests, none is a continuation fragment. Caveats: 15/890 records have null date_received, one of the 10 sampled (a complete request) has null dates and empty requester_type; three sampled say just "Personal" (a genuine short log value).
5. PASS. 1505: 96 records; none has a lone 4-digit year as its only populated value. Fields counted: foi_reference_id, date_received, decision_date, requester_type, decision_status, review_status, related_request, request_description (metadata such as public_body_id, name, URLs, row_id, known_issues, missing_columns excluded).

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

## Per-fix attribution (added 2026-11-14)

| fix | gold effect | files recovered | records | bodies |
|---|---|---|---|---|
| A | +1 TP, +3 FP | 117 | 4,720 | 31 |
| B | +1 TP, +2 FP (6ab587 shared with A) | 82 | 3,842 | 22 |
| C | none | 75 | 2,817 | 22 |
| D | none | 0 | fixes 1505 lone-year records | n/a |

- B is the sole cause of the 1505 2016-18 acceptance.
- Overall 328 of 329 newly passing files recover records (~13.7k); disabling A-D together recovers none.
- Narrowing B to tolerance 1 changes neither gold nor 1505.

## Outcome

Criteria 2 and 3 fail as written (2 on a likely-wrong expectation; 3 is +2 TP / +4 FP, precision 0.71 -> 0.65 on a provisional 10-file gold set). Per the task rules no code was tuned. Criteria 1, 4, 5 pass.

Decision 2026-11-14: user accepted fixes A-D and the PR is opened with these numbers.
