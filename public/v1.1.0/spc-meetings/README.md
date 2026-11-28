# SPC meetings

**Dataset URI:** `https://data.publicinformation.ie/dataset/spc-meetings`

Coverage: Meath County Council's Transportation and Urban Regeneration Strategic Policy Committee: six meetings, February 2025 to May 2026. No other council or committee is published yet.
The dataset holds who attended, their attendance, agenda items with COFOG 1999
topics, official decisions as verbatim quotes, and the minutes rendered verbatim
as Markdown.

## Versioning

This directory mirrors the newest immutable release, `../../v1.1.0/spc-meetings/`
(earlier releases stay in place). `owl:versionInfo` is bumped by hand for a breaking
or additive schema change; `dct:modified` in the catalogue record changes only when
the published content changes.

## Files

- `meetings` – one row per meeting
- `people` – one row per person recorded in attendance
- `attendance` – one row per person per meeting
- `items` – agenda items with their topics
- `decisions` – official decisions as contiguous quotes from the minutes
- `minutes/<council>/<committee>/<date>.md` – the verbatim minutes; [`minutes/index.md`](minutes/index.md) lists them

Each table is published as JSON-LD and CSV with CSVW metadata (`<table>.csv-metadata.json`). Related: [JSON Schema](../../schemas/spc-meetings.schema.json), [DCAT-AP catalogue record](../../catalog/dataset-spc-meetings.ttl), and the vocabularies [`cofog-1999`](../../vocabularies/cofog-1999.md), [`transport-subdomain`](../../vocabularies/transport-subdomain.csv), [`spc-attendance-status`](../../vocabularies/spc-attendance-status.csv), [`spc-attendance-mode`](../../vocabularies/spc-attendance-mode.csv), [`spc-attendee-category`](../../vocabularies/spc-attendee-category.csv) and [`spc-decision-type`](../../vocabularies/spc-decision-type.csv) under [`../../vocabularies/`](../../vocabularies/).

## Tables and fields

Tables join on `meeting_id`, `item_key` (with `meeting_id`) and `person_id`.

A `decision_id` (`<meeting_id>/d<NN>`) is allocated once and never changes or is reused, even if the extraction is re-run. A number can be missing from a meeting where a decision was retired; it is not reassigned.

### meetings

| Field | Type | Description |
|---|---|---|
| `id` | uri | Persistent URI for this record |
| `meeting_id` | string | Canonical meeting identifier, <council>/<committee>/<YYYY-MM-DD> |
| `committee_id` | string | Committee identifier, <council>/<committee> |
| `committee_name` | string | Committee name as published |
| `public_body` | uri | URI of the body in the Public Bodies dataset |
| `public_body_id` | integer | Internal public_body_id, retained for joins |
| `meeting_date` | date | Date of the meeting |
| `venue` | string | Venue as printed in the minutes |
| `start_time` | string | Start time as printed |
| `end_time` | string | End time as printed |
| `source_url` | uri | URL of the source minutes PDF |
| `source_sha256` | string | SHA-256 of the source PDF bytes |
| `minutes_path` | string | Verbatim Markdown minutes, relative to the dataset root |
| `attendance_published` | boolean | false when the meeting's attendance was withheld |

### people

| Field | Type | Description |
|---|---|---|
| `id` | uri | Persistent URI for this record |
| `person_id` | string | Stable person identifier |
| `canonical_name` | string | Canonical name from the committed register |
| `kind` | string | councillor, sectoral_representative, official or guest |
| `councillor_id` | string | Councillor ID used by the motions dataset; empty for other kinds |
| `public_body` | uri | URI of the body in the Public Bodies dataset |
| `public_body_id` | integer | Internal public_body_id, retained for joins |

### attendance

| Field | Type | Description |
|---|---|---|
| `id` | uri | Persistent URI for this record |
| `meeting_id` | string | Canonical meeting identifier, <council>/<committee>/<YYYY-MM-DD> |
| `meeting_date` | date | Date of the meeting |
| `person_id` | string | Stable person identifier |
| `category` | string | councillors, sectoral_representatives, apologies, officials or presenters |
| `role` | string | Role as printed, empty when none is printed |
| `status` | string | present or apologies |
| `mode` | string | remote, in_person or not_stated |
| `presented` | boolean | true when the person's name also appears in the presenters block |

### items

| Field | Type | Description |
|---|---|---|
| `id` | uri | Persistent URI for this record |
| `item_id` | string | Dataset-relative item identifier, <meeting_id>/<item_key> |
| `meeting_id` | string | Canonical meeting identifier, <council>/<committee>/<YYYY-MM-DD> |
| `item_number` | string | Number as printed; not unique (two items may share one) |
| `item_key` | string | Stable item key, e.g. item-6-0 and item-6-0-2 |
| `title` | string | Item title as printed |
| `text` | string | Item text, page furniture removed |
| `is_minutes_approval` | boolean | true for approval of the previous meeting's minutes |
| `topics_published` | boolean | false when the item's topics were withheld |
| `cofog` | string | Pipe-separated COFOG 1999 codes, primary first; empty when withheld |
| `subdomains` | string | Pipe-separated transport subdomains; empty for non-transport items |
| `procedural` | boolean | true for a purely procedural item; empty when withheld |

### decisions

| Field | Type | Description |
|---|---|---|
| `id` | uri | Persistent URI for this record |
| `decision_id` | string | Stable decision identifier, <meeting_id>/d<NN> |
| `meeting_id` | string | Canonical meeting identifier, <council>/<committee>/<YYYY-MM-DD> |
| `meeting_date` | date | Date of the meeting |
| `item_number` | string | Number as printed; not unique (two items may share one) |
| `item_key` | string | Stable item key, e.g. item-6-0 and item-6-0-2 |
| `decision_text` | string | Verbatim contiguous quote from the item text |
| `decision_type` | string | agreed, adopted, recommended_to_council, referred, deferred or appointment |
| `proposer` | string | Person ID of the proposer; empty when the minutes do not name one |
| `seconder` | string | Person ID of the seconder; empty when the minutes do not name one |
| `proposer_unresolved` | boolean | true when a named proposer could not be resolved, grounded or found present |
| `seconder_unresolved` | boolean | true when a named seconder could not be resolved, grounded or found present |

## Reading withheld and empty values

- The pipeline fails closed: a value it cannot confirm is withheld, not guessed.
- `attendance_published` is false on a meeting whose attendance is withheld because
  a printed name could not be resolved to the committed register. That meeting has
  no attendance rows.
- `topics_published` is false when an item's topics were withheld; `cofog`,
  `subdomains` and `procedural` are then null.
- In JSON-LD, null means withheld and `[]` means genuinely none. In CSV both are an
  empty cell, so read `topics_published` to tell them apart.
- `cofog` and `subdomains` are pipe-joined in CSV (`a|b`); CSVW declares
  `"separator": "|"`. They are arrays in JSON-LD.
- `proposer` and `seconder` are empty when the minutes name no one, or the name
  could not be confirmed; the matching `*_unresolved` flag is true in the second
  case.

## Counts

- Meetings: 6
- People: 28
- Attendance rows: 98
- Items: 46
- Decisions: 17

## People named in this dataset

The dataset names councillors, council officials, sectoral representatives (which
can include private citizens, for example Public Participation Network
representatives), presenters and guests, with their attendance, apologies and
the role printed in the minutes. Every name and role comes from minutes the
council itself published. Names are matched to a committed register; nothing is
added about a person beyond what the minutes print. To ask for a correction or
removal, write to dave@publicinformation.ie.

## Source, attribution and licence

Source: Meath County Council, Transportation and Urban Regeneration Strategic
Policy Committee minutes, retrieved from www.meath.ie; each meeting records its
`source_url` and the PDF's `source_sha256`. The minutes are the council's
material, reproduced here without alteration to their wording.

COFOG 1999 is the UN Statistics Division classification; transport subdomains
follow the transport-governance vocabulary. The topics, decisions and attendance
tables are derived by PublicInformation.ie (an LLM proposes topics and decisions;
each decision is checked to be a verbatim quote).

The derived dataset is published under CC BY 4.0. Meath County Council's own
re-use terms for the underlying minutes have not been independently confirmed
against www.meath.ie; if you re-use the verbatim minutes, check them.
Attribute as: *Source: Meath County Council; processed by PublicInformation.ie.*

## Reproducing

See `pipelines/spc_pipeline/README.md` in the repository: requirements, the LLM
credentials and cost, and the step order.
