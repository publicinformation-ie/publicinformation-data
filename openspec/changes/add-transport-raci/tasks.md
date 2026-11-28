# Tasks

## 1. Master tables and validator

- [x] 1.1 Create `src/lib/transport_raci/` with a loader. It reads every table in `reference/transport-raci/` into typed records: stages, groupings, activities, activity_groupings, activity_cofog, activity_stages, parties, variants, evidence_levels, boundary_rules, sources, jurisdictions, assignments, assignment_roles, assignment_sources, migration_resolutions. Verify with a loader test over a small fixture master in `tests/fixtures/transport_raci/`.
- [x] 1.2 Implement the validator in `src/lib/transport_raci/validate.py`. It returns every error with its table and key, and never stops at the first. Rules:
  - unique keys;
  - foreign keys resolve;
  - COFOG codes exist in `public/vocabularies/cofog-1999.json`;
  - body URIs exist in `public-bodies.csv`;
  - an assignment's (activity, stage) is an activity–stage link;
  - (activity, stage, variant, jurisdiction) is unique;
  - at most one A, and zero A only when evidence is `unverified` with a note;
  - no party is both A and C;
  - a category is never A, except TP;
  - exactly one primary grouping per active activity;
  - retired and placeholder activities have no stages.

  Verify with one failing-fixture test per rule in `tests/test_transport_raci_validate.py`, plus a passing test on the fixture master.
- [x] 1.3 Implement row generation `generate_rows(master) -> list[Row]` (row ID `<activity_id>.<stage_id>`, coverage state, assessed-line count). Verify with a fixture test, including that retired activities produce no rows.
- [x] 1.4 Run `uv run pyright` and `uv run pytest tests/test_transport_raci_validate.py -q` and verify both are clean.

## 2. Migration from the handoff

- [x] 2.1 Write `scripts/migrate_transport_raci_handoff.py --register <md> --assignments <csv> --sources <csv> --out reference/transport-raci/`. It parses the register's Sections 4, 5 and 6 tables into the axis tables and the CSV into the sparse matrix, using exact rules only:
  - party cells split on `;`;
  - a bracketed suffix becomes the qualifier;
  - evidence strings map exactly to evidence IDs;
  - variants become slugs;
  - "Not assessed" lines are skipped.

  Every unmappable value goes to `reference/transport-raci/migration_errors.json` (row ID, column, value, reason), and the value is left out. Verify with a test on a small synthetic register and CSV in `tests/fixtures/`, covering each error class.
- [x] 2.2 Apply rulings from `migration_resolutions.csv` (error key, ruling, ruled_by, date). A ruling that matches no error fails the run. Pre-seed rulings for the deterministic cases in design.md:
  - `prescribed bodies` becomes the `prescribed-bodies` category;
  - `DoE, AT (SRTS)` becomes DoE and AT with qualifier SRTS.

  Verify with tests for an applied ruling and a stale ruling.
- [x] 2.3 Add `public_note` handling. A note matching an internal reference (`\bF\d+\b`, `Decision \d+`, scenario references) is flagged in the error log as `needs_public_note`; other notes are copied to `public_note`. Verify with a fixture test.
- [x] 2.4 Run the migration on `docs/handoff-l4-raci/` and commit the master tables and resolutions. `migration_errors.json` is committed too, as the review list. Verify with a one-off check recorded in the PR description:
  - 613 generated rows equal the register's Section 7 IDs;
  - 184 assessed rows;
  - 224 assessed lines, either written or logged;
  - running the migration twice gives byte-identical output.
- [x] 2.5 Write `public_note` text for every flagged note, as a reviewed edit to the master. Verify that `migration_errors.json` has no `needs_public_note` left. (Revised: the rewrites now live in the committed `public_text.csv`, which the migration applies; activity, stage and party prose has `public_*` twins handled the same way.)
- [x] 2.6 Add `tests/test_transport_raci_master.py`. It validates the committed master, pins the 613, 184 and 224-less-exclusions counts, and checks that `migration_errors.json` lists every unresolved role. Verify that it passes without `docs/` present (run it with the handoff folder moved away).
- [x] 2.7 Produce `reference/transport-raci/skill_mismatches.md`, comparing assignments with `.claude/skills/transport-governance/raci-gda.md` where they overlap: national and regional roads, active travel, bus infrastructure, speed limits, kerbside. Change neither side. Verify that the file lists each compared pair with agree or mismatch.

## 3. Vocabularies

- [x] 3.1 In `scripts/build_transport_raci.py`, build `transport-stage`, `transport-activity`, `transport-raci-party` and `raci-evidence-level`, each as JSON, CSV, CSVW metadata and SKOS Turtle, following `scripts/build_cofog_vocabulary.py`:
  - URIs are `/ns/<vocabulary>#<notation>`;
  - activities are `skos:broader` their primary grouping and `skos:related` any other grouping;
  - a grouping is `skos:broader` its confirmed COFOG class URI, or `skos:related` a candidate one;
  - parties have `skos:exactMatch` to their public-bodies URIs;
  - evidence levels carry the plain labels in the spec, plus `not-assessed`.

  Verify with tests in `tests/test_transport_raci_vocabularies.py`: distributions agree, CSVW contract, Turtle parses, RT3 → `cofog#04.5.1` broader, X1 → `cofog#03.1.0` related only, no COFOG concept declared, RT-30 is published as retired.
- [x] 3.2 Add resolver pages `public/ns/<vocabulary>/index.html` for the four vocabularies, modelled on `public/ns/cofog/`, and a README per vocabulary in `public/vocabularies/`. Verify with a test that each page links every distribution.
- [x] 3.3 Add `--check`: it exits non-zero and names each differing file. Writes go through `stamp_if_changed`. Verify with tests that regeneration is a no-op and that a hand edit is detected.

## 4. Dataset

- [x] 4.1 Build `assignments.csv`, `assignment-roles.csv`, `assignment-sources.csv`, `variants.csv`, `sources.csv`, `boundary-rules.csv` and their CSVW metadata. They use vocabulary URIs, drop the internal fields, and leave out unresolved roles. Write them to `public/latest/transport-raci/` and `public/v0.1.0/transport-raci/`. Verify with tests that the two trees are byte-identical, roles reference `/ns/transport-raci-party#`, and every line's jurisdiction is Meath.
- [x] 4.2 Build `rows.csv` (coverage), `raci-wide.csv` (the reading view, with a derived no-local-authority-role flag) and `transport-raci.json` (activity → stage → assignments). Verify with tests:
  - `rows.csv` has 613 rows, 184 of them assessed;
  - `RL-03.S2` is not assessed;
  - for `RT-09.S12`, A is the council executive and evidence reads "set by law";
  - the JSON and the CSVs agree;
  - the no-local-authority-role flag is correct on a fixture line.
- [x] 4.3 Add the leak check: every published file is scanned for internal references, and a missing `public_note` fails the build. Verify with tests on the real output and a failing fixture.
- [x] 4.4 Write `public/latest/transport-raci/METHODOLOGY.md` by hand. It covers the register's Sections 1–3, 9 and 11 rewritten for the public: COFOG anchoring, activities × stages, the two council organs, the boundary rules, testing against 14 scenarios without citing the unpublished report, and the Meath scope. The generator copies it to the versioned tree. Verify that it has been reviewed in the PR and that the leak check passes on it.
- [x] 4.5 Generate `README.md` and `llms.txt`:
  - both carry the Meath-only scope statement (Meath is in the GDA);
  - the README also covers how to read RACI and the evidence levels, coverage numbers, the list of unresolved items as "role not yet published: awaiting review", not legal advice, and how to report a correction;
  - `llms.txt` uses absolute URLs to the README, methodology, JSON and wide view, plus a short "how to answer a question" note.

  Verify with tests that the scope statement is present in both and every `llms.txt` link exists in the tree.
- [x] 4.6 Write `public/catalog/dataset-transport-raci.ttl`:
  - title, and a description stating that this is analysis by publicinformation.ie, not official or republished data;
  - `dct:provenance` linking the methodology;
  - `prov:wasDerivedFrom` per cited source URL;
  - `dct:spatial` Meath, pre-release `adms:status`, `owl:versionInfo "0.1.0"`, CC BY 4.0;
  - `dct:relation` to public-bodies and COFOG;
  - distributions.

  Verify with a test that it parses and has those properties.

## 5. Discovery, docs and benchmark

- [x] 5.1 Link the dataset and vocabularies from `public/README.md`, `public/GET_THE_DATA.md`, `public/get-the-data.html` (every CSV, with a plain description). `public/index.html` is only a redirect to the public README, so it has no reference list and needs no change. Add a `public/CHANGELOG.md` entry, a `DATA_SOURCES.md` entry, and entries in `scripts/README.md` and `scripts/AGENTS.md` for both scripts. Verify that the existing discovery guard test passes for `transport-raci`.
- [x] 5.2 Run the benchmark. Answer the brief's six questions using only `llms.txt` and the files it links, and record each answer in the PR description: bus routes, active travel maintenance and greenways answered with confidence; congestion, non-Local Link fares and train timetables answered "not yet assessed". Verify that no answer needs data outside those links.
- [x] 5.3 Run the full checks: `uv run pytest tests/ -q`, `uv run pyright`, and `uv run python scripts/build_transport_raci.py --check` (exits 0). Review the generated `public/` diff before merging.
  - Note: the full root suite has one pre-existing failure, `tests/test_spc_meetings_dataset.py::test_every_real_exported_record_validates_and_links_its_body`, which reads stale local SPC output and is unrelated to this change.

## 6. Rulings and corrections (28 November 2026)

- [x] 6.1 Research the 35 `GS` cells against primary law and official guidance; record the findings and citations in `reference/transport-raci/gs_research.md`.
- [x] 6.2 Record Dave's rulings in `migration_resolutions.csv`: 30 cells resolved (29 × `AGS`, plus `RT-26.S13a` C → `RSA; AGS`), 5 left unresolved (`RT-10.S14` C, `RT-26.S14` C, `RT-37.S15` C, `RT-37.S11` Garda-run closures R, `RT-37.S14` Offences R).
- [x] 6.3 Record evidence per ruled role. Add `evidence_id`, `source_ids` and `rationale` to rulings; add `evidence_id` to `assignment_roles.csv`; add the cited provisions as `added_sources.csv` (`P1`–`P13`); link ruling sources to the assignment. Publish the per-role evidence and mark it in the wide view.
- [x] 6.4 Add the corrections layer. `corrections.csv` corrects facts that are not role errors, with a staleness check: the X-18 event-licensing law change (Part 16 PDA 2024, S.I. 468/2026, repeal of Part XVI PDA 2000), the Meath source page note, and RT-37.S14 offences C → R under s.81(3)(a) Roads Act 1993. Add the HSE as a party and publish it, with the NTA, as Consulted on X-18.S13b.
- [x] 6.5 Correct the seven `s.38 route` public notes: the s.38(3) duty applies only to prescribed classes of measures and none has been prescribed; the operative duty is s.95(3)(b) RTA 1961 where regulatory signs are provided.
- [x] 6.7 Record Dave's decisions on the source ambiguities in `review_decisions.csv`: both variant pairs kept separate, X-07 kept on X5. The item leaves the error log, the decision stays in the record, and the README lists it.
- [x] 6.6 Update the docs (`migration_notes.md`, `skill_mismatches.md`, the dataset README review list) and the tests, including the byte-for-byte rerun with the new inputs.

## Workflow follow-up

- Remaining review items after the rulings: the 5 unresolved `GS` cells, the 2 variant merges, the X-07 grouping, and the `public_text.csv` drafts (47 rewrites). Each ruling ships in a later build.
- Start the follow-up change: rebuild the `transport-governance` skill on this model, deprecate `transport-subdomain`, and re-tag SPC (paid step `extract_spc_items`).
- Archive this change after review and publication.
