# Override files newly failing the gate (task 11)

Baseline: ledger 02 state (/Volumes/ext/dev/publicinformation/foi-after-role-gate-2026-11-14). 14 override files, 4 not present as records at all (0 rows).

| body | file | extractor | failed checks | records before | records after | canon errors before -> after |
|---|---|---|---|---|---|---|
| 1104 | Central Bank freedom-of-information-disclosure-log-2025-(non-personal-requests).pdf | camelot_stream | width_uniformity, fragment_share, anchored_row_share (role_contamination 0.117 passes) | 130 | 0 | 4 -> 0 |
| 1552 | NCCA ncca-disclosure-log-2024.pdf | pdfplumber | width_uniformity, fragment_share, split_word_rate, anchored_row_share (role_contamination 0.015) | 101 | 0 | 14 -> 0 |

Total lost: 231 records (57081 -> 56850). Canonicalize errors 1326 -> 1308.

Flagged but records unchanged: body 1295 Fingal 2016 (failed: anchored_row_share 0.776). Its 119 records (268 errors) still emerge because
`extract_disclosures_normalize_header/override.json` carries a hand-curated 368-row table for this URL that replaces the gated (emptied) rows
downstream. The gate cannot reach it.

Passing override files (unchanged): Fingal 2022 and 2023, LCC 2023, Meath 2018 H1/H2 and 2019 H1/H2.
