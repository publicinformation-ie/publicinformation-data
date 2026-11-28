# Tasks

## 1. Crosswalk and SPC export

- [x] 1.1 Add `grouping_ids` to each of the 17 entries in
  `pipelines/spc_pipeline/reference/transport_subdomains.json` per the design table, with a
  recorded reason where the list is empty, and mark the file frozen in its metadata.
  Verify: a test loads the file and asserts 17 entries, each with a non-empty list or a
  reason.
- [x] 1.2 Map the classification step's `subdomains` to `groupings` in
  `scripts/transform_spc_meetings.py`, deduplicated and ordered, and raise a recorded error
  for a subdomain the crosswalk does not hold.
  Verify: a unit test maps `infra/regional-local-roads` to `RT1` and raises on an unknown
  tag.
- [x] 1.3 Rename the published field in the items table (CSV column, JSON-LD property,
  CSVW description and separator) from `subdomains` to `groupings`, and set the JSON
  Schema enum to the grouping notations in `public/vocabularies/transport-activity.csv`.
  Verify: `test_csvw_marks_pipe_separated_arrays`,
  `test_published_vocabulary_notations_match_the_schema_enums` and the items CSV test pass
  with the new name.
- [x] 1.4 State in the SPC README that transport groupings are mapped from the earlier
  subdomain tagging and are coarser than it, and link the `transport-activity` vocabulary
  in place of `transport-subdomain`.
  Verify: the README text is published in the rebuilt export and a test asserts the
  mapping sentence is present.
- [x] 1.5 Update the rest of `tests/test_spc_meetings_dataset.py` and any fixture that
  names `subdomains`.
  Verify: `uv run pytest tests/test_spc_meetings_dataset.py -q` passes.

## 2. Retire the subdomain vocabulary

- [x] 2.1 Extend `pipelines/spc_pipeline/scripts/build_vocabularies.py` to write
  `public/vocabularies/transport-subdomain.ttl` (SKOS, every term `owl:deprecated` with
  `dct:isReplacedBy`, and a note for the term with no replacement),
  `transport-subdomain.md`, and a resolver page at `public/ns/transport-subdomain/`.
  Verify: the files are written and the Turtle parses with 17 deprecated terms.
- [x] 2.2 Leave `transport-subdomain.csv` and its CSVW metadata byte-identical.
  Verify: `git diff` shows no change to either file.
- [x] 2.3 Add a test that every term's replacements match the crosswalk and that the
  no-replacement term carries its reason.
  Verify: `uv run pytest tests/test_spc_meetings_dataset.py -q` passes.
- [x] 2.4 Point the vocabulary links in the SPC README, `public/GET_THE_DATA.md`,
  `public/get-the-data.html` and `public/latest/spc-meetings/README.md` at
  `transport-activity`, noting that `transport-subdomain` is retired.
  Verify: no public page describes the subdomains as the current transport vocabulary.

## 3. Release spc-meetings 2.0.0

- [x] 3.1 Move the export to `public/v2.0.0/spc-meetings/`, bump `owl:versionInfo` to
  `2.0.0` in `public/catalog/dataset-spc-meetings.ttl`, and add a `public/CHANGELOG.md`
  entry naming the removed `subdomains` field and its replacement.
  Verify: the rebuilt dataset lands in `v2.0.0`, `latest` mirrors it, and
  `public/v1.2.0/spc-meetings/` is unchanged.
- [x] 3.2 Rebuild with `cd pipelines/spc_pipeline && uv run python process.py --force
  --stop-on-error --from extract_spc_items` is **not** required; run the export steps only
  (`--from render_spc_minutes` onward is fine) so no model is called.
  Verify: no step reports an LLM call, and the diff against `v1.2.0` touches only the items
  table and the README.

## 4. Rebuild the skill

- [x] 4.1 Rewrite `.claude/skills/transport-governance/SKILL.md`: what it reads, the
  routing procedure, the Meath caveat for other councils, the gap rule, the evidence rule,
  and the analysis disclaimer.
  Verify: the description still triggers on "who does what in transport" questions.
- [x] 4.2 Shrink `vocabulary.md` to the question vocabulary the dataset does not publish
  (aliases, banned terms) and point every definition at the published vocabularies.
  Verify: no RACI row table or restated party/activity definition remains in the file.
- [x] 4.3 Rewrite `checks.md`'s questions and expected answers against rows that exist in
  the published dataset, keeping the trap coverage (national vs regional roads, Part 8 vs
  s.38, kerbside parking, school transport, greenway enforcement) and adding a deliberate
  gap question.
  Verify: every expected assignment ID in the table exists in
  `public/latest/transport-raci/rows.csv`.
- [x] 4.4 Delete `raci-gda.md` and update any reference to it (`AGENTS.md`, the skill's own
  files).
  Verify: `grep -r raci-gda` returns nothing in tracked files.
- [x] 4.5 Add `tests/test_transport_governance_skill.py`: every assignment ID in
  `checks.md` exists in the published dataset, every link target in the skill exists, and
  the skill holds no row table.
  Verify: `uv run pytest tests/test_transport_governance_skill.py -q` passes.

## 5. Verification

- [x] 5.1 Run the root suite, the transport RACI suite and pyright.
  Verify: `uv run pytest tests/ -q` shows only the known SPC stale-output failure before
  the rebuild and none after; `uv run pyright` reports no errors.
- [x] 5.2 Run `openspec validate rebuild-transport-governance-skill --strict`, then review
  the `public/` diff before merging.
  Verify: validation passes and the diff contains only the items field rename, the
  vocabulary retirement files and the README/CHANGELOG text.

## Workflow follow-up

- Archive the change and sync its specs into `openspec/specs/` with
  `openspec archive rebuild-transport-governance-skill --yes`.
- Deferred: `dct:spatial` as a location URI, and DCAT records for the four transport RACI
  vocabularies.
