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
`exclusions_proposed.json` holds the 19 `not_foi_log` entries; it reaches the step only through Task 8.

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
