# Design

## Context

See proposal.md for the motivation. The current state that shapes the approach:

- `export_status` writes the combined `public/foi-disclosures.json` (`process.py:256–265`) from `extract_disclosures_deduplicate/output.json`. `scripts/transform_foi_disclosures.py` reads that file and writes `public/latest/foi-disclosures/foi-disclosures.{csv,jsonld}`. Nothing writes `foi-disclosures.xlsx`.
- `.gitattributes` sends `public/**/*.{json,jsonld,csv,xlsx}` and `transform_disclosure_files/output.json` to LFS.
- `deploy-pages.yml` uploads `public/` as-is to `data.publicinformation.ie`. The web repo seeds from `https://data.publicinformation.ie/latest/foi-disclosures/foi-disclosures.csv` and can also read a local path.
- Versioning today: other datasets are snapshotted in-repo under `public/vX.Y.Z/<dataset>/` (v1.0.0 to v3.2.0), and tags exist per dataset (`foi-disclosures-v1.0.0`, `public-bodies-v1.0.0`) as well as repo-wide (`v1.0.0`). FOI disclosures are in no `public/vX.Y.Z/` snapshot.
- `row_id` is `compute_row_id(file_url, original_row_index)` (`extract_disclosures_canonicalize/process.py:124`), so it is stable across rescans unless a file's rows move.
- Measured churn per rescan:
  - **LFS:** 50–59 MB for the combined JSON and ~38 MB for the step output.
  - **Ordinary git:** 0.3–0.6 MB for each.
  - **Bodies:** 6–35 of 115 are touched per run.
- Measured per-body sizes (57,685 rows, 115 bodies): the largest body is about 3.3 MB pretty-printed and 3.0 MB as compact NDJSON; the median is about 100 KB; 53 bodies are over 200 KB. The total is about 41 MB as NDJSON.
- `fetch_status_annexes` already works like a cache. Its `output.json` is gitignored and records `source_sha256`, but the `annexes/*.xlsx` files are committed and no expected checksum is declared anywhere.

## Goals / Non-Goals

**Goals:**
- Per-change storage proportional to the rows changed.
- Rescan PRs that show, as a readable text diff, which bodies and rows changed.
- The public URLs stay the same.
- One source of truth (the per-body files), from which every other form, including the manifest, is built.
- A dataset an agent can navigate in small pieces: an index first, then one body, then individual rows.

**Non-Goals:**
- Splitting other datasets (motions, actions, public bodies) or changing `public/vX.Y.Z/` snapshots.
- Rewriting history or reclaiming quota already spent.
- Changing the row schema or the content of the CSV/JSON-LD columns.
- Splitting the `transform_disclosure_files` step output. See decision 3.

## Decisions

**1. Per-body NDJSON files at `public/latest/foi-disclosures/bodies/<public_body_id>.ndjson`.**
- **Why per body:** this was decided with the user. Bodies are stable keys, and changes cluster by body.
- **Why under `latest/foi-disclosures/`:** one dataset lives in one folder, matching the `latest/<dataset>/` layout of the other datasets, and it avoids having a `foi-disclosures.json` file next to a `foi-disclosures/` folder.
- **Format:** one row per line, compact JSON (`separators=(",", ":")`), keys in the current row field order, `ensure_ascii=False` so Irish-language text stays readable and smaller, with U+2028 and U+2029 escaped so no reader splits a row. Rows are sorted by `row_id`; UTF-8, LF line endings and a trailing newline.
- **Why NDJSON:** a grep hit is one whole row, `wc -l` is the row count, and `head` gives a usable sample, all of which help agents and humans working from a shell. Git diffs at row level, which is how the data changes. NDJSON is only about 10% smaller than pretty-printed JSON, so the gain is in navigation, not size.
- **Alternatives considered:**
  - **Pretty-printed JSON array (`indent=2`):** field-level diffs, but a grep hit returns one field with none of its row, and agents pay for the indentation. These are new files with no existing consumers, so consistency with other `public/` JSON costs nothing to give up.
  - **Per source file (1,340 files):** smaller files, but in ordinary git per-body files already store only what changed, so the extra files buy little. The manifest plus `grep` covers finding rows inside a large body.

**2. Built forms are built by the export step and in CI, and never committed.**
- A single build entry point, `scripts/build_foi_combined.py` (a thin CLI over a function in the shared module), reads the per-body files and writes:
  - `public/foi-disclosures.json`
  - `public/latest/foi-disclosures/foi-disclosures.{csv,jsonld,xlsx}`
  - `public/latest/foi-disclosures/bodies/manifest.json`
- `export_status` calls the build function right after `write_parts`, so after a pipeline run the local built files always match the per-body files. A stale, gitignored combined file would otherwise mislead anyone, human or agent, who greps it.
- `scripts/transform_foi_disclosures.py` becomes its CSV/JSON-LD stage, with the input switched from the combined JSON to the per-body loader.
- The XLSX is written with openpyxl in write-only mode, using `CSV_FIELDNAMES` as the header so it can't drift from the CSV.
- The combined JSON keeps today's shape (a plain array of rows) and is ordered by `(public_body_id, row_id)`.
- These outputs are added to `.gitignore`.
- **`dct:modified` stamping moves to the export step.** Today `transform_foi_disclosures.py:168` calls `stamp_if_changed`, which compares newly built bytes with the files on disk and, if they differ, rewrites `dct:modified` in the committed `public/catalog/dataset-foi-disclosures.ttl`. Once the combined files aren't committed, a fresh checkout or CI has nothing to compare against, so every build would stamp: CI would serve the deploy date as the content date, and a local build would dirty the `.ttl`. Instead, `export_status` stamps the `.ttl` only when `write_parts` changed, added or removed a per-body file. The build never touches the `.ttl`.
- `deploy-pages.yml` installs `scripts/requirements-build.txt` (openpyxl pinned to the same version as `pipelines/foi_pipeline/requirements.txt`, currently 3.1.5) and runs the build before `upload-pages-artifact`, so the URLs stay the same.
- Versioned releases are published to bunny.net, not to GitHub releases. See decision 7.
- **Refinement of the earlier choice:** the user picked "combined release asset, web switches to it". Building inside the Pages deploy keeps the existing URL, so `publicinformation-web` needs no change. Pages serves `latest`, and bunny holds only the versioned releases. This was confirmed with the user.
- **Alternative:** committing the combined files in ordinary git. Rejected: the CSV is 50+ MB, which is near GitHub's warning size, and the CRLF/NUL content makes git treat it as binary.

**3. `transform_disclosure_files/output.json` stays a single file in ordinary git.**
- The FOI runner's contract is one `output.json` per step, and `export_status` reads it by that path (`process.py:304–307`). Splitting it would break the step contract for a file that isn't a published output.
- At about 36 MB (pretty-printed, 1.1M lines) it is under the 45 MB guard, and it costs about 0.5 MB per change in ordinary git.
- `metadata.completed_at` is removed from the committed file. If a run timestamp is still wanted, it goes to the step's run log, which isn't committed.
- If the size guard trips, splitting this file becomes its own change.

**4. `.gitattributes` overrides, not removals.** Later lines win in `.gitattributes`. Add:
```
public/latest/foi-disclosures/bodies/** !filter !diff !merge text eol=lf
public/disclosure-files.json !filter !diff !merge text eol=lf
pipelines/foi_pipeline/steps/transform_disclosure_files/output.json !filter !diff !merge text eol=lf
```
and delete the existing `transform_disclosure_files/output.json` LFS line. The broad `public/**` LFS rules stay for other datasets. Existing pointers are converted with `git rm --cached` and a re-add in the migration commit.
- **`!` not `-`:** `-diff` and `-merge` *unset* the attributes, which makes git show "Binary files differ" and refuse to merge the file as text. `!` makes them *unspecified*, so git falls back to normal text diff and merge. (Checked in a scratch repo with `git check-attr -a`.)

**5. One shared module; no committed manifest.** Something like `src/lib/foi_dataset.py` owns `write_parts(rows, out_dir)`, `load_parts(out_dir)`, `verify_parts(out_dir)` and `build_manifest(out_dir)`. The export step, the build script, the tests and the size guard all use it, so the serialisation rules are written once.
- **Why the manifest isn't committed:** every rescan, override or fix would rewrite it, so any two branches touching FOI data would conflict on it, and it holds nothing that can't be computed from the files.
- **What verification checks instead:** each file parses line by line; every row's `public_body_id` matches its filename; rows are sorted by `row_id`, with no `row_id` repeated across files; and each file's bytes equal its canonical re-serialisation.
- **Manifest contents (built):** for each body, `public_body_id`, `name`, `path`, `url` (on `data.publicinformation.ie`), `row_count`, `date_received_min`, `date_received_max` and `sha256`, plus the dataset totals, `schema_version` (from `DATASET_VERSION`), `build` (set only in releases; see decision 7) and the source commit. Agents read it first to find a body by name before opening a file.

**6. Annexes use the declared checksum.**
- `status_annex` in `documents.yml` gains `sha256`, filled from the current committed files.
- `_declared()` includes it, so the existing eviction logic refetches when a declaration changes.
- After download, a mismatch raises a new `AnnexChecksumMismatch` error. This is the existing `_AnnexError` path, so the run records an error instead of crashing.
- `annexes/` is added to `.gitignore` and the files are removed from the index. The cache stays where it is, so `extract_annex_status` (`:514`) needs no path change.

**7. A release publisher that doesn't depend on GitHub.**
- **Trigger:** `foi-disclosures-v*` tags, extending the existing `foi-disclosures-v1.0.0` tag. A repo-wide `vX.Y.Z` tag or another dataset's tag never publishes FOI data.
- **Schema version plus build version (decided with the user).** The version number stays the schema contract: `DATASET_VERSION` and `owl:versionInfo`, which are stable through many builds and bumped by hand only for schema changes. Each release adds a build identifier:
  - **Tag:** `foi-disclosures-v<schema>+<build>`, using SemVer build metadata, e.g. `foi-disclosures-v1.0.0+20261113`. The build is the UTC release date `YYYYMMDD`, with `.<n>` for a second release on the same day (`+20261113.2`).
  - **Folder:** `foi-disclosures/v<schema>/<build>/`, e.g. `foi-disclosures/v1.0.0/20261113/`, so all builds of one schema version sit together. Folder names avoid `+`, which some tools mangle in URLs.
  - **Guard:** the publisher rejects a tag with no build part, a malformed build, or a schema part that doesn't equal `DATASET_VERSION` at the tagged commit.
  - **Recorded in the release:** the release's `manifest.json` carries `schema_version`, `build` and the source commit. The Pages-built manifest carries `schema_version` and the source commit, with `build` set to null.
  - **Existing tag:** `foi-disclosures-v1.0.0` predates this scheme. It is left as historical and never published to bunny.
- **What it does:** `scripts/publish_artifacts.py <tag> --target {bunny,local:<dir>}` runs the build and writes `SHA256SUMS`. It then checks that the version folder doesn't already exist and uploads the six files: the combined JSON, CSV, JSON-LD and XLSX, `manifest.json` and `SHA256SUMS`.
- **No `latest/` on bunny:** Pages already serves `latest`. A second copy that only moves on tags would disagree with Pages most of the time, and it would need a CDN purge. Versioned folders never change, so they need no purge.
- **Hostname:** release URLs given in docs and the catalog use `https://releases.publicinformation.ie/`, a CNAME to the Pull Zone, never the `*.b-cdn.net` hostname. Moving CDN later then changes DNS, not every cited link.
- **Targets:** each target implements `exists(path)` and `put(path, bytes)`.
  - **Bunny:** `PUT https://storage.bunnycdn.com/<zone>/<path>` with an `AccessKey` header. The existence check is a `GET` on the folder listing.
  - **Local:** writes files under a directory. It serves for dry runs and tests.
- **Credentials:** `BUNNY_STORAGE_ZONE` and `BUNNY_STORAGE_KEY`, from environment variables.
- **CI:** `.github/workflows/release.yml` triggers on `push: tags: ['foi-disclosures-v*']` and does only checkout, setup-python, the build requirements and the one command. Moving git hosts means rewriting only that wrapper.
- **Relation to `public/vX.Y.Z/`:** other datasets keep their in-repo snapshots for now. FOI releases live only on bunny, because committing a 50 MB snapshot per release would bring back the cost this change removes. The docs state both schemes.
- **Alternatives considered:**
  - **GitHub release assets:** they keep the GitHub dependency the user wants to avoid.
  - **An S3 SDK:** bunny Storage isn't S3-compatible, and its HTTP API needs only the standard library or `requests`.
  - **Publishing on every merge:** more uploads for little gain. Pages already serves `latest`, and the user chose tag pushes.
  - **`v*` tags:** they would publish FOI data on any repo-wide or other-dataset release, and they don't match the existing FOI tag.
- **Reuse:** the follow-up for the documents bundles can use the same publisher and targets.

## Risks / Trade-offs

- **A bunny key leaks.** → Use the Storage Zone password for this zone only, kept as a CI secret and never logged. No account-wide API key is needed now that there is no purge.
- **bunny is unavailable.** → The site's `latest` is still served by Pages. The release job can be re-run against the same tag, and if the earlier run left a partial folder it refuses to overwrite it. Recovery then means deleting the partial folder by hand, which is acceptable because it's rare.
- **External links to `public/foi-disclosures.json` or a raw GitHub URL break.** → Pages keeps the same site URLs. Raw-GitHub links to the combined files break; this is noted in the README and the release notes.
- **Local built files go stale.** → The export step rebuilds them on every run. Anyone who edits per-body files by hand runs `scripts/build_foi_combined.py`, which has no network dependency.
- **A Pages deploy fails if the build fails, leaving the site on its previous version.** → That's acceptable, and better than serving partial data. CI runs the build on every PR, so failures show up before merge.
- **The repo's ordinary git history grows by about 0.5–3 MB per rescan.** → That's about 100× less than LFS today. Revisit if clones slow down.
- **Large bodies are still large.** → The biggest body is about 3 MB, too much for an agent to read whole. The manifest and the one-row-per-line format let an agent find and slice rows instead.
- **A file's header detection changes.** → Its rows get new `original_row_index` values and so new `row_id`s, and the whole body file reorders in that diff. This is expected and limited to that body.
- **gov.ie replaces or removes an annex.** → A checksum mismatch or fetch error is recorded per document. Updating the declared `sha256` is a deliberate curation edit.
- **Rows without `public_body_id`.** → The export fails loudly. Every row has one today; the check makes that an enforced rule.

## Migration Plan

1. Land the shared module, export change, build script and tests behind the current layout. The build produces the same row set and field values as today's committed `public/foi-disclosures.json`; only the row order may differ (it becomes `(public_body_id, row_id)`).
2. In one commit:
   - add the `.gitattributes` overrides and `.gitignore` entries;
   - write the per-body files;
   - `git rm --cached` the combined JSON, CSV, JSON-LD and XLSX and the LFS-tracked step output, then re-add the step output and `public/disclosure-files.json` as ordinary files;
   - remove the annex files from the index and add their checksums to `documents.yml`.
3. Update `deploy-pages.yml` and add `release.yml` in the same PR. Before merging, check that a dry-run build on the PR matches the live site's CSV row count. Set up the bunny Storage Zone, Pull Zone, `releases.publicinformation.ie` CNAME and CI secrets. Before the first real tag, run `publish_artifacts.py --target local:<dir>`, then publish a throwaway test tag and delete it. The first real FOI release is `foi-disclosures-v1.0.0+<release date>`.
4. **Rollback:** revert the PR. The old LFS objects are still on the remote, so the reverted pointers resolve.

## Open Questions

- Whether `public/latest/foi-request-files/*` (under 1 MB) should get the same treatment. This is deferrable and doesn't affect this design.
