# Scaling the FOI Pipeline to 883 Bodies / 200k+ Records — Umbrella Design

**Date:** 2026-06-04
**Status:** Draft (awaiting review)
**Spec Location:** `docs/superpowers/specs/2026-06-04-scaling-pipeline-to-883-bodies-design.md`

---

## Overview

### Summary

The pipeline is expanding from **157 public bodies to 883**, with an expected
**200,000+ FOI disclosure records**. This umbrella design re-shapes how the
project *stores and distributes* data so it scales without bloating git, slowing
the website build, or making per-body maintenance painful.

The architecture spine is a single inversion of responsibility:

> **`publicinformation-data` is the canonical, self-contained data store and
> distributor. The SQLite/libSQL database the pipeline builds is the single
> source of truth. Everything published is derived from it and distributed as
> Codeberg release assets, so the data survives even if the website dies.
> `publicinformation-web` becomes a pure *consumer* that generates nothing
> canonical.**

This is an *umbrella* spec covering three loosely-coupled subsystems. Each gets
its own implementation plan after this design is approved:

- **A — Artifacts & git de-bloat** (this repo) — *independently shippable first.*
- **B — Incremental per-body processing at scale** (this repo).
- **C — Website build scaling & decoupling** (the web repo).

### Binding constraints (from the user)

The user identified three pains driving this work — **git repo bloat**,
**website load/build performance**, and **maintainability**. Raw pipeline
*throughput* was explicitly **not** a primary concern.

### Guiding principles (from the user)

1. `publicinformation-data` must **not depend on** `publicinformation-web`.
   Third parties must be able to build on this repo standalone.
2. If the database is the source of truth, **it belongs in this repo** and must
   be a published, downloadable artifact.
3. The repo must remain usable to **download all data**. "If the website dies,
   Codeberg remains."
4. Distribution is via **Codeberg release assets** (not committed to git
   history), keeping `git clone` lean while satisfying (3).
5. Open data is published as a **single normalized + compressed bulk artifact**
   (plus the DB), *not* per-body shards.

### Goals

1. Remove large generated data from git history-going-forward; keep `git clone`
   lean.
2. Make the database a first-class, repo-owned, downloadable artifact.
3. Publish normalized + compressed open-data artifacts as Codeberg release
   assets on each run.
4. Sever the website's filesystem/codegen coupling to this repo; the website
   consumes only a `DATABASE_URL` or a downloaded release DB.
5. Make ongoing data refresh at 883 bodies incremental: detect changed sources
   automatically; upsert the DB instead of full-reloading it.

### Non-Goals

1. Per-body sharded output files (the user chose a single bulk artifact).
2. A new multi-body CLI flag — `--public-body` is deliberately single-ID
   (Non-Goal in `2026-06-02-public-body-filter-design.md`); we reuse it.
3. Rewriting the pipeline step model, step order, or the `results` /
   `public_bodies` output schemas.
4. Resolving the website's FOI-pagination rendering strategy — explicitly
   **deferred to Plan C** (see Open Questions).
5. Changing the libSQL schema's *meaning*; `schema.sql` remains the contract.

---

## Background: what already exists (verified)

This design deliberately *reuses* substantial existing machinery rather than
inventing parallel systems.

### Data flow today

```
source sites
  └─▶ pipeline steps (find_public_bodies … extract_disclosures_*)
        ├─ each step: output.json (+ status.json, errors.json, dirty_ids.json)   [gitignored]
        ├─ export_status  ─▶ public/foi-disclosures.json (24.6 MB), pipeline-data.json   [COMMITTED]
        ├─ generate_topics ─▶ public/topics.json (1.6 MB)                                  [COMMITTED]
        └─ db_upload ─▶ libSQL DB  (local.db, or remote Bunny via DATABASE_URL)   [local.db gitignored]
                          └─▶ website (publicinformation-web) reads the DB
```

### Key verified facts

- **The website already reads the DB, not the JSON.** `fetchData.ts` uses
  `@libsql/client` and queries per body (`WHERE public_body_id = ?`). The site
  is fully static (SSG) and *already paginates* FOI per body
  (`body/[id]/foi/[page].astro`). The big `public/*.json` files are **not**
  website inputs.
- **`public/*.json` is purely (a) open-data download + (b) a denormalized
  mirror.** `db_upload` reads *step* outputs, not `public/`.
- **No runtime dependency on the web repo exists** (only archived-doc
  references). The web `downloads/[dataset].{json,csv}.ts` endpoints export only
  lightweight *body-metadata* lists — not the FOI records.
- **Compression is dramatic:** `foi-disclosures.json` 24.6 MB → **2.6 MB
  gzipped** (9.5×), because records repeat `name` and carry many nulls /
  `missing_columns`. At ~200k records, normalized + gzipped is ≈6–8 MB.
- **Incremental machinery already exists:**
  - `IncrementalWriter` (`file_utils.py`) is **merge-based + resumable**:
    `is_processed(id)` skips already-done bodies. → **Adding the 726 new bodies
    and re-running already skips the 157 done ones, with no new flag.**
  - `--public-body <id>` (single ID) scopes a full run to one body with a
    **no-effect guarantee** for all others, via `filter_by_public_body`,
    `IncrementalWriter(target_public_body=...)` eviction, `merge_replacing_body`,
    and the `dirty_ids.json` downstream cascade. See
    `2026-06-02-public-body-filter-design.md`.
  - `dirty_ids` cascade: a changed body is evicted + reprocessed downstream
    while others stay byte-for-byte intact.
- **Two real gaps for scale:**
  1. Dirty is triggered **only by `override.json` changes**, not by a council
     silently updating its source disclosure log. There is no automatic
     **source-content-change** detection.
  2. **`db_upload` does a full `DELETE FROM {table}` then re-INSERT** every run.
     Over HTTP to remote Bunny libSQL, full-reloading 200k+ rows each run is the
     real DB-scaling risk. The public-body spec already flagged that `db_upload`
     scoped runs need idempotent upsert.
- **Committed bloat is not only `public/`:** `normalize_disclosure_cells/
  changes.json` (30 MB) and `eval/input.json` fixtures (25 MB each) are tracked
  and will grow too.
- **No CI in this repo** (the *web* repo has `.forgejo/`; this one does not).
  Release publishing must be a locally-runnable script, optionally wired to
  Forgejo Actions later.
- **`docs/` is gitignored** except `docs/archive`; specs are force-added
  (`git add -f`) and tracked. This spec will be added the same way.

---

## Architecture

```
  source sites ──▶ pipeline (per-body, incremental) ──▶ libSQL/SQLite DB  ◀── SOURCE OF TRUTH
                                                              │
                          ┌───────────────────────────────────┼─────────────────────┐
                          ▼                                   ▼                     ▼
                 normalized JSON/CSV (gz)          publicinformation.db.gz      remote Bunny
                 (foi-disclosures, public-          (canonical snapshot)        libSQL (prod)
                  bodies, disclosure-files,                 │                        │
                  topics)                                   │                        │
                          └────────── Codeberg release `data-latest` ───────────────┘
                                                  │
                                                  ▼
                          website (CONSUMER): reads Bunny OR a downloaded release DB
                                     — never a filesystem path into this repo
```

### Cross-repo data contract

This is the entire interface between the two repos:

- **`public/schema.sql`** (owned here, committed) — the structural contract.
  Carries a `schema_version`.
- **Codeberg release** named `data-YYYY-MM-DD` plus a moving **`data-latest`**,
  with assets:
  - `publicinformation.db.gz` — canonical SQLite snapshot (the source of truth).
  - `foi-disclosures.json.gz` — normalized FOI records.
  - `public-bodies.json` — id → name/url/category/status (small, uncompressed).
  - `disclosure-files.json.gz`, `topics.json.gz`.
  - `manifest.json` — `{ generated_at, schema_version, counts:{bodies,
    disclosures,files,topics}, sha256:{<asset>:<hash>} }`.
- **The website depends on exactly one thing:** a `DATABASE_URL`
  (Bunny prod, populated by this repo) **or** a downloaded `publicinformation.db`
  from the latest release. The current dev coupling
  `file:../publicinformation-data/local.db` is **removed**.

Because the canonical DB and all open data are release assets attached to the
Codeberg repo, principle (3) holds: the website can vanish and every byte
remains downloadable from Codeberg.

---

## Subsystem A — Artifacts & git de-bloat *(Plan A, ship first)*

### A1. Normalize the published records

Drop redundancy from *published* artifacts (it stays in the DB / internal step
outputs):

- Remove the denormalized `name` from each FOI record; consumers join on
  `public_body_id` against `public-bodies.json`.
- Remove `missing_columns` from the published record (internal QA field).
- Result: smaller, cleaner open data; combined with gzip, ~6–8 MB at 200k rows.

### A2. New publishing step/script `publish_dist`

A new pipeline step (or `scripts/publish_dist.py`) that runs after `db_upload`:

1. Reads the DB (source of truth) — *not* the committed JSON.
2. Emits normalized artifacts to a **gitignored `dist/`** directory, gzipped,
   plus `manifest.json` with counts + SHA-256 checksums.
3. Snapshots + gzips the SQLite DB to `dist/publicinformation.db.gz`.
4. Uploads all `dist/` assets to a Codeberg release via the Forgejo/Codeberg
   API (token from env, e.g. `CODEBERG_TOKEN`), creating/moving `data-latest`
   and a dated release. Locally runnable; CI-wireable later.

### A3. Stop committing generated data; de-bloat git

- `git rm --cached public/foi-disclosures.json public/topics.json`
  (and `pipeline-data.json` / `disclosure-files.json` — confirm none are still
  read by anything before removing; the website does not read them).
- Gitignore `dist/`, `public/*.json` generated outputs. Keep
  **`public/schema.sql`** committed (the contract).
- Gitignore `normalize_disclosure_cells/changes.json` (30 MB) and reduce the
  25 MB `eval/input.json` fixtures to small representative samples, with a
  regeneration script for the full set.
- History rewriting (e.g. `git filter-repo`) to purge past blobs is **optional**
  and called out as a separate, risky decision — default is "stop the bleeding
  going forward," not rewrite history.

### A4. Consumer convenience

- `scripts/fetch-data.sh` — pulls the latest release assets (DB + JSON) for
  offline / third-party users. README documents: "clone is lean; one command
  fetches all data."
- README "Get the Data" table updated to point at release assets, not in-tree
  files.

---

## Subsystem B — Incremental per-body processing at scale *(Plan B)*

**Reuse, don't reinvent.** `--public-body` stays single-ID; `IncrementalWriter`
already skips done bodies; the `dirty_ids` cascade already reprocesses changed
bodies while preserving the rest. Subsystem B fills the two real gaps only.

### B1. Adding the 726 new bodies needs no new flag

Document and verify the existing path: add the new bodies to the source list,
run the pipeline normally; `IncrementalWriter.is_processed()` skips the 157 done
bodies and processes only the new ones. (A full `--force` run remains available
but is now the expensive exception, not the norm.)

### B2. Automatic source-content-change detection (the real gap)

Today a body is only marked dirty by an `override.json` change. At 883 bodies a
council will silently update its disclosure log and the change will be missed.

- Maintain a per-body **content manifest** (e.g.
  `find_disclosure_files`/`transform_disclosure_files` records a content hash of
  each fetched source page/file alongside `public_body_id`).
- On a run, if a body's fetched source hash differs from the manifest, mark that
  body **dirty** — feeding the *existing* `dirty_ids.json` cascade, which already
  evicts + reprocesses just that body downstream.
- This is additive: it produces `dirty_ids`, the same signal the cascade already
  consumes. No new orchestration flag.

### B3. Incremental `db_upload` (critical for 200k rows over HTTP)

Replace the full `DELETE FROM {table}` + reload with a delta load:

- Upsert `public_bodies` rows.
- For child tables (`foi_disclosures`, `disclosure_files`, topic links), replace
  **only the rows of bodies that changed this run** (driven by the same dirty
  set), inside a batch/transaction — never wipe the whole table.
- A `--full` flag preserves today's wipe-and-reload for cold rebuilds / schema
  changes.
- This aligns with the public-body spec's note that scoped `db_upload` must be an
  idempotent upsert.

### B4. DB indexes for both write and read paths

Add indexes the build and pipeline rely on:
`foi_disclosures(public_body_id, decision_date)`,
`disclosure_files(public_body_id)`, plus topic-link `public_body_id`/`slug`
indexes. (Shared with Subsystem C's build-query needs.)

---

## Subsystem C — Website build scaling & decoupling *(Plan C, separate repo)*

### C1. Decouple from this repo's filesystem

- The website must build against a `DATABASE_URL` (Bunny) or a downloaded
  release DB (`publicinformation.db` from `data-latest`), never
  `file:../publicinformation-data/local.db`. Provide a build-time fetch step in
  the web repo that pulls the release DB.

### C2. Build-time scaling

- Rely on the indexes from B4.
- The web `downloads/` endpoints should serve the **release artifacts** this repo
  produces, not regenerate canonical data, so the website remains a pure
  consumer.

### C3. FOI-pagination rendering — **OPEN, deferred to Plan C**

At 200k records the site would prerender ~4,000 deep `body/[id]/foi/[page]`
pages, each a build-time DB query (~6,000 pages total). Options (prerender
first-N + client fetch / on-demand SSR via the existing `edge-function/` /
prerender-all) are **not decided here**; recorded as the first open question for
Plan C.

---

## Sequencing & decomposition

| Plan | Subsystem | Repo | Independence |
|------|-----------|------|--------------|
| **A** | Artifacts & git de-bloat + release publishing | data | Independently shippable; relieves git pain first. Only needs the existing DB. |
| **B** | Content-hash dirty detection + incremental `db_upload` + indexes | data | Builds on A's DB-as-truth; reuses `--public-body`/`dirty_ids`. |
| **C** | Website decouple + build scaling + FOI render decision | web | Depends on A's release contract existing. |

Each plan becomes its own `writing-plans` implementation plan after this spec is
approved.

---

## Testing strategy (high level; per-plan plans go deeper)

- **A:** unit-test normalization (record shape, join integrity against
  `public-bodies.json`), `manifest.json` checksums; integration-test
  `publish_dist` against a temp release (mock Codeberg API); verify `git clone`
  size drop and that `fetch-data.sh` reconstitutes a usable DB + JSON.
- **B:** unit-test content-hash dirty detection (changed hash ⇒ body in
  `dirty_ids`; unchanged ⇒ absent); integration-test the no-effect guarantee
  still holds; test incremental `db_upload` upserts only the dirty body's rows
  and leaves others intact; test `--full` cold rebuild equals today's output.
- **C:** (in web repo) build against a downloaded release DB with no path into
  this repo; build-time/perf check at scale.

---

## Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Release publishing has no CI here | Local-runnable `publish_dist`; wire Forgejo Actions later. |
| `git rm --cached` doesn't shrink existing history | Stop-the-bleeding default; optional `git filter-repo` flagged as a separate decision. |
| Incremental `db_upload` could drift from a full rebuild | Keep `--full` path; periodically reconcile; checksums in `manifest.json`. |
| Dropping `name`/`missing_columns` breaks a consumer | `name` is derivable via `public-bodies.json`; document the join; bump `schema_version`. |
| Cross-body dedup (`extract_disclosures_deduplicate`) interacts with per-body dirty | Already flagged in the public-body spec; verify dedup stays correct under incremental runs. |
| Website still reaches into this repo's filesystem | C1 makes the release DB / `DATABASE_URL` the only contract; add a guard/test. |

---

## Open questions

1. **(Plan C) FOI-pagination rendering** — prerender first-N + client fetch vs
   on-demand SSR vs prerender-all. Deferred by the user.
2. **Release versioning detail** — dated `data-YYYY-MM-DD` + moving `data-latest`
   is proposed; confirm retention (how many dated releases to keep).
3. **Keep any in-tree JSON fallback?** — default is no committed bulk JSON
   (release assets only); confirm no consumer needs an in-tree copy.
4. **History rewrite** — purge past large blobs with `git filter-repo`, or only
   stop committing going forward? Default: stop going forward.

---

## Design decisions

| Question | Resolution |
|----------|------------|
| Source of truth? | The libSQL/SQLite DB, owned and published by this repo. |
| Repo ↔ website dependency direction? | Website depends on this repo's release/DB only; this repo depends on nothing in the web repo. |
| Open-data shape? | Single normalized + gzipped bulk artifact (+ DB), not per-body shards. |
| Distribution? | Codeberg release assets (`data-latest` + dated); lean `git clone` + `fetch-data.sh`. |
| New multi-body flag? | No. Reuse single-ID `--public-body`; new bodies auto-skip via `IncrementalWriter`. |
| How are changed sources detected? | New per-body content-hash manifest feeding the existing `dirty_ids` cascade. |
| `db_upload` at scale? | Incremental upsert of dirty bodies' rows; `--full` for cold rebuild. |
| Git bloat beyond `public/`? | Also evict `changes.json` (30 MB) and shrink eval fixtures (25 MB). |
| Website FOI rendering? | Deferred to Plan C. |
| History rewrite? | Out of scope by default; flagged as optional. |
