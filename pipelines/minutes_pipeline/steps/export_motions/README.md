# export_motions

Final fan-in that exports the canonical motion records grouped by authority, writing one clean per-authority file plus an index.

## What it does

1. Groups the flat canonical motion list (from `canonicalize_motions`) by `public_body_slug`.
2. Writes the step's standard `output.json` (`metadata` + flat `results` of all motions).
3. Writes **`public/motions/<slug>.json`** for each authority — `{public_body_slug, public_body_name, public_body_id, motions: [...]}`.
4. Writes **`public/motions/index.json`** — `{authorities: [<slug>, …]}`.

The public files are the MVP motion dataset; review `public/motions/` before running `scripts/publish_pages.sh`.

## Input

- `canonicalize_motions/output.json` (generated upstream)

## Output

- `output.json` — step output with `metadata.total_motions` and `metadata.authorities`.
- `public/motions/<slug>.json` — per-authority motion lists.
- `public/motions/index.json` — available-authority index.

## Notable files

- No `errors.json` is produced — this step is a deterministic fan-out over already-canonicalised records.
