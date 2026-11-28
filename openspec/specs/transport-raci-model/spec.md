# transport-raci-model Specification

## Purpose
Holds the single canonical representation of who does what in local transport. Each axis of the RACI matrix is its own committed master table, and a sparse matrix records only assessed facts, so that every published view is derived from one source.

## Requirements

### Requirement: Each axis is a separate master table

The master SHALL hold stages, L4 groupings, activities, activity–grouping links, activity–COFOG links, activity–stage links, parties, variants, evidence levels, boundary rules, sources and jurisdictions as separate committed CSV tables under `reference/transport-raci/`. Each table SHALL have a unique key, and no axis's attributes SHALL be repeated in another table.

#### Scenario: Axis tables exist with unique keys

- **WHEN** the master is loaded
- **THEN** every axis table is present and no key repeats within its table

#### Scenario: Duplicate key fails

- **WHEN** `activities.csv` contains `RT-09` twice
- **THEN** validation fails and names the table and key

### Requirement: The sparse matrix holds only assessed facts

Assignments SHALL be stored only for assessed activity × stage × variant combinations, scoped to one jurisdiction. Roles SHALL be stored one per line as (assignment, role, party, qualifier), with role one of R, A, C or I. Sources SHALL be stored one per line as (assignment, source). The master SHALL NOT store "Not assessed" lines or the full row register.

#### Scenario: Unassessed row has no assignment

- **WHEN** `RT-01.S1` has not been assessed
- **THEN** no assignment line exists for it in the master

#### Scenario: Multi-party role cell becomes several lines

- **WHEN** an assessed assignment has two Consulted parties
- **THEN** the master holds two role lines with role `C`, one per party

### Requirement: The row register is generated from activity stages

The full set of RACI rows SHALL be generated as the activity–stage links. Each row ID SHALL be `<activity_id>.<stage_id>`. Retired and placeholder activities SHALL have no stages.

#### Scenario: Register matches the handoff

- **WHEN** the rows are generated from the migrated master
- **THEN** there are 613 rows and their IDs equal the handoff register's Section 7 row IDs

#### Scenario: Retired activity has no rows

- **WHEN** rows are generated
- **THEN** `RT-30`, `RT-31`, `RL-06`, `AT-05`, `OT-01` and `OT-02` produce no rows

### Requirement: COFOG is referenced, never copied

Groupings and activities SHALL reference COFOG 1999 only by code. Every referenced code SHALL exist in `public/vocabularies/cofog-1999.json`, and each link SHALL carry a status of `confirmed` or `candidate`. The master SHALL NOT store COFOG labels or hierarchy.

#### Scenario: Unknown COFOG code fails

- **WHEN** a grouping references `04.5.9`
- **THEN** validation fails and names the grouping

#### Scenario: Candidate placement is kept

- **WHEN** the master is migrated
- **THEN** `X-01` is linked to `03.1.0` with status `candidate`

### Requirement: Every activity has one primary grouping

An activity MAY belong to more than one L4 grouping, but exactly one link SHALL be marked primary.

#### Scenario: Multi-grouping activity

- **WHEN** `X-04` is linked to `X1` and `RT8`
- **THEN** exactly one of the two links is primary and validation passes

#### Scenario: No primary fails

- **WHEN** an active activity has grouping links but none is primary
- **THEN** validation fails and names the activity

### Requirement: Parties are typed and linked to public bodies

Each party SHALL have a kind of `body`, `organ` or `category`. A `body` SHALL carry its `public-bodies` URI where one exists, and that URI SHALL exist in `public/latest/public-bodies/public-bodies.csv`. An `organ` SHALL name its parent party or, for council organs, belong to the assignment's jurisdiction.

#### Scenario: Body links to the public-bodies dataset

- **WHEN** party `NTA` is loaded
- **THEN** it has kind `body` and URI `https://data.publicinformation.ie/body/national-transport-authority-nta`

#### Scenario: Unknown body URI fails

- **WHEN** a body party's URI is not in `public-bodies`
- **THEN** validation fails and names the party

#### Scenario: Body without a public-bodies entry

- **WHEN** party `RMO` has no `public-bodies` entry
- **THEN** it is kind `body` with an empty URI and validation passes

### Requirement: Accountability rules are enforced

Each assignment SHALL have at most one Accountable party. It SHALL have none only when its evidence is `unverified` and its note is not empty. No party SHALL be both A and C on one assignment. A `category` party SHALL NOT be Accountable, except `TP` under boundary rule B14.

#### Scenario: Two Accountable parties fail

- **WHEN** an assignment has two `A` role lines
- **THEN** validation fails and names the assignment

#### Scenario: Unverified line without A

- **WHEN** `RT-10.S12` (Royal Canal Greenway variant) has no A, evidence `unverified` and a note
- **THEN** validation passes

#### Scenario: Category Accountable fails

- **WHEN** an assignment has party `DA` as A
- **THEN** validation fails

### Requirement: References resolve and combinations are unique

Every foreign key in the sparse matrix SHALL resolve to its axis table. Each assignment's (activity, stage) SHALL be an activity–stage link. The pair (activity, stage, variant, jurisdiction) SHALL be unique.

#### Scenario: Assignment on a stage the activity lacks

- **WHEN** an assignment references `RT-19.S7a` and `RT-19` has no `S7a`
- **THEN** validation fails and names the assignment

#### Scenario: Unknown source fails

- **WHEN** an assignment cites `S999`
- **THEN** validation fails

### Requirement: Validation fails closed

A validation failure SHALL stop the build before any output is written, and SHALL report every failing line with its table and key.

#### Scenario: One bad line blocks all output

- **WHEN** one role line references an unknown party
- **THEN** no published file changes, and the error names `assignment_roles.csv` and the line

### Requirement: The handoff migrates deterministically

A one-off migration SHALL read the handoff register and CSV from paths given as arguments and write the master tables and a migration error log. It SHALL map values by exact rules only. Any value it cannot map SHALL be logged and left out, and the migration SHALL NOT guess. Running it twice on the same inputs SHALL produce identical bytes.

#### Scenario: Unmappable party is logged

- **WHEN** a role cell contains a value that is neither a known party nor covered by a ruling
- **THEN** that role is not written, and the error log records the row ID, column and value

#### Scenario: Not assessed lines produce nothing

- **WHEN** the handoff CSV line has evidence `Not assessed`
- **THEN** no assignment is written for it

#### Scenario: Migration acceptance counts

- **WHEN** the migration runs on the v0.4 register and the v0.1 CSV
- **THEN** 184 distinct rows have assignments, and 224 assessed lines are written or logged

### Requirement: Human rulings are recorded as data

Rulings on migration errors SHALL be held in a committed `migration_resolutions.csv` with the error key, the ruling, who ruled and the date. The migration SHALL apply rulings it finds and SHALL log any error that has no ruling. A ruling that matches no error SHALL fail the migration.

#### Scenario: Ruling applied

- **WHEN** a resolution maps `GS` on `X-02.S14` to `AGS`
- **THEN** the migrated role line has party `AGS`, and the error is not in the log

#### Scenario: Stale ruling fails

- **WHEN** a resolution's error key matches nothing in the handoff
- **THEN** the migration fails and names the resolution

### Requirement: The master is pinned in tests

Tests SHALL pin the generated row count (613), the count of assessed rows (184) and the count of assessed lines (224 less the lines excluded by recorded rulings), without reading the gitignored handoff.

#### Scenario: Hand edit changes counts

- **WHEN** an assignment is deleted from the master without a matching ruling
- **THEN** the pinned-count test fails
