# export_status

Merges the outputs of all pipeline steps into a unified per-body status report and writes the public-facing JSON files consumed by the website.

## What it does

Reads `find_public_bodies/output.json` as the base record set, then iterates through each pipeline step in order (as defined in `pipeline.json`) and calls a per-step merger function that updates each body's `status` object. The status object tracks:

- `website_url` — whether the body's website is reachable.
- `foi_page` — whether a FOI page was found and is reachable.
- `foi_email` — whether a FOI contact email was extracted.
- `disclosures_page` — whether a disclosure log page was found.
- `disclosure_files` — total / valid / failed file counts.
- `foi_requests` — count of successfully canonicalised FOI request records.

In addition to the step-level `output.json`, this step writes these public files to `public/`:

| File | Contents |
|---|---|
| `public/pipeline-data.json` | Full merged status for every public body |
| `public/disclosure-files.json` | Flat list of all discovered disclosure log file URLs |
| `public/latest/foi-disclosures/bodies/<public_body_id>.ndjson` | All canonicalised FOI request records, one canonical NDJSON file per body (committed, ordinary git) |

After writing the per-body files the step rebuilds the **uncommitted** combined forms
(`public/foi-disclosures.json`, `public/latest/foi-disclosures/foi-disclosures.{csv,jsonld,xlsx}`
and `bodies/manifest.json`) via `scripts/build_foi_combined.py`, so local files always match the
per-body files. It stamps `dct:modified` in `public/catalog/dataset-foi-disclosures.ttl` only when
a per-body file was added, changed or removed.

On a full (unscoped) run it also regenerates the public-bodies catalog via
`publish_public_artifacts()` → `src/lib/publish_public_bodies.py`, writing
`public/v2.0.0/public-bodies/` and `public/latest/public-bodies/`. Scoped
`--public-body` runs skip this: their merge holds one body, and publishing it
would blank every other body's crawl columns.

## Orphan guard

Disclosure-step records naming a `public_body_id` that is not a canonical body
normally abort the run — that is the wrong-id mistake the guard exists for (an
override attached to an unrelated body). One exception: an id that names a real
body in `find_public_bodies` but is **no longer FOI-subject** — foi.gov.ie
dropped it from its directory — is stale rather than corrupt. Those records are
skipped by the mergers and reported under "Retired bodies still referenced by
disclosure steps" for review, because raising would wedge every subsequent run.
A hand-curated (`overridden`) record naming an out-of-scope body still raises.

## Input

All step `output.json` files (read directly from sibling step directories, not via the `--input` argument).

## Output

`output.json` — `{ metadata, public_bodies: [...] }`. Each body includes its full `status` object with results from every completed step.
