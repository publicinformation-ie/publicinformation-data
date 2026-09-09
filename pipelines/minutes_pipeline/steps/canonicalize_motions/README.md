# canonicalize_motions

Fan-in that turns `extract_motions` output into a flat list of canonical motion records — deterministic, stateless, no network.

## What it does

For each extracted record (each with a `motions` list or `null`):

1. **Join** `public_body_id` to the authority's `slug`/`name` from `find_local_authorities` (a sibling step). An id with no matching authority is an error (`UnknownAuthority`).
2. **Assign a composite id** `<slug>/<meeting_date>/m<NNN>`, with `NNN` a zero-padded 3-digit sequence numbered by order of appearance across all documents of one (authority/district, meeting_date) meeting.
3. **Deduplicate** identical motion text within the same meeting.
4. **Map the status** to the closed set via `map_status` (`CANONICAL_STATUSES`): `carried`, `carried_as_amended`, `not_carried`, `withdrawn`, `deferred`, `not_recorded`. Aliases (`defeated`/`lost` → `not_carried`, `amended` → `carried_as_amended`, …) are normalised.
5. **Classify the meeting type**: `municipal_district` when a district is set, else `council`.

## Fail-closed policy

- An **unmappable `status_label`** becomes `not_recorded` **plus** an `errors.json` entry (`UnknownStatusLabel`) — never a silent default.
- A **missing/unresolved `meeting_date`** excludes the motion (it cannot get a stable id) **plus** an error (`MissingMeetingDate`).
- A document whose LLM extraction **failed** (`motions: null`) produces no canonical motions and an error (`NoMotionsExtracted`).

## Input

- `extract_motions/output.json` (generated upstream)
- `find_local_authorities/output.json` (sibling step, for `slug`/`name`)

## Output

`output.json` — `{ metadata, results: [...] }`, a flat list of canonical motion records with `motion_id`, `public_body_id`, `public_body_slug`, `public_body_name`, `municipal_district`, `meeting_date`, `meeting_type`, `source_file_url`, `motion_text`, `proposer`, `seconder`, `status`.

## Notable files

- `errors.json` — per-motion/per-document canonicalization errors.
- `--public-body` scoping uses `merge_replacing_body` (Shape-b merge-back), matching `extract_disclosures_canonicalize_rows`.
