# Proposal

## Why

Who does what in local transport is currently described in a draft L4 activity register and a RACI CSV, kept outside the repo, and the repo's `transport-governance` skill holds a second, incompatible model. We need one canonical representation, anchored on the COFOG vocabulary that is already published. It must be stored as normalised data and published as open data, so that LLMs, the peer `publicinformation-web` repo and future derived works can all use it. It also has to be clearly labelled as analysis by publicinformation.ie rather than republished official data.

## What Changes

- Add committed master tables under `reference/transport-raci/`:
  - one table per axis: stages, L4 groupings, activities and their links, parties, variants, evidence levels, boundary rules, sources and jurisdictions;
  - a sparse matrix that holds only assessed facts: assignments, one line per role, and their sources;
  - a resolutions file for human rulings on migration errors.
- Add a one-off, deterministic migration from the handoff register and CSV (gitignored, under `docs/handoff-l4-raci/`). Every value it can't map is logged; nothing is guessed.
- Add one validator and one generator, `scripts/build_transport_raci.py`, with `--check`. Both fail closed. The generator derives:
  - the 613-row register and its coverage, which are never stored;
  - four SKOS vocabularies (stages, activities with their groupings, parties, evidence levels) that link to the existing COFOG 1999 vocabulary by URI;
  - the `transport-raci` dataset at v0.1.0: tables, a wide reading view, nested JSON, README, `llms.txt`, a DCAT record with provenance, and resolver pages.
- Scope every assignment to Meath County Council and say so throughout.
- Keep scenario, F- and Decision references in the master only. Published outputs cite only sources S1–S176 and boundary rules B1–B14.
- Produce a mismatch list against the existing `transport-governance` skill. No automatic corrections.
- Not in this change: rebuilding the skill, deprecating `transport-subdomain` and re-tagging SPC. Those come in a follow-up change. Chatbot pages and guides go in `publicinformation-web`.

## Capabilities

### New Capabilities

- `transport-raci-model`: the committed master tables (the axes and the sparse matrix), the validation rules every build enforces, the migration from the handoff, and the resolutions mechanism.
- `transport-raci-vocabularies`: the published stage, activity, party and evidence-level vocabularies, with their URIs, distributions, resolver pages and links to COFOG 1999 and `public-bodies`.
- `transport-raci-dataset`: the published RACI dataset. Covers its tables and generated views, coverage statements, Meath scope, labelling as analytical data with provenance, removal of non-public references, `llms.txt`, catalogue and documentation.

### Modified Capabilities

None. `cofog-vocabulary` is consumed unchanged.

## Impact

- **New:** `reference/transport-raci/*.csv`, `scripts/migrate_transport_raci_handoff.py`, `scripts/build_transport_raci.py`, a shared validator module, `tests/test_transport_raci*.py`.
- **New published files:**
  - `public/vocabularies/transport-stage.*`, `transport-activity.*`, `transport-raci-party.*`, `raci-evidence-level.*`;
  - `public/ns/<name>/index.html`;
  - `public/latest/transport-raci/` and `public/v0.1.0/transport-raci/`;
  - `public/catalog/dataset-transport-raci.ttl`.
- **Updated docs:** `public/README.md`, `public/GET_THE_DATA.md` and `get-the-data.html`, `public/CHANGELOG.md`, `DATA_SOURCES.md`, `scripts/README.md`, `scripts/AGENTS.md`.
- **No network, paid steps or database writes.** It reads `public/vocabularies/cofog-1999.json` and `public/latest/public-bodies/public-bodies.csv`.
- Publication happens through the normal `public/` merge to `main`, after the generated diff has been reviewed.
