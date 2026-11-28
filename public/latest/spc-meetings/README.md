# SPC meetings

**Dataset URI:** `https://data.publicinformation.ie/dataset/spc-meetings`

Coverage (no other council or committee is published yet):

- Kildare County Council, Transport, Mobility and Open Spaces Strategic Policy Committee: 6 meetings, 2025-02-06 to 2026-05-21
- Meath County Council, Transportation & Urban Regeneration Strategic Policy Committee: 6 meetings, 2025-02-20 to 2026-05-21
- Westmeath County Council, Planning, Regeneration & Transportation Strategic Policy Committee: 5 meetings, 2025-02-13 to 2026-03-06

The dataset holds who attended, their attendance, agenda items with COFOG 1999
topics, official decisions as verbatim quotes, and the minutes rendered verbatim
as Markdown.

## Versioning

This directory mirrors the newest immutable release, `../../v1.2.0/spc-meetings/`
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

Each table is published as JSON-LD and CSV with CSVW metadata (`<table>.csv-metadata.json`). Related: [JSON Schema](../../schemas/spc-meetings.schema.json), [DCAT-AP catalogue record](../../catalog/dataset-spc-meetings.ttl), and the vocabularies [`cofog-1999`](../../vocabularies/cofog-1999.md), [`transport-subdomain`](../../vocabularies/transport-subdomain.csv), [`spc-attendance-status`](../../vocabularies/spc-attendance-status.csv), [`spc-attendance-mode`](../../vocabularies/spc-attendance-mode.csv), [`spc-attendee-category`](../../vocabularies/spc-attendee-category.csv), [`spc-decision-type`](../../vocabularies/spc-decision-type.csv) and [`spc-text-source`](../../vocabularies/spc-text-source.csv) under [`../../vocabularies/`](../../vocabularies/).

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
| `text_source` | string | Where the minutes' text came from: text_layer, ocr or mixed |
| `ocr_engine` | string | OCR engine and settings that read the scanned pages; empty when no page was OCR'd |

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
| `category` | string | councillors, sectoral_representatives, apologies, officials, presenters, guests or absent |
| `role` | string | Role as printed, empty when none is printed |
| `status` | string | present, apologies or absent |
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

## Where the text came from (`text_source`)

Most council minutes are published as scanned images with no text layer. Each
meeting's `text_source` says how its text was read: `text_layer` (the PDF's own
text), `ocr` (every page scanned) or `mixed`. For `ocr` and `mixed` meetings,
`ocr_engine` names the engine and its settings (Tesseract, language, page
segmentation mode and resolution).

For `ocr` and `mixed` meetings, "verbatim" means **verbatim to the OCR text**, not
to the printed page: the render is checked against the words the OCR read, word
for word. OCR can misread words, accents, bullet marks and handwriting, and a
mark on the paper can become a stray token, so the source PDF, identified by
`source_url` and `source_sha256`, is authoritative. A page whose OCR confidence
is below the pipeline's threshold is never published, and a blank page is
skipped only by a reviewed, committed override.

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

- Meetings: 17
- People: 90
- Attendance rows: 280
- Items: 128
- Decisions: 42

## People named in this dataset

The dataset names councillors, council officials, sectoral representatives (which
can include private citizens, for example Public Participation Network
representatives), presenters and guests, with their attendance, apologies and
the role printed in the minutes. Every name and role comes from minutes the
council itself published. Names are matched to a committed register; nothing is
added about a person beyond what the minutes print. To ask for a correction or
removal, write to dave@publicinformation.ie.

## Source, attribution and licence

Sources (each meeting records its `source_url` and the PDF's `source_sha256`;
the minutes are the councils' material, reproduced here without alteration to
their wording):

- Kildare County Council: https://kildarecoco.ie/YourCouncil/YourElectedCouncil/Committees/StrategicPolicyCommittees/TransportationSafetyandEmergencyServices/
- Meath County Council: https://www.meath.ie/council/your-council/your-elected-council/strategic-policy-committees/transportation-and-urban-regeneration-spc
- Westmeath County Council: https://www.westmeathcoco.ie/en/ourservices/yourcouncil/meetingsminutesagendasandreports/strategicpolicycommittees/planningregenerationtransportation/

COFOG 1999 is the UN Statistics Division classification; transport subdomains
follow the transport-governance vocabulary. The topics, decisions and attendance
tables are derived by PublicInformation.ie (an LLM proposes topics and decisions;
each decision is checked to be a verbatim quote).

The derived dataset is published under CC BY 4.0. Each council's own re-use
terms for the underlying minutes have not been independently confirmed against
its website; if you re-use the verbatim minutes, check them.
Attribute as: *Source: Kildare County Council, Meath County Council, Westmeath County Council; processed by PublicInformation.ie.*

## Reproducing

See `pipelines/spc_pipeline/README.md` in the repository: requirements, the LLM
credentials and cost, and the step order.
