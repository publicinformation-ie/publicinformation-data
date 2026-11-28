# Transport RACI against the `transport-governance` skill

One-off comparison produced during the migration, as required by the handoff.
It compares the new master's assessed rows with the retired GDA RACI skill
(deleted when the skill was rebuilt against this dataset) where the two overlap:
national and regional roads, active travel, bus infrastructure, speed limits
and kerbside. **Neither side was changed.** The new data is canonical; the skill
now reads this dataset directly. A mismatch that shows an error in the new
data is fixed through `migration_resolutions.csv`, not here.

"Agree" means the same party holds the same role for the same function.
Differences in the set of Consulted parties are recorded as a mismatch, because
a missing consultee is a substantive difference. New-model rows are named by
assignment ID; only assessed rows are compared. Unassessed rows are stated as
gaps, not mismatches.

Rows were re-derived after the rulings of 28 November 2026 in
`migration_resolutions.csv` (several `GS` cells now read RSA and AGS). The five `GS` cells that still have no ruling do not appear in a comparison
below, so no verdict is marked undetermined.

## National roads

| # | Retired skill row | New model row | Verdict |
|---|---|---|---|
| 1 | `infra/national-roads` · Policy: A DoT, R DoT, C TII | `RT-24.S1` (policy for speed limits, the only assessed national-road policy row) A DoT, R DoT, C RSA, AGS, TII, LA-CE, I LA-M | Agree on A and R; mismatch on C (new adds LA-CE, RSA and AGS) |
| 2 | `infra/national-roads` · Strategic planning: A TII, R TII | No assessed row: `RT-01` is entirely not assessed | Gap in the new model |
| 3 | `infra/national-roads` · Funding: A TII, R TII | No assessed row: `RT-01.S3` is not assessed | Gap in the new model |
| 4 | `infra/national-roads` · Specification: A TII, R TII, LA-CE | No assessed row: `RT-01` is not assessed | Gap in the new model |
| 5 | `infra/national-roads` · Delivery: A TII, R LA-CE, TII | No assessed row: `RT-01.S10` is not assessed | Gap in the new model |
| 6 | `infra/national-roads` · Operation: A TII, R TII, LA-CE | No assessed row: `RT-01.S11` does not exist (INF profile) | Gap in the new model |
| 7 | `infra/national-roads` · Maintenance: A LA-CE, R LA-CE | `RT-02.S12` covers regional and local roads, not national roads; `RT-01.S12` is not assessed | Gap in the new model |
| 8 | `infra/national-roads` · Regulation, special speed limit: A LA-members, R LA-CE, C TII, AGS | `RT-25.S13a` (national managed roads variant) A TII, R TII, C RSA, AGS, I TP | Mismatch: the new model gives TII the decision on national managed roads and records no LA-members role; C is RSA and AGS, not TII |
| 9 | `infra/national-roads` · Regulation, special speed limit, other national roads | `RT-25.S13a` (other national roads variant) A LA-M, R LA-CE, C RSA, AGS, TP, with `RT-25.S5G` A TII for prior consent | Mismatch: TII is not Consulted on the S13a row; its role is split into the S5G prior-consent row. C is RSA, AGS and TP |
| 10 | `infra/national-roads` · Regulation, toll: A TII, R TII | No assessed row in the new model | Gap in the new model |

## Regional and local roads

| # | Retired skill row | New model row | Verdict |
|---|---|---|---|
| 11 | `infra/regional-local-roads` · Policy: A DoT, R DoT, C DHLGH | No assessed row: `RT-02.S1` does not exist (MAINT profile) | Gap in the new model |
| 12 | `infra/regional-local-roads` · Funding, state grant: A DoT, R DoT | `RT-02.S3` A DoT, R DoT, I LA-CE, I LA-M | Agree |
| 13 | `infra/regional-local-roads` · Funding, annual budget: A LA-members, R LA-CE | `RT-02.S3` (LA own resources variant) R LA-CE, I LA-M, evidence UNVERIFIED, no A | Mismatch: the new model records the split as unverified and does not publish an Accountable party |
| 14 | `infra/regional-local-roads` · Specification, schedule of municipal district works: A LA-MD, R LA-CE | `RT-02.S2` A LA-M, R LA-CE, I TP | Agree (LA-MD and LA-M name the same municipal-district organ) |
| 15 | `infra/regional-local-roads` · Maintenance: A LA-CE, R LA-CE | `RT-02.S12` A LA-CE, R LA-CE, R DA, I LA-M | Agree on A and R; the new model adds a delivery agent and an Informed party |
| 16 | `infra/regional-local-roads` · Consent, Section 38: A LA-CE, R LA-CE, C AGS | `RT-02` has no S7b (MAINT profile); `RT-09.S7b` is the nearest assessed road-works consent row, A LA-CE, R LA-CE, C TP, AGS | Gap: no regional-road S38 row in the new model. On the nearest row, AGS as Consulted is agreed (stated in official guidance) |
| 17 | `infra/regional-local-roads` · Consent, Part 8: A LA-members, R LA-CE | `RT-02` has no S7a (MAINT profile) | Gap in the new model |

## Active travel

| # | Retired skill row | New model row | Verdict |
|---|---|---|---|
| 18 | `infra/active-travel` · Policy: A DoT, R DoT, C NTA | `RT-09.S1` A DoT, R DoT, C NTA, TII, DoE, AT | Agree on A and R; mismatch on C (new adds TII, DoE and An Taisce) |
| 19 | `infra/active-travel` · Strategic planning: A DoT, R NTA, C LA-CE | `RT-09.S2` (NTA-funded LA scheme) A LA-CE, R AT and LA-CE, C SCH and TP | Mismatch: the new model is at scheme rather than network level; A and R differ |
| 20 | `infra/active-travel` · Funding: A NTA, R NTA, C DoT | `RT-09.S3` (NTA-funded LA scheme) A NTA, R NTA, C DoT, I LA-CE | Agree |
| 21 | `infra/active-travel` · Consent, Part 8: A LA-members, R LA-CE | `RT-09.S7a` (Part 8 route) A LA-M, R LA-CE, C TP, prescribed bodies | Agree on A and R; mismatch on C (new adds TP and prescribed bodies) |
| 22 | `infra/active-travel` · Consent, Section 38: A LA-CE, R LA-CE, C AGS, NTA | `RT-09.S7b` (s.38 route) A LA-CE, R LA-CE, C TP, AGS, I LA-M, NTA | Agree on A, R and AGS as Consulted; mismatch on NTA (Informed, not Consulted) |
| 23 | `infra/active-travel` · Delivery: A LA-CE, R LA-CE, C NTA | `RT-09.S10` (NTA-funded LA scheme) A LA-CE, R LA-CE and DA, C SCH and AGS, I NTA, LA-M | Agree on A; mismatch on R and on NTA (Informed, not Consulted) |
| 24 | `infra/active-travel` · Maintenance: A LA-CE, R LA-CE | `RT-09.S12` A LA-CE, R LA-CE and DA, I LA-M | Agree on A and R; the new model adds a delivery agent and an Informed party |
| 25 | `infra/active-travel` · Regulation: A LA-CE, R LA-CE, C AGS | `RT-09` has no S13a or S13b row (INF profile) | Gap in the new model |
| 26 | `infra/active-travel` · Operation and Enforcement not applicable | `RT-10` (greenways) adds S11, S13a and S14; `RT-10.S13a` A LA-M, R LA-CE and `RT-10.S14` A LA-CE, R LA-CE | Mismatch in scope: greenway operation and enforcement are assessed, active-travel infrastructure is not |

## Bus infrastructure

| # | Retired skill row | New model row | Verdict |
|---|---|---|---|
| 27 | `infra/bus` · Policy: A DoT, R DoT, C NTA | `RT-09.S1` is the assessed active-travel policy row; `RT-13.S1` is only assessed in the NTA-delivered variant, A NTA, R NTA, C LA-CE, DoT | Mismatch: the new model gives NTA A for a BusConnects scheme and has no generic bus-infrastructure policy row |
| 28 | `infra/bus` · Funding: A NTA, R NTA | `RT-13.S3` is not assessed | Gap in the new model |
| 29 | `infra/bus` · Consent, Part 8: A LA-members, R LA-CE | `RT-13.S7c` (BusConnects) A ACP, R NTA | Mismatch: the new model uses the ACP route for an NTA scheme |
| 30 | `infra/bus` · Consent, Section 51 approval: A ACP, R ACP | `RT-13.S7c` (BusConnects) A ACP, R NTA, C TP, LA-CE, prescribed bodies | Agree on A; mismatch on R and C |
| 31 | `infra/bus` · Delivery: A NTA, R NTA, LA-CE | `RT-13.S10` (BusConnects) A NTA, R NTA and DA, C LA-CE, I TP | Agree on A; mismatch on R (new uses a delivery agent, not LA-CE) |
| 32 | `infra/bus` · Maintenance: A LA-CE, R LA-CE, C NTA | `RT-13.S12` is not assessed | Gap in the new model |
| 33 | `infra/bus` · Regulation: A LA-CE, R LA-CE, C NTA, AGS | `RT-14a.S13b` (bus-stop location approval) A LA-CE, R LA-CE, C OPS, DA (TCU), AGS, I NTA | Agree on A, R and AGS as Consulted; mismatch on NTA (Informed, not Consulted) |

## Speed limits

| # | Retired skill row | New model row | Verdict |
|---|---|---|---|
| 34 | `infra/national-roads` · Regulation, special speed limit: A LA-members, R LA-CE, C TII, AGS | `RT-25.S13a` (national managed roads) A TII, R TII, C RSA, AGS | Mismatch (also row 8) |
| 35 | `infra/regional-local-roads` · Regulation, special speed limit: A LA-members, R LA-CE, C AGS | `RT-24.S13a` A LA-M, R LA-CE, C RSA, AGS, TP | Agree on A and R; mismatch on C (new adds RSA and TP to AGS) |
| 36 | No skill row for national default limits | `RT-40.S13a` A DoT, R DoT, I LA-CE, RSA, AGS | New model only |
| 37 | No skill row for road-works speed limit orders | `RT-37.S13b` (road works speed limit order) A LA-CE, R LA-CE, C RSA, AGS, TII (national roads) | New model only |
| 38 | No skill row for speed-limit policy separate from regulation | `RT-24.S1` A DoT, R DoT, C RSA, AGS, TII, LA-CE | New model only |

## Kerbside

| # | Retired skill row | New model row | Verdict |
|---|---|---|---|
| 39 | `infra/kerbside` · Policy: A DoT, R DoT | `RT-22.S1` is not assessed | Gap in the new model |
| 40 | `infra/kerbside` · Funding: A LA-members, R LA-CE | `RT-22` has no S3 row (custom profile) | Gap in the new model |
| 41 | `infra/kerbside` · Regulation, parking: A LA-members, R LA-CE, C AGS | `RT-22.S13a` is not assessed | Gap in the new model |
| 42 | `infra/kerbside` · Regulation, appointed stand: A LA-members, R LA-CE, C NTA, AGS | `RT-23.S13a` is not assessed | Gap in the new model |
| 43 | `infra/kerbside` · Enforcement, parking: A LA-CE, R LA-CE | `RT-22.S14` does not exist (custom profile); no assessed line covers parking enforcement (`X-02.S14` is assessed only for its speed-limits variant, so it is not compared) | Gap in the new model |
| 44 | `infra/kerbside` · Regulation, clamping: A NTA, R NTA | No assessed row in the new model | Gap in the new model |
