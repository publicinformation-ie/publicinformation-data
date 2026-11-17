# Gating triage: source files (fault kind S)

`inputs.json` holds per-file facts for the 74 kind `S` ledger entries, built by
`uv run python -m experiments.gating.triage inputs --round-dir experiments/2026-11-17-gating-triage-source-files`.
Page 1 images (110 dpi PNG) are in `review/img/<sha256>.png`.

- likely_scan (chars_per_page < 50): 1
- unreadable: 0
- sorted chars_per_page: [0.0, 127.0, 183.0, 259.0, 259.0, 259.0, 266.0, 268.0, 269.0, 269.0, 546.0, 697.4, 708.5, 858.7, 873.2, 920.0, 927.0, 938.0, 1076.0, 1104.5, 1166.0, 1239.0, 1246.3, 1249.5, 1280.0, 1303.0, 1307.0, 1338.0, 1343.2, 1405.2, 1416.0, 1428.0, 1444.2, 1462.0, 1662.0, 1675.0, 1696.3, 1703.0, 1724.9, 1728.0, 1742.8, 1762.1, 1787.0, 1788.1, 1800.8, 1810.3, 1822.2, 1826.0, 1922.1, 1951.5, 1982.6, 1992.5, 1998.7, 2010.3, 2015.0, 2050.0, 2060.0, 2199.9, 2217.0, 2223.5, 2230.0, 2250.0, 2699.0, 2719.0, 2730.7, 2783.8, 2807.0, 3006.0, 3511.9, 3534.7, 3949.0, 3949.0, 4055.7, 6204.0]

Only one file falls below 50 (0.0); the next lowest is 127.0, so the threshold of 50 sits in the gap.
