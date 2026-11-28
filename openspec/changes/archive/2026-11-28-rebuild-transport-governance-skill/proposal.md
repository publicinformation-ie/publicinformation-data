# Proposal

## Why

The transport RACI dataset (v0.1.0) replaced the hand-maintained model behind the
`transport-governance` skill. The skill still teaches that retired model, and the SPC
meetings dataset still tags agenda items with its `transport-subdomain` vocabulary, so
the repository now describes Irish transport governance three times: once as data, once
as skill prose, once as SPC tags. Two of those descriptions are already out of step with
the rulings and corrections in the dataset.

## What Changes

- Rebuild the `transport-governance` skill as a reader of the published dataset. It gains
  routing guidance (how to turn a question into activity × stage), a standing caveat that
  the assignments were analysed for Meath, rules for gaps, evidence and public wording,
  and a validation question set. `raci-gda.md` and the hand-maintained term tables go;
  the published vocabularies become the only terms.
- **BREAKING** In the SPC meetings dataset, `topics.subdomains` becomes
  `topics.groupings`, carrying transport-activity grouping IDs (`RT1`, `RL3`, …).
- Add a committed 17-row crosswalk from each retired subdomain to its grouping, applied
  during export. The paid `extract_spc_items` step is not re-run, so no decision text,
  item key or attendance record changes; the published tags are coarser and their
  provenance is stated.
- Retire the `transport-subdomain` vocabulary: its CSV and CSVW URLs stay, its terms are
  marked `owl:deprecated` with a `dct:isReplacedBy` link in a new Turtle file, and a
  retirement page and resolver page explain the replacement.
- Release the SPC meetings dataset as 2.0.0, and record the change in `public/CHANGELOG.md`
  and the dataset's DCAT record.
- Out of scope, deferred: `dct:spatial` as a location URI, and DCAT records for the four
  transport RACI vocabularies.

## Capabilities

### New Capabilities

- `transport-governance-skill`: how the agent skill answers a "who does what" transport
  question from the published transport RACI dataset, including its coverage caveat,
  gap handling, evidence and wording rules, and its validation set.

### Modified Capabilities

- `spc-topic-classification`: transport items are tagged with transport-activity
  groupings instead of the retired subdomains, through a committed crosswalk.
- `spc-meetings-dataset`: the items table publishes `groupings` instead of `subdomains`,
  the retired vocabulary is published as deprecated, and the dataset moves to 2.0.0.

## Impact

- `.claude/skills/transport-governance/`: rewritten `SKILL.md`, `vocabulary.md` and
  `checks.md`; `raci-gda.md` deleted.
- `pipelines/spc_pipeline/reference/transport_subdomains.json`: gains a grouping mapping
  per term and is frozen.
- `pipelines/spc_pipeline/scripts/build_vocabularies.py`: writes the deprecated Turtle,
  retirement page and resolver page.
- `scripts/transform_spc_meetings.py`, `public/schemas/spc-meetings.schema.json` and the
  SPC README: field rename, new output version `public/v2.0.0/spc-meetings/`.
- `tests/test_spc_meetings_dataset.py` and the transport RACI tests that reference the
  skill.
- `public/CHANGELOG.md`, `public/catalog/dataset-spc-meetings.ttl`,
  `pipelines/spc_pipeline/steps/extract_spc_items/README.md`.
- No pipeline step is re-run for pay; no assignment, decision or attendance record changes.
