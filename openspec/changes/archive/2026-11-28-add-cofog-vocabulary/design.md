# Design

## Context

COFOG 1999 is already used by `spc-topic-classification` and published as a flat CSV. The committed source of truth is `pipelines/spc_pipeline/reference/cofog_1999.json`: a flat list of 188 codes with `code`, `level`, `description`, `marker` (`CS`/`IS`) and `parent`, plus the UNSD URL, retrieval date and sha256. The CSV is written by `pipelines/spc_pipeline/scripts/build_vocabularies.py`, which also writes the SPC attendance, decision and subdomain vocabularies.

See `proposal.md` for the motivation. The constraints that shape this design are the existing vocabulary conventions in `public/vocabularies/`, the unversioned publication model for vocabularies (no `latest/` or `vX.Y.Z/` copies), the `rdflib` dependency already used by the SPC dataset test, and GitHub Pages serving `public/` as static files.

## Goals / Non-Goals

**Goals:**

- Make COFOG 1999 usable without scraping a CSV: a hierarchy in JSON, a SKOS graph in Turtle, and a resolvable URI space.
- Keep the existing CSV byte-compatible in shape and keep the SPC schema/test contract intact.
- Make the artefacts reproducible from the pinned reference with a single command and a drift check.
- Keep the change reviewable: no pipeline behaviour, no SPC record, and no classification output changes.

**Non-Goals:**

- Reproducing the UNSD explanatory notes (definitions). Labels and hierarchy only.
- Linking SPC records, or any other dataset, to term URIs.
- Moving the pinned reference out of the SPC pipeline.
- Publishing a future COFOG revision, or a versioned copy of this vocabulary.

## Decisions

### The pinned SPC reference remains the source

The new generator reads `pipelines/spc_pipeline/reference/cofog_1999.json`. That file already records the UNSD URL, retrieval date and sha256, and is refreshed by `pipelines/spc_pipeline/scripts/build_cofog.py` from the official structure file.

Alternative considered: move the reference to a neutral `data/` directory and have both the SPC pipeline and the vocabulary generator read it. That is the cleaner long-term layout, but it changes pipeline imports, tests and README for no functional gain in this change. Move it when a second pipeline needs COFOG, not before.

### One root generator, not an extension of the SPC builder

`scripts/build_cofog_vocabulary.py` owns the four distributions. The COFOG branch is removed from `pipelines/spc_pipeline/scripts/build_vocabularies.py`, which keeps writing the SPC-specific vocabularies.

Alternative considered: extend the SPC builder to write JSON and Turtle. It already reads the reference and writes the CSV, so it is the shortest path. But it makes a site-wide vocabulary a by-product of one pipeline, and future consumers would depend on `spc_pipeline` to regenerate it. A root script matches the repository's `scripts/transform_*.py` pattern and keeps the SPC pipeline focused on its dataset.

### JSON carries both a tree and a flat index

The JSON distribution has three top-level members: `scheme` (metadata), `divisions` (nested tree) and `concepts` (flat list in code order). The tree is what a UI or a documentation page wants; the flat list is what a classifier wants, without recursive traversal.

The duplication is deliberate and generated from one traversal. A test asserts that the tree and index contain the same codes and identical fields, so drift is impossible without a test failure.

Alternative considered: nested only, with a separate `index.json`. Two files make lookup cheap but add a fetch and a second drift surface. A single file with both views is simpler for a 188-term vocabulary.

### Codes are strings, service type is explicit

Every code and notation is a string (`"01"`, not `1`), because COFOG codes are fixed-width and leading zeros are meaningful. The source's `marker` is mapped to `service_type: "collective"` or `"individual"` for classes, and `null` for divisions and groups. The raw marker is not exposed; the long form is clearer and matches the UN's own expansion.

In Turtle, the service type is a `skos:scopeNote` (`"Collective service"@en` / `"Individual service"@en`). SKOS has no dedicated property for this, and inventing a `cofog:` term for one boolean would add a namespace for little value.

### The CSV keeps its four-column shape

`uri,notation,name,description` is the established vocabulary shape across the site, and the SPC test reads `notation` only. The CSV therefore does not gain `parent`, `level` or `service_type` columns; consumers that need the hierarchy use the JSON or Turtle. This keeps the CSV a drop-in replacement for the current file and avoids touching the CSVW metadata beyond regenerating it.

The `description` values keep the existing convention: `COFOG 1999 division`, `COFOG 1999 group`, `COFOG 1999 class (CS)` / `(IS)`.

### The URI namespace stays `/ns/cofog#`

The term URIs remain `https://data.publicinformation.ie/ns/cofog#<code>`, consistent with `ns/spc`, `ns/motions` and `ns/transport-subdomain`. The scheme declares `owl:versionInfo "1999"` and documents that this namespace means COFOG 1999.

Alternative considered: version the namespace as `/ns/cofog/1999#`. That is semantically cleaner for the 2028 revision and would be cheap now because only the CSV currently carries the URIs. But it breaks the established namespace pattern for one vocabulary, and the existing URI is already published. The revision will get a new namespace (`ns/cofog-2028#` or similar); the old namespace stays as the 1999 scheme.

### A static resolver page, not content negotiation

GitHub Pages cannot serve JSON-LD or Turtle based on `Accept`. `public/ns/cofog/index.html` is a small static page that names the vocabulary, lists the ten divisions, and links to the JSON, CSV, CSVW metadata and Turtle files. `<link rel="alternate">` elements point at the machine formats for clients that look for them.

`/ns/cofog` resolves because Pages redirects a directory request to `/ns/cofog/`, which serves `index.html`; the existing `/documents/` path demonstrates the pattern. A file at `public/ns/cofog` (no extension) would be served as an unknown type, so the directory-index approach is preferred.

Alternative considered: put the vocabulary document directly at `public/ns/cofog` with a JSON body. Pages would not set a useful content type, and browsers would download it rather than show a page.

### Fixed dates, not generation timestamps

The JSON and Turtle carry the classification version (`1999`) and the source retrieval date, not the generation time. The catalogue record's `dct:modified` is a content-freshness field, updated only when the generated vocabulary changes, following the repository's `stamp_if_changed` policy. This keeps `--check` deterministic: regenerating an unchanged vocabulary produces byte-identical files.

### Fail closed before writing anything

The generator builds all four outputs in memory, validates the hierarchy (unique codes, known parents, expected counts, every concept reachable from a division), and only then writes. A missing parent, duplicate code or count mismatch raises before any file is touched. `--check` performs the same build and compares bytes without writing.

## Risks / Trade-offs

- **SPC owns the source** → A future change to the SPC reference could break the generator; the tests read the same file, so the breakage is visible. Document the dependency in the vocabulary README and revisit when a second consumer appears.
- **No definitions** → Labels alone can be ambiguous for classification (`04.5.1` versus `04.5.3`). The README says the authoritative definitions are the UNSD explanatory notes; adding them is a separate, reviewed change.
- **Unversioned namespace** → A future revision must not reuse `/ns/cofog#`. The scheme metadata and README state this explicitly; the revision task must mint a new namespace.
- **CSV shape lock** → Spreadsheet users cannot see parent/level. They can join through `notation` to the JSON or use the Turtle; the alternative (extra columns) would diverge from every other vocabulary.
- **Static resolver drift** → The HTML page is hand-authored, so its links could go stale. A test checks that every linked file exists and that the page names COFOG 1999.
- **GitHub Pages redirect** → `/ns/cofog` arrives as a 301 to `/ns/cofog/`; clients must follow redirects. The README shows the trailing-slash form, and the fragment URIs are unaffected because fragments are resolved client-side.

## Migration Plan

1. Add the generator, run it, and review the `public/vocabularies/` diff. The CSV should differ only if the existing file is stale; otherwise it is byte-identical.
2. Add the resolver page, README and catalogue record; link them from the public data README and `DATA_SOURCES.md`.
3. Remove the COFOG branch from the SPC vocabulary builder and run the SPC tests. No SPC payload should change.
4. Add the changelog entry and run the root test suite.
5. Merge only after reviewing the generated `public/` diff; merging to `main` publishes the vocabulary.

Rollback is a revert of the commit: the old CSV is regenerated by the SPC builder, and the new files disappear. No data migration or versioned release is involved.

## Open Questions

None. The scope, formats, URI shape and source location are settled for this change.
