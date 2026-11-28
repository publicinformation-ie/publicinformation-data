# Design: transport RACI model (one framework for who does what in local transport)

Status: draft for review · 28 November 2026

## Intent

Make one canonical, reusable representation of **who does what in local transport in Ireland**, by activity and lifecycle stage, with a Responsible / Accountable / Consulted / Informed (RACI) assignment for each assessed combination. Store it as normalised data in this repo. Publish it as an open dataset. Then align everything else in the repo that describes transport roles to it, so there is a single framework and representation.

The data is **derived analysis**, not republished source data: publicinformation.ie compiled it from cited legislation, guidance and observed practice. Consumers must be able to tell that at a glance.

Derived works, such as chatbot-readable pages and a guide for elected representatives, belong in the peer repo `publicinformation-web`. This repo provides the data and an `llms.txt` entry point.

## Inputs

These come from a handoff exported from a claude.ai project. The copy in `docs/handoff-l4-raci/` is gitignored and must not be committed.

| File | Content |
|---|---|
| `L4_Activity_Register_v0.4.md` | Stages (Section 4), parties (Section 5), boundary rules B1–B14, the activity catalogue (Section 6), the 613-row register (Section 7), and methodology (Sections 1–3, 9–11) |
| `L4_RACI_Assignments_v0.1.csv` | 653 lines covering all 613 rows. 224 lines are assessed (Statute 51, Source 135, Default 14, UNVERIFIED 24); 429 are "Not assessed" |
| `L4_RACI_Assignments_v0.1_notes.md` | How the CSV works, evidence levels, open items |
| `L4_RACI_Publication_Brief_v0.1.md` | The original publication brief. Its constraints C1–C10 now mostly apply to `publicinformation-web`; see Non-goals |
| `L4_Sources.csv` | Sources S1–S176 with citations and URLs |

The scenario test report (`L4_Scenario_Test_Report_v0.3.md`) is not in the handoff. Scenario numbers in the CSV refer to it.

## Goals

**Project 1: the model and the dataset**
1. Store each axis of the matrix as its own normalised, hand-reviewed master table, separate from the sparse assignment data.
2. Migrate every existing assessment (the 224 assessed lines) into the master, deterministically, logging every value it cannot map. Nothing is guessed.
3. Reuse the repo's COFOG 1999 vocabulary by URI. Do not recreate COFOG.
4. Publish the axes as vocabularies and the assignments as a dataset, following the repo's existing conventions: DCAT catalogue, CSVW, versioned folders, `stamp_if_changed`, a single generator with `--check`.
5. Label the dataset as analytical and derived, using open-data best practice for provenance and per-assertion confidence.
6. Scope the assignments to **Meath County Council only**, as an MVP, and document that clearly.

**Project 3: align the repo**

This is a separate OpenSpec change, started after Project 1 is accepted.

7. Rebuild the `transport-governance` skill on the new model and retire its subdomain × function model.
8. Deprecate the `transport-subdomain` vocabulary and move SPC transport tagging onto the new model.
9. Update docs and routing (`AGENTS.md`, `scripts/AGENTS.md`, `DATA_SOURCES.md`, the public README, `CHANGELOG.md`).

## Non-goals

- Assessing any row that is not already assessed. Completing the matrix is a separate body of work. "Not assessed" is a valid published state.
- Chatbot pages, plain-language topic entry points, the "In short" summaries per activity, and the guide for elected representatives. These belong in `publicinformation-web`.
- Councils other than Meath.
- An MCP server or query API.
- Legal advice. The dataset says so explicitly.

## Anti-goals (failure even if it "works")

- Two live representations of transport roles in the repo.
- A stored 613-row register or stored "Not assessed" lines that can drift from the activity definitions.
- A migrated assignment that differs from the handoff without a logged, reviewable reason.
- A consumer mistaking this for official data or for republished source data.
- A copy of COFOG codes or labels, rather than links to the published vocabulary.

## The model

### Principle

There is one master per axis. The sparse matrix references the axes by ID and holds only assessed facts. Everything else, including the full row list and coverage, is generated.

### Master tables

They live under `reference/transport-raci/` (my call on the path). They are committed, hand-authored inputs, in the same spirit as `documents.yml` and override files: edited only through review, never by a generator.

The file format is CSV, so it diffs well and a human can review it. Prose fields (definitions, notes) are plain text cells.

| Table | Key | Fields | Notes |
|---|---|---|---|
| `stages.csv` | `stage_id` (S1…S15, S5G, S7a, S7b, S7c, S7D, S13a, S13b) | name, definition, sort_order | Register Section 4. |
| `groupings.csv` | `grouping_id` (RT1…RT9, WT1…WT4, RL1…RL5, AT1…AT4, OT1, OT2, X1…X7) | name, cofog_class, cofog_status (`confirmed` / `candidate`), status (`active` / `retired`) | The L4 level. `cofog_class` is a code that must exist in `public/vocabularies/cofog-1999.json`, and it is published as the `/ns/cofog#<code>` URI. X groupings carry `candidate` where the register says "candidate". |
| `activities.csv` | `activity_id` (RT-01…X-18) | name, definition (covers / excludes), status (`active` / `retired` / `placeholder`), register_note | Register Section 6. Retired activities (RT-30, RT-31, RL-06, AT-05) and placeholders (OT-01, OT-02) are kept, with their status, for traceability. |
| `activity_groupings.csv` | (activity_id, grouping_id) | is_primary | Many-to-many, because X-04, X-07 and X-12 sit in more than one grouping in the register. Exactly one primary grouping per activity. My call: model the ambiguity rather than pick a grouping. |
| `activity_cofog.csv` | (activity_id, cofog_code) | status (`confirmed` / `candidate`) | Only for activities whose COFOG placement differs from their grouping's, or is uncertain (X-01…X-18). Otherwise COFOG is inherited from the primary grouping. |
| `activity_stages.csv` | (activity_id, stage_id) | — | Which stages each activity has. The register's 613 rows are generated from this table. Applicability profiles (INF, MINOR and so on) are an authoring aid that stays in the methodology, not in data (my call). |
| `parties.csv` | `party_id` (DoT, NTA, TII, LA-M, LA-CE, …) | name, plain_label, kind (`body` / `organ` / `category`), public_body_uri, parent_party_id, description | Register Section 5. `body` = a public body in the `public-bodies` dataset (link by URI). `organ` = part of a body (LA-M and LA-CE are organs of the council named by the assignment's `applies_to`). `category` = a class such as delivery agents (DA), third parties (TP) or operators (OPS). Plain labels are taken from the skill's `vocabulary.md` where a body appears in both. |
| `variants.csv` | `variant_id` (slug) | label, description | One line per distinct variant. The handoff has about 40 free-text variants, some near-duplicates ("NTA-delivered (BusConnects)" / "… (BusConnects, GDA)"). The migration lists them; a human decides on any merge. |
| `evidence_levels.csv` | `evidence_id` (`statute`, `source`, `default-s149-4`, `unverified`) | label, plain_label, definition | Plain labels: "set by law", "stated in official guidance or observed practice", "assumed by default (an executive function because it is not reserved to elected members)", "not yet confirmed". "Not assessed" (plain label "not yet assessed") is a generated coverage state, not a stored level. |
| `boundary_rules.csv` | `rule_id` (B1…B14) | rule, source_decision | Needed to read some assignments. |
| `sources.csv` | `source_id` (S1…S176) | citation, urls (one or more), batch | From `L4_Sources.csv`. |
| `jurisdictions.csv` | `public_body_uri` | name, assessed_from, scope_note | One line for now: Meath County Council (`https://data.publicinformation.ie/body/meath-county-council`). It records which councils have been analysed and what "applies to" means. |

**Sparse matrix** (assessed facts only):

| Table | Key | Fields |
|---|---|---|
| `assignments.csv` | `assignment_id` (stable, e.g. `RT-09.S7b` or `RT-09.S7b~s38-route`) | activity_id, stage_id, variant_id (nullable), applies_to (public_body_uri), evidence_id, note, scenario_refs |
| `assignment_roles.csv` | (assignment_id, role, party_id, qualifier) | role is one of R, A, C, I. qualifier holds what the handoff wrote in brackets ("developer", "TCU", "ESB"). |
| `assignment_sources.csv` | (assignment_id, source_id) | — |

**Why roles are stored one per line** (my call): validation becomes simple and exact. The CSV's semicolon cells hide errors that the migration has already found, such as `DoE, AT (SRTS)` (a comma inside a cell), `prescribed bodies` (not a party) and `TII (national roads)`. The cost is that the files are less comfortable to edit by hand. A generated wide view (see Published outputs) covers reading and review.

**"No local authority role"** is not a stored value. It is derived and three-valued: `false` when an LA organ holds any role; `true` when the assignment has an Accountable party and no LA organ holds any role; `unknown` when it has no Accountable party, because the analysis has not established who decides. A row that nobody has assessed stays "not assessed". None of these collapse into each other.

**Public text layer.** The master keeps the handoff's prose exactly. Each published prose field has a `public_*` twin (`public_note`, `public_name`, `public_definition`, `public_description`) that equals the source unless the source cites an internal reference; then it comes from a reviewed entry in the committed `reference/transport-raci/public_text.csv`, keyed by table, record and field and pinned to the exact original text. A stale entry fails the migration. This keeps the committed master exactly reproducible from the handoff plus committed human inputs.

### Validation (fail closed)

A single validator runs in the generator and in tests:

- Every foreign key resolves: activity, stage, grouping, party, variant, evidence, source, jurisdiction. Every `cofog_class` and `cofog_code` exists in the published COFOG vocabulary.
- Every assignment's (activity, stage) is in `activity_stages`.
- At most one A per assignment. Zero A is allowed only when evidence is `unverified`, and the note must say why (10 such lines in the handoff).
- A party is never both A and C on the same assignment.
- A `category` party is never A, except TP under boundary rule B14. This follows the register's rule that contractors are never Accountable.
- (assignment_id) is unique, and (activity, stage, variant, applies_to) is unique.
- Every activity has exactly one primary grouping. Retired and placeholder activities have no stages and no assignments.

Any failure writes nothing and names the offending line.

### Migration (one-off)

`scripts/migrate_transport_raci_handoff.py` reads the handoff files (passed as paths) and writes the master tables plus a `migration_errors.json`.

- Deterministic parsing only. Party cells split on `;`. A bracketed suffix becomes `qualifier`. A cell that does not resolve to a known party, such as `prescribed bodies` or comma-joined parties, is logged as an error, and that role is not written until a human resolves it.
- Free-text variants become slugs. Near-duplicates are listed, not merged.
- Evidence strings map exactly (`Default (s.149(4))` → `default-s149-4`). Anything else is an error.
- "Not assessed" lines produce no assignment.
- Prose for the axes is parsed from the register's markdown tables (Sections 4, 5 and 6). Section 7 is used only as a cross-check: the generated row set must equal the register's 613 rows.
- The script is kept in the repo for traceability, but it is not part of the regular build. After migration the master tables are the source of truth.
- **Rulings are data, not edits.** Human decisions on logged errors live in a committed `reference/transport-raci/migration_resolutions.csv` (error key → ruling → ruled_by → date), which the migration reads. This keeps the migration reproducible and the rulings reviewable. Known cases the builder check found, with the deterministic handling chosen:
  - `prescribed bodies` (9 cells): becomes a `category` party `prescribed-bodies` (statutory consultees under the Part 8 regulations). My call.
  - `DoE, AT (SRTS)` (3 cells): splits into DoE and AT with qualifier `SRTS`, recorded as a resolution. My call.
  - `GS` (enforcement and safety bodies): splits into two `body` parties, AGS and RSA, both of which are in `public-bodies`. Each GS cell needs a ruling on which body is meant. `X-02.S14` (A = GS) is the one that matters, because a category can't be Accountable.
  - Near-duplicate variants: listed as proposed merges, each needing a ruling.
  - X-07's grouping "X5 / RT1-RT4" is logged as ambiguous. X7 ("Cross-cutting; classify by function") has a null `cofog_class`.
  - The Road Management Office (RMO) has no `public-bodies` entry. It is a `body` party with a null URI until that entry exists.

Acceptance (a one-off check at migration time, recorded in the change): the regenerated wide view equals the handoff CSV's assessed lines, except for the logged errors and their rulings. The row count is 613, with 184 rows assessed.

## Published outputs

One generator, `scripts/build_transport_raci.py`, is the only writer, following the `build_cofog_vocabulary.py` pattern. It validates, builds every output in memory, then writes through `stamp_if_changed`. `--check` exits non-zero on drift and names the file.

**Vocabularies** in `public/vocabularies/`, each as JSON, CSV + CSVW metadata and SKOS Turtle, with a `/ns/<name>` resolver page, like `cofog-1999`:
- `transport-stage`: the stages.
- `transport-activity`: groupings and activities as one SKOS scheme. Each activity is `skos:broader` its primary grouping. Each grouping is `skos:broader` its COFOG class URI (cross-scheme), or `skos:related` it where `candidate`. My call: one scheme, so that COFOG → grouping → activity reads as one hierarchy.
- `transport-raci-party`: parties, linking to `public-bodies` URIs where `kind = body`.
- `raci-evidence-level`: evidence levels with their plain labels.

**Dataset** `public/latest/transport-raci/` and the versioned `public/v0.1.0/transport-raci/`. The name is my call; it starts at 0.1.0 to signal a pre-stable MVP.
- `assignments.csv`, `assignment-roles.csv`, `assignment-sources.csv`, `variants.csv`, `sources.csv`, `boundary-rules.csv`, with CSVW metadata. Internal fields (`scenario_refs`, `source_decision`) are not published; see Decisions on release and references.
- `rows.csv` (generated): all 613 activity × stage rows with their coverage state (`assessed` / `not assessed`) and assessed-line count. This is the coverage statement.
- `raci-wide.csv` (generated, for reading): one line per assessed assignment, with R, A, C and I as readable party names and evidence as its plain label. It is derived, documented as a view, and never edited.
- `transport-raci.json`: everything nested by activity → stage → assignment, for LLM and programmatic use.
- `README.md`: what the data is, how it was made, scope (Meath only), how to read RACI and the evidence levels, known gaps, how to report a correction.
- `METHODOLOGY.md`: the register's methodology (Sections 1–3, 9 and 11, and the boundary rules), rewritten for the public, committed and reviewed. Not generated.
- `llms.txt`: entry point in the `public/documents/*/llms.txt` style. It links the README, methodology, JSON and wide view, and gives a short "how to answer a question with this" note.

**Catalogue** `public/catalog/dataset-transport-raci.ttl`:
- `dct:creator` is publicinformation.ie. The description says plainly that this is an analytical dataset compiled by publicinformation.ie, not official data and not republished source data.
- `dct:provenance` is a `dct:ProvenanceStatement` summarising the method and linking `METHODOLOGY.md`.
- `prov:wasDerivedFrom` lists each cited source URL.
- `dct:spatial` is Meath. `dct:relation` points to `public-bodies` and the COFOG vocabulary.
- `adms:status` is set to a pre-release / under-development value.
- Licence CC BY 4.0, as for the other datasets.
- Per-assertion confidence is carried in the data through `evidence_id`, not only at dataset level.

Also: `public/CHANGELOG.md` entry, `DATA_SOURCES.md` (the dataset is derived; sources are listed in the dataset), and links from the public README and get-the-data.

## Project 3: aligning the repo (outline, its own change)

- **`transport-governance` skill.** Rewrite it to route questions into the published vocabularies and dataset (grep `raci-wide.csv` / the JSON) instead of its own `raci-gda.md` and `vocabulary.md`. Keep its banned-terms table and the canonical-versus-plain register rule, re-expressed against the new IDs. Retire `raci-gda.md` and the subdomain and function sections of `vocabulary.md`.
- **`transport-subdomain` vocabulary.** Mark it deprecated (`owl:deprecated`, with a pointer to the new vocabulary) but keep it published and resolvable, because its URIs are already used. My call: published URIs are never removed.
- **SPC meetings dataset.** Replace subdomain tags with tags from the new vocabulary. The `subdomains` field is filled by the paid LLM step `extract_spc_items`. This is a schema change with a version bump and a changelog entry.
- **Docs.** Update the `AGENTS.md` routing table, `scripts/AGENTS.md`, the SPC README, `DATA_SOURCES.md` and `CHANGELOG.md`.

## Tests

In the root suite (`uv run pytest tests/ -q`):
- the validator rules, each with a failing fixture;
- pinned invariants on the committed master: 613 generated rows, 184 assessed rows, and 224 assessed lines less the exclusions in `migration_resolutions.csv`. The handoff is gitignored, so CI never reads it. The comparison with the handoff happens once, at migration time (above). After that the pinned counts guard the master, and a deliberate change to them is a reviewed edit;
- every COFOG reference resolves against `public/vocabularies/cofog-1999.json`;
- `--check` is a no-op on an unchanged master and detects hand edits;
- the vocabularies parse as SKOS Turtle, CSV and JSON agree, and URI patterns hold;
- the catalogue parses and carries the provenance properties above.

**Benchmark check** (manual, recorded in the change): answer the brief's six questions from `llms.txt` → README → JSON/wide view only. The answers must match the data, including honest "not yet assessed" answers for congestion, non-Local Link fares and train timetables.

## Left to the builder

- Exact column names, file names and JSON shape, within the structure above.
- Resolver page wording and layout, following `public/ns/cofog/`.
- Slug scheme for variant IDs and assignment IDs, as long as they are stable and readable.
- Whether the validator is a module shared by the generator and tests (preferred) or duplicated.

## Decisions on release and references

- **Release gate: publish now, gaps logged.** v0.1.0 ships with any role still awaiting a ruling left out of the published data. The README lists each one ("role not yet published: awaiting review") so a consumer sees the gap. Rulings are added later through `migration_resolutions.csv` and appear in the next build.
- **Non-public references stay internal.** Scenario numbers, F-numbers and Decision numbers stay in the master tables (`scenario_refs`, `boundary_rules.source_decision`, notes) but are stripped from every published output. Published notes cite only sources S1–S176 and boundary rules B1–B14. The generator removes the internal fields. Free-text notes that cite internal references aren't edited by the generator; the migration flags them. Each one gets a `public_note` in the master, rewritten without the reference and reviewed in the PR, and the generator publishes only `public_note`. A test fails if any published file contains a pattern like `F\d+` or `Decision \d+`, or a scenario reference. `METHODOLOGY.md` says the method was tested against 14 scenarios, without citing an unpublished report.

## Overlap with the existing skill (between Project 1 and Project 3)

The handoff asks for the RACI to be checked against `transport-governance/raci-gda.md` where they overlap. Project 1 produces a mismatch list (`reference/transport-raci/skill_mismatches.md`) and corrects neither side automatically. The new data is canonical. A mismatch that shows an error in the new data is fixed through `migration_resolutions.csv`; anything else is left for Project 3 to remove along with the skill. Two representations coexist only between the two changes. My call.

## Open items

These are recorded, not blocking:
- Missing assignment A parties and open findings (F9, F15, F22, F24, F34, F36) carry over as `unverified` assignments with notes, exactly as in the handoff.
- X-14 may duplicate RT-28 (register open question). Both are kept as-is.
