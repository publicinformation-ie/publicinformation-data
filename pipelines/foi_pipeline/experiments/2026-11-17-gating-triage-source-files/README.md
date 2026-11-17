# Gating triage: source files (fault kind S)

`inputs.json` holds per-file facts for the 74 kind `S` ledger entries, built by
`uv run python -m experiments.gating.triage inputs --round-dir experiments/2026-11-17-gating-triage-source-files`.
Page 1 images (110 dpi PNG) are in `review/img/<sha256>.png`.

- likely_scan (chars_per_page < 50): 1
- unreadable: 0
- sorted chars_per_page: [0.0, 127.0, 183.0, 259.0, 259.0, 259.0, 266.0, 268.0, 269.0, 269.0, 546.0, 697.4, 708.5, 858.7, 873.2, 920.0, 927.0, 938.0, 1076.0, 1104.5, 1166.0, 1239.0, 1246.3, 1249.5, 1280.0, 1303.0, 1307.0, 1338.0, 1343.2, 1405.2, 1416.0, 1428.0, 1444.2, 1462.0, 1662.0, 1675.0, 1696.3, 1703.0, 1724.9, 1728.0, 1742.8, 1762.1, 1787.0, 1788.1, 1800.8, 1810.3, 1822.2, 1826.0, 1922.1, 1951.5, 1982.6, 1992.5, 1998.7, 2010.3, 2015.0, 2050.0, 2060.0, 2199.9, 2217.0, 2223.5, 2230.0, 2250.0, 2699.0, 2719.0, 2730.7, 2783.8, 2807.0, 3006.0, 3511.9, 3534.7, 3949.0, 3949.0, 4055.7, 6204.0]

Only one file falls below 50 (0.0); the next lowest is 127.0, so the threshold of 50 sits in the gap.

## Verdicts applied (2026-11-17)

User sitting complete: 74 confirmed, 0 unconfirmed — hard_table 40, not_foi_log 19, small_log 15.
`exclusions_proposed.json` holds the 19 `not_foi_log` entries; it reaches the step only through the ship step in PLAYBOOK §7 (done in this round on 2026-11-17).

## Pattern search (Task 7 step 5)

Candidates run through `exclusion_check` against the 19 confirmed files:

| pattern | covers confirmed | with records | unconfirmed hits | ok |
|---|---|---|---|---|
| url `application` | 5 | 0 | 3 (dlrcoco Application Form, hse.gov.uk hop1-1a, b3) | yes |
| url `environment` | 3 | 0 | 0 | yes |
| url `request-for-access` | 0 | 0 | 0 | no |
| url `access-to-information-on-the-environment` | 1 | 0 | 0 | no |

Ruling: no pattern added. `application` and `environment` pass the numeric gate but are generic words that
would reject future disclosure logs whose URL or link text carries them (e.g. a body's "applications log",
a Department of the Environment log); `application` also has 3 unread unconfirmed hits. The 19 files are
excluded by explicit URL instead. Cost if wrong: a future non-FOI form of the same family is not auto-rejected
and returns for another triage round.

## Shipped (Task 8, 2026-11-17)

- Files excluded: the 19 `not_foi_log` entries, now in `steps/verify_disclosure_files/excluded_files.json` (recorded as rejections with signal `manual_exclusion`). Patterns added: none.
- Run: verify unscoped without `--force` (no downloads, 19 `manual_exclusion` records, `dirty_ids.json` = the 16 bodies of those files: 1047, 1093, 1149, 1177, 1194, 1298, 1391, 1394, 1442, 1443, 1493, 1559, 1602, 1732, 1747, 1867), then `process.py --from transform_disclosure_files --to extract_disclosures_deduplicate` (`Dirty: evicted 103 record(s) for 16 body ID(s)`). Snapshot before the run: `/Volumes/ext/dev/publicinformation/foi-before-source-exclusions-2026-11-17`.
- Errors before and after: `assess_table_structure` 126 -> 107 (exactly the 19 excluded URLs removed, none added). `transform_disclosure_files` 4 -> 8 and `extract_disclosures_normalize_rows` 444 -> 460 are duplicates only (unique errors identical once `timestamp` is ignored: 4 and 422, none new, none lost). Eviction removes a body's records but not its errors, so the re-run appends the same errors again. Pre-existing behaviour, accepted, not deduplicated, deferred as a minor. `extract_disclosures_canonicalize` 139 and `extract_disclosures_canonicalize_rows` 1316 unchanged.
- Record counts: every file other than the 19 is unchanged in every step from verify to deduplicate. transform 1445 -> 1426, normalize_rows 1449 -> 1430, canonicalize 58036, canonicalize_rows 57854, deduplicate 52439 (all unchanged: the excluded files had no canonical rows). `before_after.py --bodies` over the 16 bodies: canonicalize_rows 2807 -> 2807, TableStructureUnreliable 22 -> 3.
- Ledger rebuilt (`uv run python -m experiments.gating.ledger`): gated 107, by kind E 77, G 25, M 5. The kind `S` entries are gone.
- Files per remaining class (of the 74 kind `S` files): hard_table 40, small_log 15 (both stay in the pipeline), not_foi_log 19 (excluded).
- Handed to the paid trial (`scan`): 1 file, the only one under 50 chars per page (0.0), classed small_log: `https://assets-eu-01.kc-usercontent.com:443/5608854e-b2c7-0144-a5f6-88a7e629b0a4/e1a94111-56fd-43da-8326-7c328c24478c/foi-disclosure-log-2024.pdf`.

### Verifier signals shared by three or more `not_foi_log` files (for a later decision on the verifier, no code change)

| verification_signal | not_foi_log files |
|---|---|
| decision, foi | 7 |
| freedom of information, foi | 5 |
| freedom of information, decision | 4 |

(The other two files carry `url:freedom of information, foi` x2 and `disclosure log` x1.)
