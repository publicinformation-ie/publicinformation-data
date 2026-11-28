# Migration notes

Recorded when `scripts/migrate_transport_raci_handoff.py` was run against
handoff v0.4 (register) and v0.1 (assignments). The handoff is gitignored, so
this note and the committed master are the durable record.

## Reproducibility

Every CSV in this folder and `migration_errors.json` are written by the
migration and are never edited by hand, except `public_text.csv`, which it
reads only. Four committed human inputs are read:

- `migration_resolutions.csv`: rulings on logged role errors (read and written
  back unchanged);
- `public_text.csv`: reviewed public copies of prose that cites an internal
  reference;
- `corrections.csv`: corrections to handoff facts that are not role errors
  (read and written back unchanged);
- `added_sources.csv`: sources the handoff lacks, merged into `sources.csv`
  after the handoff's own sources;
- `review_decisions.csv`: decisions on logged ambiguities that are not roles
  (a proposed variant merge, an ambiguous grouping), read and written back
  unchanged.

Re-running the migration on the handoff with these five files reproduces every
migration output byte for byte. `tests/test_transport_raci_migration.py`
checks this whenever the handoff is present (it is skipped in CI).
`migration_errors.json` is exactly what the script writes.

## Acceptance check

| Check | Result |
|---|---|
| Generated rows equal register Section 7 | 613 rows, identical IDs |
| Assessed rows | 184 |
| Assessed lines written or logged | 224 assignments (no line dropped) |
| Running the migration twice | byte-identical output |

## Rulings

`migration_resolutions.csv` holds:

- the deterministic rulings from the design, approved by Dave:
  `prescribed bodies` → the `prescribed-bodies` category party (9 cells), and
  `DoE, AT (SRTS)` → `DoE` plus `AT` with qualifier `SRTS` (3 cells);
- Dave's rulings of 28 November 2026 on `GS` cells: `X-02.S14` (Speed limits)
  A and R → `AGS`; C on `RT-24.S1`, `RT-24.S13a`, `RT-25.S13a` (both national
  road variants), `RT-37.S13b` (road works speed limit order) and `RT-40.S1`,
  and I on `RT-40.S13a` → `RSA; AGS`;
- Dave's rulings of the same date on the remaining `GS` cells, after the
  research in `gs_research.md`: 30 cells → `AGS` (and `RT-26.S13a` C →
  `RSA; AGS`). Each records its own `evidence_id`, `source_ids` and
  `rationale`.

Five `GS` cells have no ruling and stay on the review list: `RT-10.S14` C,
`RT-26.S14` C, `RT-37.S15` C, `RT-37.S11` (Garda-run event closures) R and
`RT-37.S14` (Offences) R.

## Per-role evidence

Evidence is recorded on the assignment line, and a role usually takes the
line's evidence. A ruling or correction may set `evidence_id` on the role
itself (`assignment_roles.csv`), with `source_ids` linked to the assignment.
For example the Gardaí are Consulted on the s.38 route rows on the strength of
official guidance, while those lines are otherwise assumed by the s.149(4)
default; the published role therefore carries `source`, not the line's
`default-s149-4`. The wide view marks such a role after its name.

## Corrections

`corrections.csv` corrects a handoff fact that is wrong, rather than rewriting
prose that cites an internal reference. Each row names the exact `original` it
replaces, the `corrected` value, the evidence, the sources, a rationale, the
ruling and the date. A correction fails the run when the source text no longer
matches, the record does not exist, or the field is not correctable. Four are
recorded, all ruled by Dave on 28 November 2026:

- `activities` `X-18` definition and `assignments` `X-18.S13b` note: event
  licensing is now Part 16 of the Planning and Development Act 2024, s.479, and
  S.I. No. 468 of 2026; Part XVI of the 2000 Act, including s.230, was repealed
  on 9 September 2026;
- `sources` `S153` citation: the Meath page predates that repeal;
- `assignment_roles` `RT-37.S14~offences|LA-CE`: role C → R, because Roads Act
  1993 s.81(3)(a) lets the road authority prosecute summary offences.

## Public text layer

The master keeps the handoff's prose exactly as written: assignment `note`,
activity and stage `name` and `definition`, party `name` and `description`.
Each has a public twin (`public_note`, `public_name`, `public_definition`,
`public_description`), and the generator publishes only the twin.

- A source text that cites no internal reference (finding, decision or
  scenario number) is copied unchanged. The validator enforces this, so a
  public copy can never differ from such a text.
- A source text that cites one takes the entry in `public_text.csv` for that
  exact table, key and field. The entry records the `original` it replaces; if
  the source text changes, or the key or field does not exist, or the source no
  longer cites an internal reference, the migration fails as stale.
- With no entry, the migration logs `needs_public_note` (assignments) or
  `needs_public_text` (prose) and leaves the public copy empty; the generator
  then refuses to build.

Internal references are finding numbers (`F9`), decision numbers
(`Decision 5`), scenario references, and register version/history markers
(`(v0.4)`, `v0.4:`, `in v0.3`). The pattern is defined once, as
`INTERNAL_REF` in `src/lib/transport_raci/model.py`; the generator's leak
check scans every published file with the same tokens. A versioned dataset
path such as `/v0.1.0/` is not a register marker and is not matched.

Rewrites only remove the internal reference and keep the meaning. Change
history ("v0.4: S10 and S11 added") is dropped only where an entry says so.
Where a history sentence carries substance (which stage covers what), the
rewrite keeps it in the present tense. Where a finding number named a boundary
rule, the rewrite names the rule: `F29` is the source of boundary rule B9, so
RT-25 now cites B9.

Every entry was reviewed and approved by Dave on 28 November 2026.
`public_text.csv` holds 47 entries. The first 31 rewrites:

| Table | Key | Field | Public text |
|---|---|---|---|
| `assignments` | `RT-04.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `assignments` | `RT-06.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `assignments` | `RT-07.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `assignments` | `RT-09.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `assignments` | `RT-11.S10~nta-scheme-tfi-bikes` | note | The split between the National Transport Authority and the local authority is not confirmed. |
| `assignments` | `RT-13.S12~nta-delivered-busconnects` | note | The Accountable party may be the local authority executive or the National Transport Authority; no handover provision was found. |
| `assignments` | `RT-13.S5G~nta-delivered-busconnects` | note | It is not confirmed who sanctions the National Transport Authority's own schemes. |
| `assignments` | `RT-14a.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `assignments` | `RT-29.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `assignments` | `RT-36.S13b~esb-openings` | note | The sources conflict: one records consultation only, another a licence requirement. |
| `assignments` | `RT-37.S11~garda-run-event-closures-eg-slane-2026` | note | The legal basis is not confirmed; no Council s.75 order was found. |
| `assignments` | `RT-38.S5G` | note | Inspection and acceptance of estate infrastructure. |
| `assignments` | `RT-42.S7b~s38-route` | note | Garda consultation under s.38(3) applies only to prescribed classes of measure, and none has been prescribed. Section 95(3)(b) of the Road Traffic Act 1961 requires Garda consultation where regulatory traffic signs are provided. The body that signs the Traffic Works Order is not confirmed. |
| `activities` | `RT-14a` | definition | Kerbs, hardstanding, footpath links and other civil works at bus stops, and approval of bus stop locations (s.16 RTA 2002; S.I. 12 of 2013). |
| `activities` | `RT-14b` | definition | Shelters, poles, flags and passenger furniture at bus stops, typically supplied and maintained through the NTA's shelter contractor. |
| `activities` | `RT-24` | definition | Special speed-limit bye-laws under s.9 RTA 2004 (reserved, s.9(10)), including 30 km/h urban limits, and other local road traffic bye-laws. Excludes national managed roads (RT-25), national default limits (RT-40) and road works speed limit orders (RT-37, boundary rule B12). S5G covers TII's prior consent on national roads. |
| `activities` | `RT-25` | definition | Speed-limit decisions on national roads: TII bye-laws on national managed roads (s.9A RTA 2004); LA bye-laws on other national roads with TII's prior written consent (s.9(7)). S5G follows boundary rule B9. |
| `activities` | `RT-36` | definition | Road opening licences (s.13(10) Roads Act 1993; MapRoad Roadworks Licensing), sectoral consents for statutory undertakers, s.101D RTA 1961 directions, co-ordination of works, the licence holder's works and reinstatement, and enforcement. |
| `activities` | `RT-37` | definition | Temporary road closure orders for events, works or other purposes (s.75 Roads Act 1993; Arts 12 and 14 Roads Regulations 1994), road works speed limit orders (s.10 RTA 2004), temporary traffic management, offences and cost recovery. |
| `activities` | `X-16` | definition | Transport impacts of planning applications, planning conditions requiring developer-delivered footpaths, cycle routes and junctions, development contributions (s.48 PDA 2000 → s.584 PDA 2024), discharge of conditions and release of security, and planning enforcement. Distinct from plan-making (X-08). |
| `activities` | `X-17` | definition | Programme-level funding functions: programme terms and conditions, envelope allocations (e.g. DoT → NTA, TII; DoT → LAs by formula), programme co-ordination contracts and programme reporting. Allocation to individual projects stays in S3 of each asset or service activity. |
| `activities` | `X-18` | definition | Event licences for audiences of 5,000 or more (s.230 PDA 2000; s.479 PDA 2024), whose conditions include traffic management plans agreed with the LA and An Garda Síochána. Road closures for events stay in RT-37. |
| `stages` | `S3` | definition | Allocating funding to a project or service within an activity, with the allocating body Accountable. Programme envelopes, terms and conditions sit in X-17. |
| `stages` | `S7D` | definition | A decision by a public body that fixes the legal status of land or an asset (declaring a road public; extinguishing a public right of way) or decides whether another party's development may proceed (planning permission, appeal, material contravention resolution). Excludes consent for the sponsor's own works (S7a–c), rules and licences governing use (S13a/b) and acceptance or discharge decisions (S5G). **Tie-break:** a decision that creates an offence for users of the asset is S13a/b. |
| `parties` | `AT` | description | Safe Routes to School co-ordination; Green-Schools. |
| `parties` | `DRCD` | description | Non-transport funding of transport assets (RRDF, ORIS). |
| `parties` | `DoE` | description | Safe Routes to School co-sponsor. |
| `parties` | `OPS` | description | Bus and Local Link operators; consulted on stops, priority and routes. |
| `parties` | `RMO` | description | Runs MapRoad and MapRoad Roadworks Licensing; national licence fees. |
| `parties` | `SCH` | description | SRTS applicants and partners; owners of school grounds. |
| `parties` | `WI` | description | Landowner for canal greenways (e.g. Royal Canal Greenway). |

### Rewrites added for version history

Added after the internal-reference pattern was widened to version/history
markers. They are appended after the first 31 entries, which are unchanged.
Each removes only the version tag or the history sentence.

| Table | Key | Field | Public text |
|---|---|---|---|
| `activities` | `RT-02` | definition | Routine and periodic maintenance, pavement renewal (e.g. surface dressing, strengthening/resurfacing) and rehabilitation of regional and local roads. Statutory duty of the road authority under s.13 Roads Act 1993; funded by own resources plus DoT Protection and Renewal grants. Improvement and new construction: RT-35; winter and emergency maintenance: RT-39. S6 covers conditional AA/EIA screening and exemption check. |
| `activities` | `RT-10` | definition | Plan, construct, improve, operate, regulate and maintain greenways. All greenways are treated as serving a transport function. S13a covers greenway bye-laws and S14 their enforcement. |
| `activities` | `RT-13` | definition | Physical bus lanes, bus gates and other infrastructure intended to prioritise bus movement. Excludes signal control operation. The delivering body may be the NTA (e.g. BusConnects Core Bus Corridors under s.51 Roads Act 1993). Post-construction maintenance party UNVERIFIED. |
| `activities` | `RT-19` | definition | Planning, coordination and development of rural and community road passenger transport services, including TFI Local Link. The NTA is responsible; 15 Transport Co-ordination Units administer operator contracts on its behalf. The LA has no funding, procurement or operating role in this activity; LA decisions sit in RT-14a.S13b (stop approvals), RT-15 (interchanges), X-08.S1 and RT-32.S2. |
| `activities` | `RT-30` | definition | Retired. Programme-level functions now sit in X-17; project allocation in S3 of each asset activity. Row retained for traceability only. |
| `activities` | `RT-31` | definition | Retired. Now stages S5–S9 of each asset activity, with consent routes S7a–S7c. Row retained for traceability only. |
| `activities` | `RT-38` | definition | Declaring roads public and taking estate roads, footpaths and public lighting in charge (s.11 Roads Act 1993; s.180 PDA 2000 until 25 Nov 2026, then s.261 PDA 2024, with s.263 transitional); extinguishing public rights of way. Transfers maintenance responsibility to the Local Authority. The order sits in S7D. |
| `activities` | `RL-06` | definition | Retired for consistency with RT-30. Programme level: X-17; project allocation: RL-01/RL-02 × S3. |
| `activities` | `AT-05` | definition | Retired for consistency with RT-30. Programme level: X-17; project allocation: AT-01 × S3. |
| `parties` | `DoE` | name | Department of Education |
| `parties` | `DRCD` | name | Department of Rural and Community Development |
| `parties` | `RMO` | name | Road Management Office / CCMA shared service |
| `parties` | `WI` | name | Waterways Ireland |
| `parties` | `OPS` | name | Public transport operators |
| `parties` | `AT` | name | An Taisce as programme co-ordinator |
| `parties` | `SCH` | name | Schools / Boards of Management |

## Decisions on the source material

`review_decisions.csv` records the ambiguities that were reviewed and left as
they are, so they leave the open review list without disappearing from the
record:

- both near-duplicate variant pairs are kept separate: the GDA lines record a
  separate open question and RT-17 appears only under the GDA variant; the
  Waterways Ireland lines record a different landowner question;
- `X-07` stays on grouping `X5` (electricity supply), with the register's
  candidate COFOG placement kept.

A decision on an error key that no longer exists fails the run, and a decision
may not clear a role error: roles go through `migration_resolutions.csv`.

## Still open

`migration_errors.json` is the review list. It records 5 unresolved `GS` role
tokens: `RT-10.S14` C, `RT-26.S14` C, `RT-37.S15` C, `RT-37.S11` (Garda-run
event closures) R and `RT-37.S14` (Offences) R. The research in
`gs_research.md` found no basis for the first three, and only an inferred basis
for the last two.

Roles still awaiting a ruling are absent from the published dataset. The
dataset README lists each as "role not yet published: awaiting review".
Applied rulings are removed from the error log.
