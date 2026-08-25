# statespend_pipeline

Maps the [statespend.ie](https://statespend.ie) public-body list onto our canonical
`public_body_id` register. statespend.ie is a React SPA backed by an internal JSON API with no
registry/website/CRO linkage on their side — the only foreign identifiers are a dense integer
`id`, a display `label`, and a coarse `entity_type`. See
`docs/superpowers/plans/2026-08-25-statespend-bodies-pipeline.md` for the full source-system
analysis and quantified mapping tiers this pipeline implements.

## Steps

1. **`fetch_statespend_bodies`** — paginates `GET /api/rank?dim=bodies&metric=count&limit=…&offset=…`
   (no auth). Fatal-exits on request failure, non-JSON (the SPA fallback returns 200+HTML),
   fewer than `MIN_BODY_COUNT` bodies, or duplicate ids. Record shape:
   `{statespend_id, statespend_name, statespend_entity_type, statespend_url}`.
2. **`match_public_bodies`** — fuzzy-matches `statespend_name` against the CSO-register-derived
   candidate pool via `src/lib/body_matching.py` (`MATCH_THRESHOLD = 0.90`, deliberately not
   lowered). Writes `match_log.json` with every best score so near-misses are auditable without a
   re-crawl, and runs a soft `entity_type` cross-check that flags inconsistencies into the log
   rather than failing.
3. **`apply_overrides`** — applies committed `override.json` corrections keyed by
   **`str(statespend_id)`** (JSON keys are strings; record ids are ints — see the docstring in
   `process.py`). Drops still-unresolved records (Tier D: NTMA internal fund accounts, DPER
   pseudo-offices, bodies with no canonical counterpart) but logs every drop with its reason to
   `dropped.json` per the fail-closed rule in AGENTS.md. Non-null override ids are verified to
   exist in the canonical register at runtime; a miss fatal-exits.

## Override authoring rules

- Every non-null value must be verified by name lookup against
  `pipelines/cso_pipeline/steps/resolve_website_urls/output.json` before being written — never
  typed from memory (wrong-id incident class, see foi_pipeline AGENTS.md).
- An explicit `null` suppresses a wrong ≥0.90 fuzzy match *and* records the drop decision
  (NTMA ×3, DPER OGCIO/OGP, Moorepark, KARE Central Services, Credit Review Office,
  Companies Registration Office, Houses of the Oireachtas Service, Judicial Council,
  Royal Irish Academy of Music, National Asset Management Agency).
- Renamed/successor bodies are mapped deliberately (e.g. An Bord Pleanála → An Coimisiún
  Pleanála, Irish Water → Uisce Éireann, BAI → Coimisiún na Meán); where two statespend rows
  intentionally collapse onto one canonical body (SFI + Research Ireland → Taighde Éireann),
  that is recorded here as expected behaviour, not a dedup bug.
